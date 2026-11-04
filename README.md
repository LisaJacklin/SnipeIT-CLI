# SnipeIT-CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/LisaJacklin/SnipeIT-CLI/actions/workflows/ci.yml/badge.svg)](https://github.com/LisaJacklin/SnipeIT-CLI/actions)

A command-line interface for querying and managing Snipe-IT inventory and assets seamlessly.

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

# Test against a specific URL
snipeit test auth --url https://snipeit.example.com
```

---

### Hardware Asset Management

#### 1. List Assets
```bash
# List first 10 assets
snipeit asset list

# Paginate and search by keyword
snipeit asset list --limit 20 --offset 10 --search "MacBook"
```

#### 2. Get Asset Details
Retrieve full asset details by Asset Tag, database ID, or Hostname:
```bash
snipeit asset get ACEP-00001
snipeit asset get 12
snipeit asset get macbook-lab-01

# Print raw JSON response
snipeit asset get ACEP-00001 --raw
```

#### 3. Create / Add Single Asset (`create`, `add`)
Add a new hardware asset interactively or non-interactively. Model, status, and location can be specified by ID or human-readable name!

```bash
# Interactive mode (guided walkthrough with tables for available models and statuses)
snipeit asset create
# or using alias:
snipeit asset add

# Non-interactive mode with flags
snipeit asset create \
  --tag ACEP-00101 \
  --model-id "MacBook Pro 16" \
  --status-id "Ready to Deploy" \
  --name "mac-eng-01" \
  --serial "C02G123456" \
  --location-id "Headquarters" \
  --notes "Engineering workstation" \
  -y
```

#### 4. Update / Edit Single Asset (`update`, `edit`)
Update an asset by Tag, ID, or Hostname.
- When run interactively without flags, it prompts you for each field with the **current value pre-populated as default**.
- Shows a color-coded **before/after diff table** before applying changes via `PATCH`.

```bash
# Interactive update (displays current values and prompts for changes)
snipeit asset update ACEP-00101
# or using alias:
snipeit asset edit ACEP-00101

# Update specific fields non-interactively
snipeit asset update ACEP-00101 \
  --status-id "Archived" \
  --location-id "Storage Room" \
  --notes "Decommissioned after hardware audit" \
  -y
```

#### 5. Bulk Add Assets (`bulk-add`, `bulk-create`)
Import and create assets in bulk from a CSV or JSON file. Metadata (models, statuses, locations) is cached in memory to optimize API efficiency.

```bash
# Preview and validate rows with --dry-run (no assets created)
snipeit asset bulk-add --file new_laptops.csv --dry-run

# Execute bulk creation
snipeit asset bulk-add --file new_laptops.csv
# or using alias:
snipeit asset bulk-create --file new_laptops.csv -y

# Bulk create from a JSON file
snipeit asset bulk-add --file assets.json -y
```

#### 6. Bulk Update Assets (`bulk-update`)
Update multiple assets in two flexible ways:

**Method A: By CSV / JSON File**
```bash
# Preview updates from spreadsheet
snipeit asset bulk-update --file audit_updates.csv --dry-run

# Apply batch updates from spreadsheet
snipeit asset bulk-update --file audit_updates.csv -y
```

**Method B: By Asset Tags / IDs from the Command Line**
```bash
# Update multiple assets at once with common attributes
snipeit asset bulk-update ACEP-00101 ACEP-00102 ACEP-00103 \
  --status-id "Ready to Deploy" \
  --location-id "Headquarters" \
  --notes "Audited and verified" \
  -y

# Using comma-separated --tags flag
snipeit asset bulk-update --tags "ACEP-00101,ACEP-00102" --status-id "Archived" -y
```

#### 7. Generate CSV Templates (`template`)
Generate starter CSV templates with headers and sample rows for bulk import or bulk updating:

```bash
# Output bulk add template to terminal
snipeit asset template add

# Save bulk add template directly to a file
snipeit asset template add -o assets_add_template.csv

# Save bulk update template to a file
snipeit asset template update -o assets_update_template.csv
```

---

### User Management
```bash
# View account details for the authenticated user
snipeit user me
```

---

## CSV File Formats

### Bulk Add CSV Format
Supported column headers (case-insensitive, spaces or underscores):
- `asset_tag` (optional; leave empty for Snipe-IT auto-generation)
- `model` or `model_id` (**required**; numeric ID or exact/partial model name)
- `status` or `status_id` (**required**; numeric ID or status name)
- `name` or `hostname` (optional)
- `serial` or `serial_number` (optional)
- `location` or `location_id` (optional; numeric ID or location name)
- `notes` (optional)
- `order_number` (optional)
- `purchase_date` (optional; `YYYY-MM-DD`)
- `purchase_cost` (optional)

```csv
asset_tag,model,status,name,serial,location,notes,order_number,purchase_date,purchase_cost
ACEP-00101,MacBook Pro 16,Ready to Deploy,macbook-lab-01,C02G123456,Headquarters,Assigned to IT,PO-98765,2026-01-15,2499.00
ACEP-00102,Dell Latitude 7420,Pending,dell-lab-02,8XYZ123,Headquarters,Setup pending,PO-98766,2026-02-01,1399.00
```

### Bulk Update CSV Format
Include an identifier column (`asset_tag`, `id`, or `name`) plus any attributes you wish to change:

```csv
asset_tag,status,location,notes
ACEP-00101,Archived,Storage Room,Decommissioned after hardware audit
ACEP-00102,Ready to Deploy,Headquarters,Re-imaged and verified
```

---

## Project Structure

- [`snipeit.py`](snipeit.py) - Main CLI implementation.
- [`tests/test_snipeit.py`](tests/test_snipeit.py) - Unit test suite.
- [`example-config.py`](example-config.py) - Configuration template.
- [`pyproject.toml`](pyproject.toml) - Build configuration and package metadata.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) - Contribution guidelines.
- [`RELEASE_NOTES.md`](RELEASE_NOTES.md) - Release notes and version history.

---

## AI Assistance Disclosure

This project was developed by Lisa Jacklin-Wyatt with pair-programming assistance from Google DeepMind's agentic AI coding assistant (Antigravity).

AI assistance included:
- CLI command structure and terminal output formatting using Typer and Rich.
- Single and bulk asset management workflows (create, update, bulk-add, bulk-update, template).
- In-memory metadata caching and model/status/location name-or-ID resolution.
- Configuration loading architecture and profile fallback logic.
- Security auditing of error handling to prevent API token exposure.
- Comprehensive unit test suite and GitHub Actions CI matrix.

All API interactions and commands were reviewed and tested against live Snipe-IT instances.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.