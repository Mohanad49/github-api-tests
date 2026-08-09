# GitHub REST API — Automated Test Suite

[![GitHub API Tests](https://github.com/Mohanad49/github-api-tests/actions/workflows/api-tests.yml/badge.svg)](https://github.com/Mohanad49/github-api-tests/actions/workflows/api-tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

API test suite for the [GitHub REST API](https://docs.github.com/en/rest), built with
**Python, requests and pytest**. 56 tests over repositories, issues, users and
authentication, running nightly against the live API.

**[Allure report →](https://mohanad49.github.io/github-api-tests/)** ·
**[Flake history on TestPulse →](https://testpulse-eight.vercel.app/suites/github-api)**

The target is a real, public, rate-limited API rather than a practice sandbox, which is
the point: the interesting problems in API testing are the ones a sandbox does not have.

---

## What it covers

| Module | Coverage |
|---|---|
| `test_repositories` | CRUD, JSON Schema validation, pagination and `Link` headers, rate-limit headers, negative cases |
| `test_issues` | Create, update, close, labels, comments, state filtering, negative cases |
| `test_users` | Authenticated and public lookup, schema validation, an idempotent write |
| `test_auth` | Invalid, missing and malformed tokens; 401 bodies; public endpoints |
| `test_rate_limiting` | The suite's own throttling client — offline, no token needed |

Every response body that has a schema is validated against one in `schemas/`, so a test
asserting `200` is also asserting the shape of what came back.

## Three things worth reading the code for

### 1. The suite used to rate-limit itself, and blamed the API

Every scheduled run failed for ten consecutive nights. The failures looked like this:

```
E  assert 403 == 201
ERROR tests/test_issues.py::TestIssues::test_add_label_to_issue
  AssertionError: Repo creation failed — status 403: {"message":"You have exceeded a
  secondary rate limit and have been temporarily blocked from content creation..."}
```

GitHub enforces two different limits. The **primary** one — 5,000 requests an hour — is
the famous one, and this suite never came close to it. The **secondary** limits govern
*rates*, and one of them caps how fast an account may create content. A repository is
content. So is an issue, a comment, a label, and the initial commit `auto_init` makes.

The suite created a fresh repository for every test that needed one: nine repositories,
nine initial commits and six issues, as fast as the network allowed. Then a nightly job
was added that ran three more copies of the suite in parallel, all sharing one token.
Four concurrent bursts of content creation is exactly what the limit exists to stop.

The fix has three parts, and only one of them is "send fewer requests":

- **`utils/api_client.py`** — `GitHubSession` paces writes a second apart (GitHub's own
  documented guidance), honours `Retry-After`, waits out an exhausted primary limit and
  backs off on secondary ones. The rate-limit helpers were already in this file. Nothing
  imported them.
- **`conftest.py`** — one repository shared across the tests that only read from it. The
  cost is isolation, and the reason it is affordable is written down in the fixture
  rather than glossed over.
- **`.github/workflows/api-tests.yml`** — the nightly repeats run one at a time. Three
  runs of one commit disagreeing only means something if nothing else about the runs
  differed, and "how many siblings were competing for the same token" is a difference.

### 2. The retry logic deliberately refuses to retry some 403s

GitHub returns `403` both for *you are going too fast* and for *you may not do that*,
and this suite asserts on the second kind. A retry layer that cannot tell them apart
turns a fast, correct negative test into a five-minute sleep ending in the same answer.

So `is_rate_limited()` requires positive evidence of throttling — a `Retry-After`
header, an exhausted `x-ratelimit-remaining`, or the secondary-limit message in the body
— and `tests/test_rate_limiting.py` pins that behaviour with a test named
`test_plain_403_is_not_retried`. Those tests are offline: they construct responses
rather than provoking real limits, because a test that abuses the API to prove it
handles abuse is not one anyone can run on a fork.

### 3. The write test writes the same value back

`test_patch_authenticated_user_is_accepted` exercises `PATCH /user` by setting the bio to
whatever it already is.

An earlier version set a test string and restored it on the next line — safe right up
until the process dies between those two calls. A cancelled workflow or a runner timeout
would leave a real, public profile advertising that a test suite writes to it, and on a
nightly schedule that is several chances a week. Writing the current value back exercises
the same endpoint, auth, status code and response shape with no window to clean up.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then paste a PAT with repo + user + delete_repo scopes
pytest tests/ -v
```

The suite creates and deletes private repositories under the authenticated account, so
point it at a token you are happy to have do that. It needs three scopes: `repo` to
create, `user` to exercise `PATCH /user`, and `delete_repo` — without the last one,
cleanup silently 403s and leaves `test-repo-*` repositories behind.

Selected runs:

```bash
pytest tests/ -v -m smoke                    # smoke only
pytest tests/ -v -m negative                 # negative cases only
pytest tests/test_rate_limiting.py           # offline; no token, no network

pytest tests/ --alluredir=allure-results && allure serve allure-results
```

## Layout

```
.github/workflows/api-tests.yml   CI: nightly, plus repeat runs for flake detection
tests/
  test_repositories.py            repo CRUD, schema, pagination
  test_issues.py                  issue CRUD, labels, comments
  test_users.py                   user info, schema, idempotent write
  test_auth.py                    auth negative testing
  test_rate_limiting.py           the throttling client itself (offline)
schemas/                          JSON Schemas: repository, issue, user
utils/
  api_client.py                   GitHubSession — pacing, backoff, retry policy
  schema_validator.py             schema loading and validation
conftest.py                       shared fixtures
```

## CI

Runs on push, on pull request, and nightly at 02:00 UTC. Each run:

1. Executes the suite and emits both Allure results and JUnit XML
2. Publishes the Allure report to GitHub Pages
3. Ingests the JUnit file into [TestPulse](https://github.com/Mohanad49/testpulse) —
   including on failure, because a red run is the data point that matters most

The nightly schedule additionally runs the same commit three more times, one after
another. pytest cannot report retries the way Playwright can, so the only way to produce
same-commit evidence of flakiness is to run one unchanged SHA several times and see
whether the outcomes agree.

## License

[MIT](LICENSE)
