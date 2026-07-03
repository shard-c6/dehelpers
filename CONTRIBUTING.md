# Contributing to dehelpers

First off, thank you for considering contributing to `dehelpers`! It's people like you who make open-source software a better place.

---

## Code of Conduct

Please note that this project is released with a Contributor Covenant [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

---

## How Can I Contribute?

### 1. Reporting Bugs
* Check the [Issues](https://github.com/shard-c6/dehelpers/issues) tab first to see if the bug has already been reported.
* If not, open a new issue. Include a clear description of the bug, steps to reproduce it, the expected behavior, and any relevant traceback or log output.

### 2. Suggesting Enhancements
* Open an issue describing the proposed feature, why it is useful, and how it fits into the scope of data engineering pipelines.

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
4. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
5. **Write your code & unit tests.** Make sure any new logic is fully covered by tests in the `tests/` directory.
6. **Run the test suite** to ensure everything works:
   ```bash
   pytest -v --tb=short -m "not postgres"
   ```
7. **Commit your changes** with a clear commit message:
   ```bash
   git commit -m "Add feature to support custom pagination parameters"
   ```
8. **Push your branch** to your fork:
   ```bash
   git push origin feature/my-cool-feature
   ```
9. **Open a Pull Request** against the `main` branch of the `shard-c6/dehelpers` repository.

---

## Development Guidelines

* **Coding Style:** Follow PEP 8 guidelines. Use clean docstrings and type hints for all public functions and classes.
* **Testing:** We maintain a high standard of coverage (≥90%). Every new feature should include comprehensive tests.
* **Fork Safety:** Keep in mind that connection pools (like the SQLAlchemy engine) should not be shared across fork boundaries. Ensure all resource cleanup is properly context-managed.
