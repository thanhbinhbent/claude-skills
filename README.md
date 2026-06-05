# Claude Skills — Aggregator

An **open source** project that collects [Agent Skills](https://agentskills.io) for Claude
from several source repos (plus your own), keeps them up to date, and installs them into
Claude's skills folder — your way. Nothing runs automatically.

> A skill is a folder with a `SKILL.md` file (frontmatter + instructions) that Claude loads
> on demand.

## Quick start

```bash
git clone <this-repo-url> claude-skills && cd claude-skills
python3 scripts/sync.py      # pull skills from the sources (already committed, optional)
./scripts/install.sh         # install into ~/.claude/skills
```

## How it works

```
sources.json  ──sync.py──▶  external-skills/   (pulled, committed)
custom-skills/              (your own skills, never touched by sync)
        └────install.sh────▶  ~/.claude/skills  or  <project>/.claude/skills
```

- `external-skills/SOURCES.lock.json` records the source repo + commit for every skill.
- `.github/workflows/update-skills.yml` re-runs sync daily and commits updates.

## Updating

```bash
git pull                  # get the latest committed skills (nothing else runs)
python3 scripts/sync.py   # or re-pull from sources yourself
```

Symlink installs update existing skills automatically after a pull; re-run `install.sh` to pick
up new ones (or to refresh a `--copy` install).

## Installing

```bash
./scripts/install.sh                     # symlink → ~/.claude/skills        (global, default)
./scripts/install.sh --project [DIR]     # symlink → DIR/.claude/skills      (default: cwd)
./scripts/install.sh --target DIR        # symlink → DIR
./scripts/install.sh --copy ...          # copy real files instead of symlinks
./scripts/install.sh --uninstall ...     # remove skills from that target
```

- **Global** = available in every project; **project** = scoped to one folder.
- **Symlink** = tiny, auto-updates; **copy** = portable, safe to commit & share.

## Sources

Each entry in `sources.json` (only `repo` is required):

```json
{ "repo": "https://github.com/owner/repo.git", "ref": "main", "path": "skills",
  "name": "", "include": [], "exclude": [], "prefix": "" }
```

`path` = folder holding skills in that repo · `include`/`exclude` = filter by name ·
`prefix` = force-namespace all skills. After editing, run `sync.py` then `install.sh`.

**Name clashes** are handled automatically: the earlier source keeps the clean name, a later
duplicate is renamed to `<source>-<name>`. `custom-skills/` always wins over `external-skills/`.

## Write your own skill

Create `custom-skills/<name>/SKILL.md` with `name` + `description` frontmatter, then run
`./scripts/install.sh`. See [./template](./template) and [./spec](./spec).

## License

The aggregator tooling (`scripts/`, `.github/`, `sources.json`, docs) is **MIT** — see
[LICENSE](./LICENSE). Skills in `external-skills/` keep their source repo's license (all MIT or
Apache-2.0); each skill's origin is recorded in `external-skills/SOURCES.lock.json` and its
original license files travel with it.
