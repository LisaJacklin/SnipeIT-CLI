# Release Notes - SnipeIT-CLI

---

## v0.2.0 - Asset Management Suite

**Branch:** `snipeit-cli-start`  
**Date:** October 19, 2026  
**Author:** Lisa Jacklin-Wyatt  
**License:** MIT License  

### Overview

SnipeIT-CLI v0.2.0 introduces comprehensive single and bulk asset management capabilities. Users can now query, create, update, bulk import, and bulk update hardware assets in Snipe-IT with interactive guided walkthroughs, CLI flags, automatic ID/name resolution, before/after diff previews, and dry-run simulation mode.

### Features & Improvements

#### 1. Asset Creation (`asset create`, `asset add`)
- **Interactive Guided Creation**: When required options (`--model-id`, `--status-id`) are omitted without `--yes`, users are presented with searchable tables of available models and status labels, and prompted with validation.
- **Friendly Resolution**: Accepts numeric database IDs or human-readable model, status, and location names (case-insensitive with exact and partial matching).
- **Auto-generated Tag Support**: Allows leaving the asset tag blank to let Snipe-IT generate tags based on server auto-increment settings.
- **Verification Summary**: Renders a formatted Rich summary table before committing changes, with confirmation prompt.

#### 2. Asset Updates (`asset update`, `asset edit`)
- **Flexible Identifier Lookup**: Target assets can be specified by database ID, Asset Tag (e.g., `ACEP-00001`), or Hostname.
- **In-Place Interactive Editing**: Running without flags displays current asset attributes and prompts the user with current values pre-filled as default values (press Enter to keep).
- **Flag-Based Partial Updates**: Update one or more attributes (`--name`, `--status-id`, `--location-id`, `--notes`, `--serial`, etc.) directly via CLI flags.
- **Color-Coded Diff Preview**: Displays a comparison table highlighting current vs. proposed values before sending `PATCH` requests.

#### 3. Bulk Asset Creation (`asset bulk-add`, `asset bulk-create`)
- **CSV and JSON Import**: Import assets from spreadsheets and structured JSON files.
- **Header Alias Normalization**: Flexible column mapping supporting common variations (`tag` / `asset_tag`, `model` / `model_name`, `status` / `status_label`, `hostname` / `name`, etc.) and Excel UTF-8 BOM tolerance.
- **Cached Metadata Resolution**: Fetches models, status labels, and locations once to avoid repetitive API round-trips.
- **Pre-Flight Validation**: Validates all rows before sending write requests, highlighting missing or invalid models/statuses in a preview table.
- **Dry-Run Mode (`--dry-run`)**: Test and validate import spreadsheets against Snipe-IT without creating assets.
- **Batch Results Reporting**: Displays detailed execution results with row numbers, created IDs, and specific error messages for failed items.

#### 4. Bulk Asset Updates (`asset bulk-update`)
- **Dual Update Modes**:
  - **Spreadsheet Mode (`--file`)**: Update disparate assets using a CSV or JSON file containing identifier columns (`asset_tag`, `id`, `name`) and updated fields.
  - **CLI Batch Mode**: Update multiple assets simultaneously using positional arguments or `--tags "TAG1,TAG2"` combined with flags (e.g. `--status-id "Archived" --location-id "Storage"`).
- **Simulation Mode (`--dry-run`)**: Preview planned changes and asset matches before making modifications.
- **Action Confirmation & Summary**: Displays planned updates in a table with user confirmation and comprehensive success/failure reporting.

#### 5. Starter CSV Templates (`asset template`)
- Built-in generator (`snipeit asset template [add|update]`) to export starter CSV templates to stdout or save directly to a file (`-o filename.csv`).

#### 6. Developer Experience & Testing
- Comprehensive unit test suite (`tests/test_snipeit.py`) covering resolution logic, file parsers, CLI execution, and API error formatting.
- Integrated automated testing into the GitHub Actions CI workflow across Python 3.10–3.13.
- `--version` flag (`snipeit --version`) displaying current release.

---

## v0.1.0 - Initial Release

**Branch:** `snipeit-cli-start`  
**Date:** September 11, 2026  
**Author:** Lisa Jacklin-Wyatt  
**License:** MIT License  

### Overview

Initial release of SnipeIT-CLI, a command-line interface for querying and managing Snipe-IT inventory and assets.

### Features

#### 1. Terminal Interface
- Formatted tables with color-coded status and assignments using Rich.
- Status tables for connection checks and response latency.
- Progress indicators during network requests.

#### 2. Configuration System
- **Single Template (`example-config.py`)**: General configuration template with generic placeholders for any Snipe-IT deployment.
- **Local User Configuration (`config.py`)**: Users copy `example-config.py` to `config.py` for local settings. This file is excluded from Git commits via `.gitignore`.
- **Development Profile (`dev-config.py`)**: Support for local testing configurations without committing credentials.
- **Environment Variables**: Full fallback support for `SNIPEIT_URL` and `SNIPEIT_API_TOKEN`.

#### 3. Commands
- `snipeit test auth`: Tests connectivity, response time, and API credentials.
- `snipeit asset list`: Queries hardware assets with pagination (`--limit`, `--offset`) and text filtering (`--search`).
- `snipeit user me`: Displays account details for the authenticated user.

#### 4. Security
- Exclusion rules in `.gitignore` covering `.cred`, `.env`, and local config files.
- Error handlers structured to prevent printing API tokens in terminal output.

#### 5. Packaging and CI
- PEP 621 metadata defined in `pyproject.toml`.
- GitHub Actions CI workflow covering Python 3.10 through 3.14.
- `CONTRIBUTING.md` and MIT License included.

---

## AI Assistance Disclosure

This project was developed by Lisa Jacklin-Wyatt with pair-programming assistance from Google DeepMind's agentic AI coding assistant (Antigravity).

AI assistance included:
- CLI command structure and terminal formatting using Typer and Rich.
- Single and bulk asset management workflows (create, update, bulk-add, bulk-update, template).
- In-memory metadata caching and model/status/location name-or-ID resolution.
- Configuration loading design and credential fallback handling.
- Security auditing of error messages to avoid credential exposure.
- Packaging configuration, unit test suite, and GitHub Actions CI workflow setup.

All commands and API calls were reviewed and validated against active Snipe-IT instances.
