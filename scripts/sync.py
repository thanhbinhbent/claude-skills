#!/usr/bin/env python3
"""Sync skills from upstream repos listed in sources.json into external-skills/.

Each run rebuilds external-skills/ from scratch so it stays deterministic: a skill
removed upstream or from the manifest disappears too. Provenance (repo + commit) is
written to external-skills/SOURCES.lock.json.

Standard library only — nothing to install.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
SOURCES_FILE = REPO_DIR / "sources.json"
OUT_DIR = REPO_DIR / "external-skills"
LOCK_FILE = OUT_DIR / "SOURCES.lock.json"


def run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd, cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def clean_out_dir() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)


def discover_skills(skills_root: Path) -> dict[str, Path]:
    """Return {skill_name: path} for every subfolder that has a SKILL.md."""
    found: dict[str, Path] = {}
    if not skills_root.is_dir():
        return found
    for child in sorted(skills_root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            found[child.name] = child
    return found


def derive_source_name(repo: str) -> str:
    """Derive a kebab-case source name from a repo URL — used as the auto prefix.

    https://github.com/anthropics/skills.git -> "anthropics-skills"
    git@github.com:owner/repo.git            -> "owner-repo"
    """
    s = repo.strip()
    if s.endswith(".git"):
        s = s[:-4]
    s = s.replace(":", "/")  # git@host:owner/repo -> .../owner/repo
    parts = [p for p in s.split("/") if p]
    tail = parts[-2:] if len(parts) >= 2 else parts[-1:]
    name = re.sub(r"[^a-z0-9]+", "-", "-".join(tail).lower()).strip("-")
    return name or "source"


def rewrite_skill_name(skill_dir: Path, new_name: str) -> None:
    """Rewrite the `name:` field in a SKILL.md frontmatter (used when prefixing).

    Claude identifies a skill by its frontmatter `name:`, so when we rename the folder
    with a prefix we must update this field too, otherwise it still clashes.
    """
    md = skill_dir / "SKILL.md"
    lines = md.read_text().splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":  # end of frontmatter
            break
        if lines[i].lstrip().startswith("name:"):
            indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
            nl = "\n" if lines[i].endswith("\n") else ""
            lines[i] = f"{indent}name: {new_name}{nl}"
            md.write_text("".join(lines))
            return


def main() -> int:
    if not SOURCES_FILE.is_file():
        print(f"error: {SOURCES_FILE} not found", file=sys.stderr)
        return 1

    sources = json.loads(SOURCES_FILE.read_text()).get("sources", [])
    if not sources:
        print("warning: sources.json has no sources — nothing to sync")

    clean_out_dir()

    lock: dict[str, dict] = {}
    # owner_of[name] = source that already claimed that output name (clash detection)
    owner_of: dict[str, str] = {}
    summary: list[str] = []

    # Cache clones by (repo, ref) so multiple sources pointing at the same repo
    # (different paths) don't re-clone — e.g. mattpocock/skills split by category.
    clones: dict[tuple, tuple] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        for idx, src in enumerate(sources):
            repo = src["repo"]
            name = (src.get("name") or "").strip() or derive_source_name(repo)
            ref = src.get("ref", "main")
            sub = src.get("path", ".")
            include = set(src.get("include", []) or [])
            exclude = set(src.get("exclude", []) or [])
            prefix = (src.get("prefix") or "").strip()

            key = (repo, ref)
            if key in clones:
                clone_dir, sha = clones[key]
            else:
                clone_dir = tmp_root / f"{idx}-{derive_source_name(repo)}"
                print(f"→ cloning {repo}@{ref} ...")
                run([
                    "git", "clone", "--depth", "1", "--branch", ref,
                    repo, str(clone_dir),
                ])
                sha = run(["git", "rev-parse", "HEAD"], cwd=clone_dir)
                clones[key] = (clone_dir, sha)

            skills_root = (clone_dir / sub).resolve()
            available = discover_skills(skills_root)

            picked = 0
            filtered: list[str] = []
            renamed: list[str] = []
            conflicts: list[str] = []
            for skill_name, skill_path in available.items():
                if include and skill_name not in include:
                    filtered.append(skill_name)
                    continue
                if skill_name in exclude:
                    filtered.append(skill_name)
                    continue

                # Decide the output folder name:
                #   - explicit prefix      -> always "<prefix>-<skill>"
                #   - no prefix, clashes   -> auto-prefix with the source name
                #   - no prefix, no clash  -> keep the original name
                if prefix:
                    out_name = f"{prefix}-{skill_name}"
                elif skill_name in owner_of:
                    out_name = f"{name}-{skill_name}"
                else:
                    out_name = skill_name

                if out_name in owner_of:
                    # Rare: still clashes after prefixing -> skip.
                    conflicts.append(f"{skill_name} -> {out_name} (already exists)")
                    continue

                shutil.copytree(skill_path, OUT_DIR / out_name)
                if out_name != skill_name:
                    # Also rewrite frontmatter name: so Claude treats it as a distinct skill.
                    rewrite_skill_name(OUT_DIR / out_name, out_name)
                    renamed.append(f"{skill_name} -> {out_name}")
                owner_of[out_name] = name
                lock[out_name] = {
                    "source": name,
                    "repo": repo,
                    "ref": ref,
                    "sha": sha,
                    "skill": skill_name,
                }
                picked += 1

            msg = f"  {name}: {picked} skill(s)"
            if filtered:
                msg += f" (filtered out: {', '.join(sorted(filtered))})"
            if renamed:
                msg += f"\n    ↳ renamed to avoid clash: {', '.join(renamed)}"
            if conflicts:
                msg += f"\n    ⚠ skipped: {', '.join(conflicts)}"
            summary.append(msg)

    LOCK_FILE.write_text(json.dumps(dict(sorted(lock.items())), indent=2) + "\n")

    print("\nDone:")
    for line in summary:
        print(line)
    print(f"  total: {len(lock)} skill(s) -> {OUT_DIR.relative_to(REPO_DIR)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
