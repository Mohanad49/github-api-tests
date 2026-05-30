# GitHub REST API — Automated Test Suite

Automated API test suite for the [GitHub REST API](https://docs.github.com/en/rest) using **Python + Requests + PyTest**.

## Tech Stack

| Layer          | Tool                      |
|----------------|---------------------------|
| HTTP Client    | `requests`                |
| Test Framework | `pytest`                  |
| Schema Valid.  | `jsonschema`              |
| Reporting      | `allure-pytest`, `pytest-html` |
| CI/CD          | GitHub Actions            |

## What's Tested

| Module               | Coverage                                                                 |
|----------------------|--------------------------------------------------------------------------|
| `test_repositories`  | CRUD, schema validation, pagination, rate-limit headers, negative cases  |
| `test_issues`        | Create, update, close, labels, comments, filtering, negative cases       |
| `test_users`         | Authenticated & public user lookup, schema validation, bio update        |
| `test_auth`          | Invalid/missing/malformed tokens, 401 body checks, public endpoints      |

## Setup

```bash
# 1. Clone & enter
git clone <repo-url> && cd github-api-tests

# 2. Create & activate virtual env
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your token
cp .env.example .env
# Edit .env and paste your GitHub PAT (needs repo + user scopes)
```

## Running Tests

```bash
# All tests, verbose
pytest tests/ -v

# Smoke tests only
pytest tests/ -v -m smoke

# Negative tests only
pytest tests/ -v -m negative

# Generate HTML report
pytest tests/ -v --html=report.html --self-contained-html

# Generate Allure results
pytest tests/ -v --alluredir=allure-results
allure serve allure-results
```

## Project Structure

```
├── .github/workflows/api-tests.yml   # CI pipeline
├── tests/
│   ├── test_repositories.py          # Repo CRUD, schema, pagination
│   ├── test_issues.py                # Issue CRUD, labels, comments
│   ├── test_users.py                 # User info, schema, bio update
│   └── test_auth.py                  # Auth negative testing
├── schemas/
│   ├── repository.json               # JSON Schema for repos
│   ├── issue.json                    # JSON Schema for issues
│   └── user.json                     # JSON Schema for users
├── utils/
│   ├── api_client.py                 # Reusable API client wrapper
│   └── schema_validator.py           # Schema loading & validation
├── conftest.py                       # Shared fixtures (session, test_repo, test_issue)
├── .env.example                      # Token template
├── pytest.ini                        # Pytest config & markers
└── requirements.txt                  # Pinned dependencies
```

## CI/CD

The GitHub Actions workflow (`.github/workflows/api-tests.yml`) runs on every push/PR to `main`:

1. Installs Python 3.11 + dependencies
2. Runs the full test suite with Allure output
3. Publishes an Allure report to `gh-pages`
