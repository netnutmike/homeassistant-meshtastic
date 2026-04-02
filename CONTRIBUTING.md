# Contributing

Thanks for your interest in contributing to the Meshtastic Home Assistant Integration! This guide covers everything you need to get started.

## Table of Contents

- [Branching Strategy](#branching-strategy)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Running Tests](#running-tests)
- [Pull Request Process](#pull-request-process)
- [Commit Messages](#commit-messages)
- [Reporting Issues](#reporting-issues)
- [License](#license)

## Branching Strategy

We use a two-branch model with semantic versioning (`x.y.z`) for releases:

```
main ← production-ready releases (tagged with vX.Y.Z)
dev  ← active development (default target for PRs)
```

### Branch Types

| Branch Type | Created From | Merges Into | Naming Convention |
|-------------|-------------|-------------|-------------------|
| Feature | `dev` | `dev` | `feature/your-feature-name` |
| Bug fix | `dev` | `dev` | `fix/issue-description` |
| Hotfix | `main` | `main` and `dev` | `hotfix/description` |
| Release | `dev` | `main` | `release/vX.Y.Z` |

### Workflow

1. **Feature work**: Create a branch from `dev` → `feature/your-feature-name`
2. **Bug fixes**: Create a branch from `dev` → `fix/issue-description`
3. **Hotfixes** (production-critical): Create a branch from `main` → `hotfix/description`
4. Open a PR targeting `dev` (or `main` for hotfixes)
5. After review and CI passes, merge via squash merge
6. Releases: `dev` is merged to `main` when ready for release, tagged with a semantic version

### Branch Protection

Both `main` and `dev` branches should have these protections enabled:

- **Require passing CI checks before merge** — all tests, linting, type checking, and coverage gates must pass
- **Require at least one code review approval** — another maintainer must approve the PR
- **Prevent force pushes** — history must remain linear and auditable
- **Prevent branch deletion** — `main` and `dev` must never be deleted

> **For repository admins:** Configure these rules in GitHub → Settings → Branches → Branch protection rules for both `main` and `dev`.

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **Major** (`x.0.0`): Breaking changes
- **Minor** (`0.y.0`): New features, backward compatible
- **Patch** (`0.0.z`): Bug fixes, backward compatible

Release tags use the format `vX.Y.Z` (e.g., `v1.0.0`).

## Development Setup

### Prerequisites

- Python 3.12+
- pip
- Git

### Quick Start

```bash
# Clone and set up
git clone https://github.com/your-username/homeassistant-meshtastic.git
cd homeassistant-meshtastic
make setup

# Or manually
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

See `.env.example` for all available variables with descriptions.

### Verify Your Setup

```bash
make verify-setup
```

This checks that Python, the virtual environment, and all required tools (ruff, mypy, pytest) are correctly installed.

## Development Workflow

A typical development cycle looks like this:

1. **Pick an issue** or create one describing what you want to work on
2. **Create a branch** from `dev`:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** — write code and tests
4. **Run quality checks locally**:
   ```bash
   make lint        # Check code style
   make test        # Run tests with coverage
   make type-check  # Run mypy
   ```
5. **Fix any issues**:
   ```bash
   make lint-fix    # Auto-fix linting issues
   ```
6. **Commit and push**:
   ```bash
   git add .
   git commit -m "feat: describe your change"
   git push origin feature/your-feature-name
   ```
7. **Open a PR** targeting `dev` and fill out the PR template
8. **Address review feedback** and wait for CI to pass
9. **Merge** via squash merge once approved

### Available Make Targets

| Target | Description |
|--------|-------------|
| `make setup` | Create virtual environment and install dependencies |
| `make install` | Install/update dependencies |
| `make test` | Run all tests with coverage |
| `make test-watch` | Run tests in watch mode |
| `make lint` | Check code style with ruff |
| `make lint-fix` | Auto-fix linting issues |
| `make type-check` | Run mypy type checking |
| `make verify-setup` | Verify all prerequisites are installed |

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting, configured in `home-assistant/.ruff.toml`.

```bash
make lint       # Check for issues
make lint-fix   # Auto-fix issues
```

### Key Rules

- **Line length**: 120 characters
- **Target**: Python 3.12+
- **Style**: PEP 8 conventions with `ALL` ruff rules enabled (see `.ruff.toml` for specific ignores)
- **Type hints**: Required for all function signatures
- **Docstrings**: Encouraged for public functions and classes
- **Protobuf files**: Excluded from linting (`aiomeshtastic/protobuf/`)

### Example

```python
async def connect(
    self,
    broker_host: str,
    broker_port: int = 1883,
    use_tls: bool = False,
) -> None:
    """Connect to the MQTT broker."""
    ...
```

## Running Tests

```bash
make test           # Run all tests with coverage
make type-check     # Run mypy type checking
make verify-setup   # Check your environment
```

Tests use **pytest** with **Hypothesis** for property-based testing. Coverage must stay above **80%**.

### Test Structure

```
tests/
├── conftest.py                  # Shared fixtures, Hypothesis settings
├── test_mqtt_connection.py      # MqttConnection tests
├── test_mqtt_decoder.py         # MqttPacketDecoder tests
├── test_mqtt_encryption.py      # AES-CTR encryption tests
├── test_mqtt_topic_parsing.py   # Topic parsing tests
├── test_mqtt_config_flow.py     # Config flow tests
└── test_mqtt_api_client.py      # API client routing, node discovery, dual-mode tests
```

### Hypothesis Profiles

- **`dev`** (default): 100 examples per property test
- **`ci`**: 200 examples per property test

## Pull Request Process

1. **Branch from `dev`** (or `main` for hotfixes only)
2. **Make your changes** with tests covering new functionality
3. **Run checks locally**:
   ```bash
   make lint
   make test
   make type-check
   ```
4. **Push and open a PR** targeting `dev`
5. **Fill out the PR template** — include description, testing steps, and related issues
6. **Wait for CI** — all checks must pass (tests, lint, type check, coverage ≥ 80%)
7. **Wait for code review** — at least one maintainer approval required
8. **Address any feedback**
9. **Squash merge** once approved

> **Important:** All PRs must target `dev` unless they are hotfixes. Hotfix PRs target `main` and should also be merged back into `dev`.

## Commit Messages

Use clear, descriptive commit messages following conventional commit style:

```
feat: add MQTT TLS support
fix: handle empty channel key in decoder
docs: update MQTT setup instructions
test: add property test for nonce construction
refactor: extract topic parsing into helper
chore: update dependencies
```

## Reporting Issues

Use the GitHub issue templates for:

- **Bug reports** — include steps to reproduce, expected vs actual behavior
- **Feature requests** — describe the use case and proposed solution
- **Security vulnerabilities** — use responsible disclosure via the security template

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
