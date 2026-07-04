# Contributing to dehelpers

First off, thank you for considering contributing to `dehelpers`! It's people like you who make open-source software a better place.

---

## Code of Conduct

Please note that this project is released with a Contributor Covenant [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

---

## How Can I Contribute?

### 1. Reporting Bugs
* Check the [Issues](https://github.com/shard-c6/dehelpers/issues) tab first to see if the bug has already been reported.
* If not, open a new issue using the [Bug Report template](https://github.com/shard-c6/dehelpers/issues/new?template=bug_report.yml). Include a clear description, steps to reproduce, expected behavior, and any relevant traceback.

### 2. Suggesting Enhancements
* Open an issue using the [Feature Request template](https://github.com/shard-c6/dehelpers/issues/new?template=feature_request.yml), describing the proposed feature, why it is useful, and how it fits into the scope of data engineering pipelines.
* Check the [ROADMAP.md](ROADMAP.md) first — your idea might already be planned.

### 3. Submitting Pull Requests
We welcome pull requests! To submit a change:

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/dehelpers.git
   cd dehelpers
   ```
3. **Install the package in editable mode** with development dependencies:
   ```bash
   pip install -e ".[dev,dataframe]"
   ```
4. **Set up pre-commit hooks** (this is required — CI will reject code that doesn't pass):
   ```bash
   pre-commit install
   ```
5. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
6. **Write your code & unit tests.** Make sure any new logic is fully covered by tests in the `tests/` directory.
7. **Run the checks** to ensure everything passes:
   ```bash
   # Run all pre-commit hooks (ruff lint, ruff format, mypy)
   pre-commit run --all-files

   # Run the test suite
   pytest -v --tb=short -m "not postgres"
   ```
8. **Commit your changes** with a clear commit message:
   ```bash
   git commit -m "Add feature to support custom pagination parameters"
   ```
9. **Push your branch** to your fork:
   ```bash
   git push origin feature/my-cool-feature
   ```
10. **Open a Pull Request** against the `main` branch of the `shard-c6/dehelpers` repository. The PR template will guide you through a checklist.

---

## Code Style & Tools

We enforce consistent code quality with automated tooling:

| Tool | Purpose | Config |
|------|---------|--------|
| **[ruff](https://docs.astral.sh/ruff/)** | Linting & formatting | `[tool.ruff]` in `pyproject.toml` |
| **[mypy](https://mypy.readthedocs.io/)** | Static type checking | `[tool.mypy]` in `pyproject.toml` |
| **[pre-commit](https://pre-commit.com/)** | Runs all checks on `git commit` | `.pre-commit-config.yaml` |

After cloning, always run `pre-commit install` so hooks run automatically on every commit.

---

## Development Guidelines

* **Type Hints:** All public functions and parameters must have type annotations.
* **Testing:** We maintain ≥90% coverage. Every new feature should include comprehensive tests.
* **Docstrings:** Use Google-style docstrings for all public classes and functions.
* **Fork Safety:** Keep in mind that connection pools (like the SQLAlchemy engine) should not be shared across fork boundaries. Ensure all resource cleanup is properly context-managed.
* **Changelog:** Add a note under `[Unreleased]` in `CHANGELOG.md` for every user-facing change.

---

## First-Time Contributors

Look for issues labeled [`good first issue`](https://github.com/shard-c6/dehelpers/labels/good%20first%20issue) — these are small, self-contained tasks designed to help you get familiar with the codebase.
