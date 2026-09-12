# Release Notes - SnipeIT-CLI v0.1.0

**Branch:** `snipeit-cli-start`  
**Date:** September 11, 2026  
**Author:** Lisa Jacklin-Wyatt  
**License:** MIT License  

---

## Overview

Initial release of SnipeIT-CLI, a command-line interface for querying and managing Snipe-IT inventory and assets.

---

## Features

### 1. Terminal Interface
- Formatted tables with color-coded status and assignments using Rich.
- Status tables for connection checks and response latency.
- Progress indicators during network requests.

### 2. Configuration System
- **Single Template (`example-config.py`)**: General configuration template with generic placeholders for any Snipe-IT deployment.
- **Local User Configuration (`config.py`)**: Users copy `example-config.py` to `config.py` for local settings. This file is excluded from Git commits via `.gitignore`.
- **Development Profile (`dev-config.py`)**: Support for local testing configurations without committing credentials.
- **Environment Variables**: Full fallback support for `SNIPEIT_URL` and `SNIPEIT_API_TOKEN`.

### 3. Commands
- `snipeit test auth`: Tests connectivity, response time, and API credentials.
- `snipeit asset list`: Queries hardware assets with pagination (`--limit`, `--offset`) and text filtering (`--search`).
- `snipeit user me`: Displays account details for the authenticated user.

### 4. Security
- Exclusion rules in `.gitignore` covering `.cred`, `.env`, and local config files.
- Error handlers structured to prevent printing API tokens in terminal output.

### 5. Packaging and CI
- PEP 621 metadata defined in `pyproject.toml`.
- GitHub Actions CI workflow covering Python 3.10 through 3.14.
- `CONTRIBUTING.md` and MIT License included.

---

## AI Assistance Disclosure

This project was developed by Lisa Jacklin-Wyatt with pair-programming assistance from Google DeepMind's agentic AI coding assistant (Antigravity).

AI assistance included:
- CLI command structure and terminal formatting using Typer and Rich.
- Configuration loading design and credential fallback handling.
- Security auditing of error messages.
- Packaging configuration and GitHub Actions CI workflow setup.

All commands and API calls were reviewed and validated against active Snipe-IT instances.

---

## Setup Instructions

```bash
git clone -b snipeit-cli-start https://github.com/LisaJacklin/SnipeIT-CLI.git
cd SnipeIT-CLI

python3 -m venv .venv
source .venv/bin/activate

pip install -e .

cp example-config.py config.py
# Edit config.py with your URL and API token

snipeit test auth
```

