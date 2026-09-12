# SnipeIT-CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/LisaJacklin/SnipeIT-CLI/actions/workflows/ci.yml/badge.svg)](https://github.com/LisaJacklin/SnipeIT-CLI/actions)

A command-line interface for querying and managing Snipe-IT inventory and assets.

---

## Quick Start

### 1. Installation

Clone the repository and install in a virtual environment:

```bash
git clone https://github.com/LisaJacklin/SnipeIT-CLI.git
cd SnipeIT-CLI

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

### 2. Configuration

Set up your credentials using one of the following methods:

#### Option A: Configuration File (Recommended)
Copy the example configuration to `config.py`:
```bash
cp example-config.py config.py
# Edit config.py with your Snipe-IT server URL and API token.
# config.py is ignored by Git to prevent committing credentials.
```

#### Option B: Credential Files
Place your API token on a single line in `dev.cred` or `prod.cred`:
```bash
cp example.cred dev.cred
# Paste your token into dev.cred
```

#### Option C: Environment Variables
```bash
export SNIPEIT_URL="https://snipeit.example.com"
export SNIPEIT_API_TOKEN="your_token_here"
```

---

## Commands

### Test Connectivity
Test connection and authentication against your Snipe-IT instance:
```bash
# Test using default settings
snipeit test auth

# Test using production profile
snipeit test auth --profile prod

# Test against a specific URL
snipeit test auth --url https://snipeit.example.com
```

### Hardware Assets
```bash
# List first 10 assets
snipeit asset list

# Search for assets by text query
snipeit asset list --search "MacBook" --limit 20
```

### User Management
```bash
# View account details for the authenticated user
snipeit user me
```

---

## Project Structure

- [`snipeit.py`](file:///home/lmjacklin/Github/SnipeIT-CLI/snipeit.py) - Main CLI implementation.
- [`example-config.py`](file:///home/lmjacklin/Github/SnipeIT-CLI/example-config.py) - Configuration template.
- [`pyproject.toml`](file:///home/lmjacklin/Github/SnipeIT-CLI/pyproject.toml) - Build configuration and package metadata.
- [`CONTRIBUTING.md`](file:///home/lmjacklin/Github/SnipeIT-CLI/CONTRIBUTING.md) - Contribution guidelines.
- [`RELEASE_NOTES.md`](file:///home/lmjacklin/Github/SnipeIT-CLI/RELEASE_NOTES.md) - Release notes for v0.1.0.

---

## AI Assistance Disclosure

This project was developed by Lisa Jacklin-Wyatt with pair-programming assistance from Google DeepMind's agentic AI coding assistant (Antigravity).

AI assistance included:
- CLI command structure and terminal output formatting using Typer and Rich.
- Configuration loading architecture and profile fallback logic.
- Security auditing of error handling to prevent API token exposure.
- Package configuration for open-source distribution and GitHub Actions CI testing.

All API interactions and commands were reviewed and tested against live Snipe-IT instances.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.