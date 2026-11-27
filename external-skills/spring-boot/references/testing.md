# Testing Spring Boot Applications

## Test data setup
- Prefer using real services via Testcontainers instead of mocks
- **Prefer SQL fixtures.** Put them in `src/test/resources/test-data.sql` and add `@Sql("classpath:/test-data.sql")` at class level so they load before every test method (the default `BEFORE_TEST_METHOD` phase).
- Keep fixtures deterministic and independent of test order.
- **For programmatic setup**, call exposed Services or ModuleAPI classes, not Repositories. That way setup follows business rules and module boundaries.
- **Avoid `JdbcTemplate` / `JdbcClient` / `TransactionTemplate` for fixture SQL** unless absolutely necessary. They couple tests to internals. This rule doesn't apply when the JDBC call is itself the behavior under test.

## End-to-end REST API tests with `BaseIT` + `RestTestClient`

Put the common setup in a base class:
- `RANDOM_PORT`
- the shared Testcontainers config
- the `test` profile
- SQL fixtures

```java
@SpringBootTest(webEnvironment = RANDOM_PORT)
@Import(TestcontainersConfig.class)
@AutoConfigureRestTestClient
@Sql("/test-data.sql")
public abstract class BaseIT {
    @Autowired protected RestTestClient restTestClient;
    @Autowired protected JsonMapper jsonMapper;

    protected String getUserAuthToken() { /* obtain JWT for a fixture user */ return "jwt-token"; }
}
```

```java
class UserControllerTests extends BaseIT {

    @Test
    void shouldRegisterUserSuccessfully() {
        RegisterUserResponse response = restTestClient.post().uri("/api/users")
                .contentType(MediaType.APPLICATION_JSON)
                .body("""
                        {"fullName":"User123","email":"user123@gmail.com","password":"Secret@121212"}
                        """)
                .exchange()
                .expectStatus().isCreated()
                .returnResult(RegisterUserResponse.class)
                .getResponseBody();

        assertThat(response.email()).isEqualTo("user123@gmail.com");
    }
}
```

## Testing Web Application with MockMvcTester

Follow these principles when testing Spring Boot Web MVC controllers with MockMvcTester:

- Use `MockMvcTester` for AssertJ-style fluent assertions instead of `MockMvc`
- Use `@WebMvcTest` for slice tests that focus on a single controller
- Use `@SpringBootTest` with `@AutoConfigureMockMvc` for integration tests

### Migrating from MockMvc

If gradually adopting MockMvcTester:

```java
@Autowired
MockMvc mockMvc;

MockMvcTester mockMvcTester;

@PostConstruct
void setUp() {
    mockMvcTester = MockMvcTester.create(mockMvc);
}
```

### Basic test structure

Simple single-statement assertions:

```java
@Test
void shouldRenderHomePage() {
    assertThat(mockMvcTester.get().uri("/home"))
        .hasStatusOk();
}
```

### Testing the view rendering controllers

#### Assert view name and model attributes

```java
@Test
void shouldGetUserById() {
    var result = mockMvcTester.get().uri("/users/1").exchange();
    assertThat(result)
            .hasStatusOk()
            .hasViewName("user")
            .model()
            .containsKeys("user")
            .containsEntry("user", new User(1L, "Siva", "siva@gmail.com", "siva"));
}
```

#### Assert URL redirects and flash attributes

```java
@Test
void shouldCreateUserSuccessfully() {
    var result = mockMvcTester.post().uri("/users")
            .contentType(MediaType.APPLICATION_FORM_URLENCODED)
            .param("name", "Test User 4")
            .param("email", "testuser4@gmail.com")
            .param("password", "testuser4")
            .exchange();
    assertThat(result)
            .hasStatus(HttpStatus.FOUND)
            .hasRedirectedUrl("/users")
            .flash().containsKey("successMessage")
            .hasEntrySatisfying("successMessage",
                    value -> assertThat(value).isEqualTo("User saved successfully"));
}
```

#### Assert model validation errors

```java
@Test
void shouldGetErrorsWhenUserDataIsInvalid() {
   var result = mockMvcTester.post().uri("/users")
           .contentType(MediaType.APPLICATION_FORM_URLENCODED)
           .param("name", "") // blank -invalid
           .param("email", "testuser4gmail.com") // invalid email format
           .param("password", "pwd") // valid
           .exchange();
   assertThat(result)
           .model()
           .extractingBindingResult("user")
           .hasErrorsCount(2)
           .hasFieldErrors("name", "email");
}
```
