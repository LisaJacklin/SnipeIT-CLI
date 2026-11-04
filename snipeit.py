#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Filename:    snipeit.py
# Author:      Lisa Jacklin-Wyatt
# Created:     2026-08-31
# Description: Streamlined CLI suite for querying and managing Snipe-IT inventory.
# -----------------------------------------------------------------------------
"""
SnipeIT-CLI Architecture Overview:
----------------------------------
1. Tier 1 - Configuration & Credentials (`get_config`):
   Resolves Snipe-IT endpoint and API token from environment variables,
   local config files (dev-config.py, config.py), or credential files (.cred).

2. Tier 2 - HTTP Client & Metadata Cache (`SnipeITClient`):
   Centralizes authenticated REST communication with Snipe-IT, error
   formatting, network exception handling, and lazy-loaded caching for
   taxonomies (models, status labels, locations).

3. Tier 3 - Schema Normalization & Entity Resolution:
   - Header aliases & dictionary normalization for CSV/JSON imports (`normalize_row_dict`).
   - Flexible lookup for IDs, exact names, and substring names (`resolve_id_or_name`).
   - Unified multi-strategy asset resolution across ID, tag, and hostname (`resolve_asset`).

4. Tier 4 - Typer CLI Commands & Interactive Rich Presentation:
   Organized into sub-apps: `test`, `asset`, and `user`. Provides color-coded
   tables, before/after update diffs, interactive prompts, dry-run safety,
   and batch execution tracking.
"""

import csv
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Optional, Union

import requests
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()

__version__ = "0.2.0"

# Main application and sub-command groups
app = typer.Typer(help="Snipe-IT CLI Suite", no_args_is_help=True)
test_app = typer.Typer(help="Connectivity and testing commands", no_args_is_help=True)
asset_app = typer.Typer(help="Asset management commands", no_args_is_help=True)
user_app = typer.Typer(help="User management commands", no_args_is_help=True)

app.add_typer(test_app, name="test")
app.add_typer(asset_app, name="asset")
app.add_typer(user_app, name="user")

BASE_DIR = Path(__file__).resolve().parent


def version_callback(value: bool):
    """Display CLI version and exit."""
    if value:
        console.print(f"SnipeIT-CLI v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show the version and exit."
    )
):
    """
    Snipe-IT CLI Suite for querying and managing Snipe-IT inventory and assets.
    """
    pass


# =============================================================================
# Tier 1: Configuration & Credentials
# =============================================================================

def get_config() -> tuple[str, str]:
    """
    Resolve the Snipe-IT base URL and API token.

    Evaluation Priority:
      1. Environment variables (`SNIPEIT_URL`, `SNIPEIT_API_TOKEN`).
      2. Local configuration files (`dev-config.py`, `config.py`).
      3. Project credential files (`dev.cred`, `prod.cred`, `.cred`).

    Returns:
      tuple[str, str]: Normalized base API URL (ending in /api/v1) and API token.
    """
    url = os.getenv("SNIPEIT_URL", "")
    token = os.getenv("SNIPEIT_API_TOKEN", "")

    # Check local configuration files
    for cfg_name in ("dev-config.py", "config.py"):
        cfg_path = BASE_DIR / cfg_name
        if cfg_path.exists():
            try:
                mod_name = cfg_name.replace("-", "_").replace(".py", "")
                spec = importlib.util.spec_from_file_location(mod_name, cfg_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if not url and hasattr(mod, "snipeit_url"):
                        url = mod.snipeit_url
                    if not token and hasattr(mod, "snipeit_api_token"):
                        token = mod.snipeit_api_token
                    if url and token:
                        break
            except Exception:
                pass

    # Check local credential files if token is still unset
    if not token:
        for cred_name in ("dev.cred", "prod.cred", ".cred"):
            cred_path = BASE_DIR / cred_name
            if cred_path.exists():
                token = cred_path.read_text().strip()
                if token:
                    break

    url = url.rstrip("/")
    if url and not url.endswith("/api/v1"):
        url = f"{url}/api/v1"

    return url, token


# =============================================================================
# Tier 2: HTTP Client & Metadata Cache
# =============================================================================

def fetch_available_models(base_url: str, headers: dict) -> list[dict]:
    """Fetch available hardware models from Snipe-IT."""
    try:
        r = requests.get(f"{base_url}/models", headers=headers, params={"limit": 500}, timeout=10)
        if r.status_code == 200:
            return r.json().get("rows", [])
    except requests.exceptions.RequestException:
        pass
    return []


def fetch_available_statuses(base_url: str, headers: dict) -> list[dict]:
    """Fetch available status labels from Snipe-IT."""
    try:
        r = requests.get(f"{base_url}/statuslabels", headers=headers, params={"limit": 500}, timeout=10)
        if r.status_code == 200:
            return r.json().get("rows", [])
    except requests.exceptions.RequestException:
        pass
    return []


def fetch_available_locations(base_url: str, headers: dict) -> list[dict]:
    """Fetch available locations from Snipe-IT."""
    try:
        r = requests.get(f"{base_url}/locations", headers=headers, params={"limit": 500}, timeout=10)
        if r.status_code == 200:
            return r.json().get("rows", [])
    except requests.exceptions.RequestException:
        pass
    return []


class SnipeITClient:
    """
    Authenticated HTTP client for interacting with the Snipe-IT REST API v1.
    Provides lazy-loaded caching for models, status labels, and locations.
    """

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        default_url, default_token = get_config()
        self.base_url = (base_url or default_url).rstrip("/")
        if self.base_url and not self.base_url.endswith("/api/v1"):
            self.base_url = f"{self.base_url}/api/v1"
        self.token = token or default_token

        if not self.base_url or "your-snipeit-domain.com" in self.base_url:
            console.print("[red]Error: Snipe-IT URL is not configured. Set it in config.py or SNIPEIT_URL.[/red]")
            raise typer.Exit(1)

        if not self.token:
            console.print("[red]Error: API token not found. Set it in config.py, dev.cred, or SNIPEIT_API_TOKEN.[/red]")
            raise typer.Exit(1)

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._models: Optional[list[dict]] = None
        self._statuses: Optional[list[dict]] = None
        self._locations: Optional[list[dict]] = None

    def get(self, endpoint: str, params: Optional[dict] = None, **kwargs) -> requests.Response:
        """Execute an authenticated GET request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = kwargs.pop("timeout", 15)
        try:
            return requests.get(url, headers=self.headers, params=params, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Network error on {endpoint}: {e}[/red]")
            raise typer.Exit(1)

    def post(self, endpoint: str, json: Optional[dict] = None, **kwargs) -> requests.Response:
        """Execute an authenticated POST request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = kwargs.pop("timeout", 15)
        try:
            return requests.post(url, headers=self.headers, json=json, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Network error on {endpoint}: {e}[/red]")
            raise typer.Exit(1)

    def patch(self, endpoint: str, json: Optional[dict] = None, **kwargs) -> requests.Response:
        """Execute an authenticated PATCH request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = kwargs.pop("timeout", 15)
        try:
            return requests.patch(url, headers=self.headers, json=json, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Network error on {endpoint}: {e}[/red]")
            raise typer.Exit(1)

    @property
    def models(self) -> list[dict]:
        """Lazy-loaded cached list of hardware models."""
        if self._models is None:
            self._models = fetch_available_models(self.base_url, self.headers)
        return self._models

    @property
    def statuses(self) -> list[dict]:
        """Lazy-loaded cached list of status labels."""
        if self._statuses is None:
            self._statuses = fetch_available_statuses(self.base_url, self.headers)
        return self._statuses

    @property
    def locations(self) -> list[dict]:
        """Lazy-loaded cached list of locations."""
        if self._locations is None:
            self._locations = fetch_available_locations(self.base_url, self.headers)
        return self._locations

    def resolve_asset(self, identifier: str) -> tuple[Optional[dict], list[dict]]:
        """Look up an asset by ID, tag, or hostname."""
        return resolve_asset(identifier, self.base_url, self.headers)


# =============================================================================
# Tier 3: Schemas, Normalization & Entity Resolution
# =============================================================================

# Standard asset text attributes: (dict_key, prompt_label, table_header)
ASSET_TEXT_FIELDS = [
    ("name", "Hostname / Asset Name", "Hostname / Name"),
    ("serial", "Serial Number", "Serial Number"),
    ("notes", "Notes", "Notes"),
    ("order_number", "Order Number", "Order Number"),
    ("purchase_date", "Purchase Date (YYYY-MM-DD)", "Purchase Date"),
    ("purchase_cost", "Purchase Cost", "Purchase Cost"),
]

# Header alias mappings for CSV and JSON bulk import
HEADER_MAPPING = {
    "tag": "asset_tag",
    "asset_tag": "asset_tag",
    "assettag": "asset_tag",
    "asset tag": "asset_tag",
    "model": "model_id",
    "model_id": "model_id",
    "model id": "model_id",
    "model_name": "model_id",
    "model name": "model_id",
    "status": "status_id",
    "status_id": "status_id",
    "status id": "status_id",
    "status_name": "status_id",
    "status name": "status_id",
    "status_label": "status_id",
    "status label": "status_id",
    "name": "name",
    "hostname": "name",
    "asset_name": "name",
    "asset name": "name",
    "serial": "serial",
    "serial_number": "serial",
    "serial number": "serial",
    "serialno": "serial",
    "notes": "notes",
    "note": "notes",
    "comment": "notes",
    "comments": "notes",
    "order": "order_number",
    "order_number": "order_number",
    "order number": "order_number",
    "po": "order_number",
    "po_number": "order_number",
    "po number": "order_number",
    "purchase_date": "purchase_date",
    "purchasedate": "purchase_date",
    "purchase date": "purchase_date",
    "purchase_cost": "purchase_cost",
    "purchasecost": "purchase_cost",
    "purchase cost": "purchase_cost",
    "cost": "purchase_cost",
    "location": "location_id",
    "location_id": "location_id",
    "location id": "location_id",
    "location_name": "location_id",
    "location name": "location_id",
    "id": "id",
    "asset_id": "id",
    "asset id": "id",
}


def resolve_id_or_name(user_input: Union[str, int, None], items: list[dict]) -> Optional[int]:
    """
    Resolve an integer database ID from flexible user or file input.

    Matching Priority:
      1. Direct integer or numeric string matching an item's ID.
      2. Exact case-insensitive match on item['name'].
      3. Unique substring match on item['name'] (e.g., "Latitude" -> "Dell Latitude 7420").
      4. Fallback integer value if numeric string.

    Returns:
      int: Resolved database ID, or None if unresolved.
    """
    if user_input is None:
        return None
    if isinstance(user_input, int):
        return user_input

    user_input_str = str(user_input).strip()
    if not user_input_str:
        return None

    # Exact match on numeric ID
    if user_input_str.isdigit():
        target_id = int(user_input_str)
        if not items or any(item.get("id") == target_id for item in items):
            return target_id

    # Exact match on name (case-insensitive)
    for item in items:
        if str(item.get("name", "")).strip().lower() == user_input_str.lower():
            return item.get("id")

    # Substring / partial match on name
    matches = [
        item for item in items
        if user_input_str.lower() in str(item.get("name", "")).strip().lower()
    ]
    if len(matches) == 1:
        return matches[0].get("id")

    # Numeric fallback
    if user_input_str.isdigit():
        return int(user_input_str)

    return None


def get_name_by_id(item_id: Optional[int], items: list[dict]) -> str:
    """Retrieve the human-readable name for an item ID, or '-' if None."""
    if item_id is None:
        return "-"
    for item in items:
        if item.get("id") == item_id:
            return item.get("name", str(item_id))
    return str(item_id)


def resolve_asset(identifier: str, base_url: str, headers: dict) -> tuple[Optional[dict], list[dict]]:
    """
    Find an asset by database ID, Asset Tag, or Hostname.

    Lookup Strategy:
      1. Direct query by database ID: GET /hardware/{id}
      2. Direct query by Asset Tag: GET /hardware/bytag/{tag}
      3. Fallback text search: GET /hardware?search={identifier}

    Returns:
      tuple[Optional[dict], list[dict]]: (matched_asset, list_of_ambiguous_matches)
    """
    identifier = identifier.strip()
    if not identifier:
        return None, []

    # 1. Try direct lookup by database ID if numeric
    if identifier.isdigit():
        try:
            r = requests.get(f"{base_url}/hardware/{identifier}", headers=headers, timeout=10)
            if r.status_code == 200:
                res = r.json()
                if isinstance(res, dict) and res.get("id"):
                    return res, []
        except requests.exceptions.RequestException:
            pass

    # 2. Try direct lookup by Asset Tag (/hardware/bytag/{tag})
    try:
        r = requests.get(f"{base_url}/hardware/bytag/{identifier}", headers=headers, timeout=10)
        if r.status_code == 200:
            res = r.json()
            if isinstance(res, dict) and res.get("id"):
                return res, []
    except requests.exceptions.RequestException:
        pass

    # 3. Fallback: Search across asset tags, hostnames (name), and serials
    try:
        r = requests.get(f"{base_url}/hardware", headers=headers, params={"search": identifier}, timeout=15)
        if r.status_code == 200:
            rows = r.json().get("rows", [])
            for row in rows:
                if identifier.lower() in (
                    (row.get("name") or "").strip().lower(),
                    (row.get("asset_tag") or "").strip().lower(),
                ):
                    return row, []
            if len(rows) == 1:
                return rows[0], []
            if len(rows) > 1:
                return None, rows
    except requests.exceptions.RequestException:
        pass

    return None, []


def format_api_error(res_data: dict, response_code: int = 0) -> list[str]:
    """Extract clean error messages from Snipe-IT API responses without leaking tokens."""
    errors = []
    messages = res_data.get("messages")
    if isinstance(messages, dict):
        for field, errs in messages.items():
            if isinstance(errs, list):
                for e in errs:
                    errors.append(f"{field}: {e}")
            else:
                errors.append(f"{field}: {errs}")
    elif isinstance(messages, list):
        for e in messages:
            errors.append(str(e))
    elif messages:
        errors.append(str(messages))
    elif res_data.get("error"):
        errors.append(str(res_data.get("error")))
    elif response_code:
        errors.append(f"HTTP {response_code}")
    return errors or ["Unknown server response"]


def normalize_row_dict(raw_dict: dict) -> dict:
    """Map arbitrary CSV/JSON dictionary keys to canonical Snipe-IT field names."""
    normalized = {}
    for k, v in raw_dict.items():
        if k is None or v is None:
            continue
        cleaned_key = str(k).strip().lower()
        canonical_key = HEADER_MAPPING.get(cleaned_key, cleaned_key)
        val_str = str(v).strip()
        if val_str != "":
            normalized[canonical_key] = val_str
    return normalized


def parse_asset_file(file_path: Path) -> list[dict]:
    """Read a CSV or JSON file and return a list of normalized row dictionaries."""
    if not file_path.exists():
        console.print(f"[red]Error: File '{file_path}' does not exist.[/red]")
        raise typer.Exit(1)

    suffix = file_path.suffix.lower()
    rows = []
    if suffix == ".json":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                items = content if isinstance(content, list) else [content]
                for item in items:
                    if isinstance(item, dict):
                        rows.append(normalize_row_dict(item))
        except Exception as e:
            console.print(f"[red]Failed to parse JSON file: {e}[/red]")
            raise typer.Exit(1)
    else:
        # Default to CSV with Excel UTF-8 BOM tolerance
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cleaned = normalize_row_dict(row)
                    if cleaned:
                        rows.append(cleaned)
        except Exception as e:
            console.print(f"[red]Failed to parse CSV file: {e}[/red]")
            raise typer.Exit(1)

    return rows


def render_batch_results(title: str, results: list[dict], success_verb: str = "processed"):
    """Render a standardized results table and summary counts for bulk operations."""
    table = Table(title=title)
    table.add_column("Ref / ID", justify="right", style="dim")
    table.add_column("Asset Tag", style="green")
    table.add_column("Name")
    table.add_column("Result")
    table.add_column("Details")

    success_count = 0
    fail_count = 0

    for r in results:
        if r.get("status") == "success":
            success_count += 1
            table.add_row(
                str(r.get("ref", "")),
                r.get("tag", "-"),
                r.get("name", "-"),
                f"[green]{r.get('verb', 'OK')}[/green]",
                r.get("details", ""),
            )
        else:
            fail_count += 1
            table.add_row(
                str(r.get("ref", "")),
                r.get("tag", "-"),
                r.get("name", "-"),
                "[red]Failed[/red]",
                r.get("details", ""),
            )

    console.print(table)
    console.print(f"\nSummary: [bold green]{success_count} {success_verb}[/bold green], [bold red]{fail_count} failed[/bold red]")


# =============================================================================
# Tier 4: CLI Commands
# =============================================================================

# -----------------------------------------------------------------------------
# Connectivity Commands
# -----------------------------------------------------------------------------

@test_app.command("auth")
def test_auth(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Override Snipe-IT base URL"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Timeout in seconds"),
):
    """
    Test connectivity and verify API credentials against Snipe-IT.
    """
    # Phase 1: Client initialization
    client = SnipeITClient(base_url=url)
    endpoint = f"{client.base_url}/hardware"

    console.print(f"Connecting to: {endpoint}...")

    # Phase 2: Probe API endpoint
    try:
        response = requests.get(endpoint, headers=client.headers, params={"limit": 1}, timeout=timeout)

        table = Table(title="Snipe-IT Connection Status")
        table.add_column("Property", style="dim")
        table.add_column("Value")
        table.add_row("Endpoint", endpoint)
        table.add_row("HTTP Status", str(response.status_code))
        table.add_row("Latency", f"{response.elapsed.total_seconds():.2f}s")

        if response.status_code == 200:
            total = response.json().get("total", "N/A")
            table.add_row("Auth Status", "[green][OK] Authenticated[/green]")
            table.add_row("Total Assets", str(total))
            console.print(table)
            console.print("[green]Connection successful. API token and URL are valid.[/green]")
        elif response.status_code == 401:
            table.add_row("Auth Status", "[red][FAILED] 401 Unauthorized[/red]")
            console.print(table)
            console.print("[red]Token rejected. Check your token in config.py or dev.cred.[/red]")
            raise typer.Exit(1)
        elif response.status_code == 404:
            table.add_row("Auth Status", "[yellow][FAILED] 404 Not Found[/yellow]")
            console.print(table)
            console.print(f"[yellow]Endpoint not found at {client.base_url}. Check base URL.[/yellow]")
            raise typer.Exit(1)
        else:
            table.add_row("Auth Status", f"[yellow][WARNING] HTTP {response.status_code}[/yellow]")
            console.print(table)
            raise typer.Exit(1)

    except requests.exceptions.ConnectionError:
        console.print(f"[red]Connection Error: Could not reach {client.base_url}. Check network or VPN.[/red]")
        raise typer.Exit(1)
    except requests.exceptions.Timeout:
        console.print(f"[red]Timeout: Server took longer than {timeout} seconds to respond.[/red]")
        raise typer.Exit(1)


# -----------------------------------------------------------------------------
# Asset Commands: Querying
# -----------------------------------------------------------------------------

@asset_app.command("list")
def list_assets(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of assets to display"),
    offset: int = typer.Option(0, "--offset", "-o", help="Record offset for pagination"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Filter by keyword"),
):
    """
    List hardware assets from Snipe-IT.
    """
    # Phase 1: Client initialization
    client = SnipeITClient()

    # Phase 2: Fetch assets with parameters
    params = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search

    response = client.get("hardware", params=params)
    if response.status_code != 200:
        console.print(f"[red]Failed to fetch assets (HTTP {response.status_code}).[/red]")
        raise typer.Exit(1)

    payload = response.json()
    rows = payload.get("rows", [])
    total = payload.get("total", len(rows))

    # Phase 3: Presentation
    table = Table(title=f"Assets ({len(rows)} of {total})")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Asset Tag", style="green")
    table.add_column("Name")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Location")

    for r in rows:
        loc = (r.get("location") or {}).get("name") or (r.get("rtd_location") or {}).get("name") or "-"
        table.add_row(
            str(r.get("id", "")),
            r.get("asset_tag") or "-",
            r.get("name") or "-",
            (r.get("model") or {}).get("name", "-"),
            (r.get("status_label") or {}).get("name", "-"),
            loc,
        )
    console.print(table)


@asset_app.command("get")
def get_asset(
    identifier: str = typer.Argument(..., help="Asset ID, Asset Tag (e.g. ACEP-00001), or Hostname"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Print raw JSON response"),
):
    """
    Retrieve details of an asset by ID, Asset Tag, or Hostname.
    """
    # Phase 1: Client initialization & asset resolution
    client = SnipeITClient()
    asset_data, candidates = client.resolve_asset(identifier)

    # Phase 2: Handle resolution outcomes
    if not asset_data:
        if candidates:
            console.print(f"[yellow]Multiple assets match '{identifier}'. Please specify an exact Asset Tag or ID:[/yellow]")
            table = Table(title="Matching Assets")
            table.add_column("ID", justify="right", style="dim")
            table.add_column("Asset Tag", style="green")
            table.add_column("Hostname / Name")
            table.add_column("Model")
            table.add_column("Status")
            for r in candidates:
                table.add_row(
                    str(r.get("id", "")),
                    r.get("asset_tag") or "-",
                    r.get("name") or "-",
                    (r.get("model") or {}).get("name", "-"),
                    (r.get("status_label") or {}).get("name", "-"),
                )
            console.print(table)
            return

        console.print(f"[red]Error: Asset '{identifier}' not found.[/red]")
        raise typer.Exit(1)

    if raw:
        console.print_json(json.dumps(asset_data))
        return

    # Phase 3: Formatted asset detail card
    tag = asset_data.get("asset_tag") or "N/A"
    table = Table(title=f"Asset Details: {tag}")
    table.add_column("Property", style="dim", width=20)
    table.add_column("Value")

    table.add_row("ID", str(asset_data.get("id", "")))
    table.add_row("Asset Tag", str(tag))
    table.add_row("Hostname / Name", asset_data.get("name") or "-")
    table.add_row("Serial Number", asset_data.get("serial") or "-")
    table.add_row("Model", (asset_data.get("model") or {}).get("name", "-"))
    table.add_row("Category", (asset_data.get("category") or {}).get("name", "-"))
    table.add_row("Status", (asset_data.get("status_label") or {}).get("name", "-"))

    assigned = asset_data.get("assigned_to")
    assigned_str = "Unassigned"
    if assigned and isinstance(assigned, dict):
        assigned_name = assigned.get("name") or ""
        assigned_user = assigned.get("username") or ""
        assigned_str = f"{assigned_name} ({assigned_user})" if assigned_user else assigned_name
    table.add_row("Assigned To", assigned_str or "Unassigned")

    location = (asset_data.get("location") or {}).get("name") or (asset_data.get("rtd_location") or {}).get("name") or "-"
    table.add_row("Location", location)

    if asset_data.get("purchase_date"):
        p_date = asset_data.get("purchase_date")
        table.add_row("Purchase Date", p_date.get("formatted") if isinstance(p_date, dict) else str(p_date))
    if asset_data.get("purchase_cost"):
        table.add_row("Purchase Cost", str(asset_data.get("purchase_cost")))
    if asset_data.get("notes"):
        table.add_row("Notes", str(asset_data.get("notes")))

    console.print(table)


# -----------------------------------------------------------------------------
# Asset Commands: Creation (Single & Bulk)
# -----------------------------------------------------------------------------

@asset_app.command("create")
def create_asset(
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Asset tag (auto-generated by Snipe-IT if omitted)"),
    model_id: Optional[str] = typer.Option(None, "--model-id", "-m", help="Model ID or Model Name"),
    status_id: Optional[str] = typer.Option(None, "--status-id", "-s", help="Status ID or Status Name"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Asset hostname or name"),
    serial: Optional[str] = typer.Option(None, "--serial", help="Serial number"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Notes / comments"),
    order_number: Optional[str] = typer.Option(None, "--order-number", help="Order / PO number"),
    purchase_date: Optional[str] = typer.Option(None, "--purchase-date", help="Purchase date (YYYY-MM-DD)"),
    purchase_cost: Optional[str] = typer.Option(None, "--purchase-cost", help="Purchase cost"),
    location_id: Optional[str] = typer.Option(None, "--location-id", "-l", help="Location ID or Location Name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts and confirmation"),
):
    """
    Create a new hardware asset in Snipe-IT. Interactively prompts for required and optional fields.
    """
    # Phase 1: Client initialization & metadata loading
    client = SnipeITClient()

    # Phase 2: Tag, Model, Status, and Location Resolution
    final_tag = tag
    if not final_tag and not yes:
        prompt_tag = Prompt.ask("Asset Tag [dim](leave blank to auto-generate)[/dim]", default="").strip()
        if prompt_tag:
            final_tag = prompt_tag

    # Required: Model resolution
    final_model_id = resolve_id_or_name(model_id, client.models) if model_id else None
    if final_model_id is None:
        if yes:
            console.print("[red]Error: --model-id is required when running with --yes.[/red]")
            raise typer.Exit(1)
        if client.models:
            table = Table(title="Available Models")
            table.add_column("ID", justify="right", style="dim")
            table.add_column("Name", style="green")
            table.add_column("Category")
            for m in client.models:
                table.add_row(str(m.get("id", "")), m.get("name", "-"), (m.get("category") or {}).get("name", "-"))
            console.print(table)

        while True:
            val = Prompt.ask("[bold]Model ID or Name[/bold] [bold yellow][Required][/bold yellow]").strip()
            resolved = resolve_id_or_name(val, client.models)
            if resolved is not None:
                final_model_id = resolved
                break
            console.print("[red]Invalid Model. Please enter a valid Model ID or Name.[/red]")

    # Required: Status resolution
    final_status_id = resolve_id_or_name(status_id, client.statuses) if status_id else None
    if final_status_id is None:
        if yes:
            console.print("[red]Error: --status-id is required when running with --yes.[/red]")
            raise typer.Exit(1)
        if client.statuses:
            table = Table(title="Available Status Labels")
            table.add_column("ID", justify="right", style="dim")
            table.add_column("Name", style="green")
            table.add_column("Type")
            for s in client.statuses:
                table.add_row(str(s.get("id", "")), s.get("name", "-"), s.get("type", "-"))
            console.print(table)

        while True:
            val = Prompt.ask("[bold]Status ID or Name[/bold] [bold yellow][Required][/bold yellow]").strip()
            resolved = resolve_id_or_name(val, client.statuses)
            if resolved is not None:
                final_status_id = resolved
                break
            console.print("[red]Invalid Status. Please enter a valid Status ID or Name.[/red]")

    # Optional: Location resolution
    final_loc_id = resolve_id_or_name(location_id, client.locations) if location_id else None
    if final_loc_id is None and location_id is None and not yes:
        loc_str = Prompt.ask("Location ID or Name [dim](optional)[/dim]", default="").strip()
        if loc_str:
            final_loc_id = resolve_id_or_name(loc_str, client.locations)

    # Phase 3: Data-driven acquisition of optional text fields
    text_values = {
        "name": name,
        "serial": serial,
        "notes": notes,
        "order_number": order_number,
        "purchase_date": purchase_date,
        "purchase_cost": purchase_cost,
    }
    for field_key, prompt_label, _ in ASSET_TEXT_FIELDS:
        if text_values[field_key] is None:
            val = "" if yes else Prompt.ask(f"{prompt_label} [dim](optional)[/dim]", default="").strip()
            text_values[field_key] = val or None
        else:
            text_values[field_key] = text_values[field_key].strip() or None

    # Construct API payload
    payload = {
        "model_id": final_model_id,
        "status_id": final_status_id,
    }
    if final_tag:
        payload["asset_tag"] = final_tag
    if final_loc_id:
        payload["location_id"] = final_loc_id
    for field_key, val in text_values.items():
        if val:
            payload[field_key] = val

    # Phase 4: Confirmation summary table
    model_label = get_name_by_id(final_model_id, client.models)
    status_label = get_name_by_id(final_status_id, client.statuses)
    loc_label = get_name_by_id(final_loc_id, client.locations) if final_loc_id else "-"

    summary_table = Table(title="Asset Creation Summary")
    summary_table.add_column("Field", style="dim", width=22)
    summary_table.add_column("Value")
    summary_table.add_row("Asset Tag", final_tag if final_tag else "[Auto-generated by Snipe-IT]")
    summary_table.add_row("Model", f"{model_label} (ID: {final_model_id})")
    summary_table.add_row("Status", f"{status_label} (ID: {final_status_id})")
    summary_table.add_row("Location", f"{loc_label} (ID: {final_loc_id})" if final_loc_id else "-")
    for field_key, _, table_label in ASSET_TEXT_FIELDS:
        summary_table.add_row(table_label, text_values.get(field_key) or "-")
    console.print(summary_table)

    if not yes:
        confirmed = Confirm.ask("Push this asset to Snipe-IT?", default=True)
        if not confirmed:
            console.print("[yellow]Asset creation cancelled.[/yellow]")
            return

    # Phase 5: API execution
    response = client.post("hardware", json=payload)
    res_data = response.json() if "application/json" in response.headers.get("content-type", "") else {}

    if response.status_code in (200, 201) and res_data.get("status") == "success":
        console.print("[green][OK] Asset created successfully.[/green]")
        created = res_data.get("payload", {})
        created_id = created.get("id", "")
        created_tag = created.get("asset_tag") or final_tag or "Auto-generated"
        console.print(f"Created Asset ID: [bold]{created_id}[/bold] (Tag: [bold green]{created_tag}[/bold green])")

        created_model = (created.get("model") or {}).get("name", model_label)
        created_status = (created.get("status_label") or {}).get("name", status_label)
        details_table = Table(title=f"Asset Created: {created_tag}")
        details_table.add_column("Property", style="dim", width=20)
        details_table.add_column("Value")
        details_table.add_row("ID", str(created_id))
        details_table.add_row("Asset Tag", str(created_tag))
        details_table.add_row("Hostname / Name", created.get("name") or text_values.get("name") or "-")
        details_table.add_row("Model", created_model)
        details_table.add_row("Status", created_status)
        if created.get("serial") or text_values.get("serial"):
            details_table.add_row("Serial Number", created.get("serial") or text_values.get("serial") or "-")
        if created.get("notes") or text_values.get("notes"):
            details_table.add_row("Notes", created.get("notes") or text_values.get("notes") or "-")
        console.print(details_table)
    else:
        console.print("[red][FAILED] Failed to create asset.[/red]")
        errs = format_api_error(res_data, response.status_code)
        for err in errs:
            console.print(f"  - [red]{err}[/red]")
        raise typer.Exit(1)


@asset_app.command("bulk-add")
def bulk_add_assets(
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to CSV or JSON file containing assets to add"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate assets without sending create requests to Snipe-IT"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation"),
    template: bool = typer.Option(False, "--template", help="Output a sample CSV template for bulk adding"),
):
    """
    Bulk import and create hardware assets from a CSV or JSON file.
    """
    if template:
        asset_template(template_type="add", output=None)
        return

    # Phase 1: Input file acquisition
    if not file:
        if yes:
            console.print("[red]Error: --file is required when running with --yes.[/red]")
            raise typer.Exit(1)
        file_input = Prompt.ask("Path to CSV or JSON file").strip()
        if not file_input:
            console.print("[red]No file specified. Aborting.[/red]")
            raise typer.Exit(1)
        file = Path(file_input)

    rows = parse_asset_file(file)
    if not rows:
        console.print(f"[yellow]No data rows found in '{file}'.[/yellow]")
        return

    # Phase 2: Client initialization & pre-flight validation
    client = SnipeITClient()
    console.print("[dim]Fetching metadata from Snipe-IT...[/dim]")

    valid_items = []
    preview_table = Table(title=f"Bulk Add Preview: {file.name} ({len(rows)} rows)")
    preview_table.add_column("Row", justify="right", style="dim")
    preview_table.add_column("Asset Tag", style="green")
    preview_table.add_column("Hostname / Name")
    preview_table.add_column("Model")
    preview_table.add_column("Status")
    preview_table.add_column("Location")
    preview_table.add_column("Validation")

    for idx, row in enumerate(rows, start=1):
        errors = []
        raw_model = row.get("model_id")
        raw_status = row.get("status_id")
        raw_loc = row.get("location_id")
        tag = row.get("asset_tag", "")
        name_val = row.get("name", "")

        resolved_model = resolve_id_or_name(raw_model, client.models) if raw_model else None
        if not raw_model:
            errors.append("Missing Model")
        elif resolved_model is None:
            errors.append(f"Model '{raw_model}' not found")

        resolved_status = resolve_id_or_name(raw_status, client.statuses) if raw_status else None
        if not raw_status:
            errors.append("Missing Status")
        elif resolved_status is None:
            errors.append(f"Status '{raw_status}' not found")

        resolved_loc = resolve_id_or_name(raw_loc, client.locations) if raw_loc else None
        if raw_loc and resolved_loc is None:
            errors.append(f"Location '{raw_loc}' not found")

        model_disp = get_name_by_id(resolved_model, client.models) if resolved_model else str(raw_model or "-")
        status_disp = get_name_by_id(resolved_status, client.statuses) if resolved_status else str(raw_status or "-")
        loc_disp = get_name_by_id(resolved_loc, client.locations) if resolved_loc else str(raw_loc or "-")

        if errors:
            status_cell = f"[red]{'; '.join(errors)}[/red]"
        else:
            status_cell = "[green]Valid[/green]"
            payload = {
                "model_id": resolved_model,
                "status_id": resolved_status,
            }
            if tag:
                payload["asset_tag"] = tag
            if resolved_loc:
                payload["location_id"] = resolved_loc
            for field_key, _, _ in ASSET_TEXT_FIELDS:
                if row.get(field_key):
                    payload[field_key] = row.get(field_key)

            valid_items.append((idx, tag or "[Auto]", name_val, payload))

        preview_table.add_row(
            str(idx),
            tag or "[dim]Auto[/dim]",
            name_val or "-",
            model_disp,
            status_disp,
            loc_disp,
            status_cell,
        )

    console.print(preview_table)

    num_invalid = len(rows) - len(valid_items)
    console.print(f"Validation summary: [bold green]{len(valid_items)} valid[/bold green], [bold red]{num_invalid} invalid[/bold red]")

    # Phase 3: Simulation or confirmation gate
    if dry_run:
        console.print("[cyan][DRY RUN] Simulation complete. No assets were created in Snipe-IT.[/cyan]")
        return

    if not valid_items:
        console.print("[red]No valid rows to process. Aborting bulk creation.[/red]")
        raise typer.Exit(1)

    if not yes:
        confirmed = Confirm.ask(f"Proceed with creating {len(valid_items)} asset(s) in Snipe-IT?", default=True)
        if not confirmed:
            console.print("[yellow]Bulk creation cancelled.[/yellow]")
            return

    # Phase 4: API execution & result rendering
    console.print(f"\n[bold]Pushing {len(valid_items)} asset(s) to Snipe-IT...[/bold]")
    results = []

    for idx, tag, name_val, payload in valid_items:
        try:
            resp = client.post("hardware", json=payload)
            res_data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            if resp.status_code in (200, 201) and res_data.get("status") == "success":
                created_id = res_data.get("payload", {}).get("id", "")
                created_tag = res_data.get("payload", {}).get("asset_tag", tag)
                results.append({
                    "ref": idx,
                    "tag": created_tag,
                    "name": name_val or "-",
                    "status": "success",
                    "verb": "Created",
                    "details": f"ID: {created_id}",
                })
            else:
                errs = format_api_error(res_data, resp.status_code)
                results.append({
                    "ref": idx,
                    "tag": tag,
                    "name": name_val or "-",
                    "status": "failed",
                    "details": "; ".join(errs),
                })
        except requests.exceptions.RequestException as e:
            results.append({
                "ref": idx,
                "tag": tag,
                "name": name_val or "-",
                "status": "failed",
                "details": f"Network Error: {e}",
            })

    render_batch_results("Bulk Creation Results", results, success_verb="created")


# -----------------------------------------------------------------------------
# Asset Commands: Updating (Single & Bulk)
# -----------------------------------------------------------------------------

@asset_app.command("update")
def update_asset(
    identifier: str = typer.Argument(..., help="Asset ID, Asset Tag (e.g. ACEP-00001), or Hostname to update"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="New asset tag"),
    model_id: Optional[str] = typer.Option(None, "--model-id", "-m", help="New Model ID or Model Name"),
    status_id: Optional[str] = typer.Option(None, "--status-id", "-s", help="New Status ID or Status Name"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New asset hostname or name"),
    serial: Optional[str] = typer.Option(None, "--serial", help="New serial number"),
    notes: Optional[str] = typer.Option(None, "--notes", help="New notes / comments"),
    order_number: Optional[str] = typer.Option(None, "--order-number", help="New order / PO number"),
    purchase_date: Optional[str] = typer.Option(None, "--purchase-date", help="New purchase date (YYYY-MM-DD)"),
    purchase_cost: Optional[str] = typer.Option(None, "--purchase-cost", help="New purchase cost"),
    location_id: Optional[str] = typer.Option(None, "--location-id", "-l", help="New Location ID or Location Name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts and confirmation"),
):
    """
    Update an existing hardware asset in Snipe-IT. Interactively prompts for changes if no flags are passed.
    """
    # Phase 1: Client initialization & target resolution
    client = SnipeITClient()
    asset_data, candidates = client.resolve_asset(identifier)

    if not asset_data:
        if candidates:
            console.print(f"[yellow]Multiple assets match '{identifier}'. Please specify an exact Asset Tag or ID:[/yellow]")
            table = Table(title="Matching Assets")
            table.add_column("ID", justify="right", style="dim")
            table.add_column("Asset Tag", style="green")
            table.add_column("Hostname / Name")
            table.add_column("Model")
            table.add_column("Status")
            for r in candidates:
                table.add_row(
                    str(r.get("id", "")),
                    r.get("asset_tag") or "-",
                    r.get("name") or "-",
                    (r.get("model") or {}).get("name", "-"),
                    (r.get("status_label") or {}).get("name", "-"),
                )
            console.print(table)
            return

        console.print(f"[red]Error: Asset '{identifier}' not found.[/red]")
        raise typer.Exit(1)

    # Phase 2: Extract baseline asset values
    target_id = asset_data.get("id")
    curr_tag = asset_data.get("asset_tag") or ""
    curr_model_obj = asset_data.get("model") or {}
    curr_model_id = curr_model_obj.get("id")
    curr_model_name = curr_model_obj.get("name") or ""
    curr_status_obj = asset_data.get("status_label") or {}
    curr_status_id = curr_status_obj.get("id")
    curr_status_name = curr_status_obj.get("name") or ""
    curr_loc_obj = asset_data.get("location") or asset_data.get("rtd_location") or {}
    curr_loc_id = curr_loc_obj.get("id")
    curr_loc_name = curr_loc_obj.get("name") or ""

    pdate_raw = asset_data.get("purchase_date")
    curr_pdate = pdate_raw.get("date") if isinstance(pdate_raw, dict) else (str(pdate_raw) if pdate_raw else "")

    curr_text_values = {
        "name": asset_data.get("name") or "",
        "serial": asset_data.get("serial") or "",
        "notes": asset_data.get("notes") or "",
        "order_number": asset_data.get("order_number") or "",
        "purchase_date": curr_pdate,
        "purchase_cost": str(asset_data.get("purchase_cost") or ""),
    }

    flag_text_inputs = {
        "name": name,
        "serial": serial,
        "notes": notes,
        "order_number": order_number,
        "purchase_date": purchase_date,
        "purchase_cost": purchase_cost,
    }

    flags_passed = any(
        x is not None for x in [
            tag, model_id, status_id, location_id,
            *flag_text_inputs.values()
        ]
    )

    # Phase 3: Input acquisition (Interactive guided prompts vs CLI flags)
    new_tag = curr_tag
    new_model_id = curr_model_id
    new_status_id = curr_status_id
    new_loc_id = curr_loc_id
    new_text_values = dict(curr_text_values)

    if not flags_passed and not yes:
        console.print(f"[bold cyan]Editing Asset {curr_tag or target_id}[/bold cyan] [dim](Press Enter to keep current value)[/dim]")
        new_tag = Prompt.ask("Asset Tag", default=curr_tag).strip()

        model_input = Prompt.ask("Model ID or Name", default=curr_model_name or str(curr_model_id or "")).strip()
        if model_input != (curr_model_name or str(curr_model_id or "")):
            resolved_m = resolve_id_or_name(model_input, client.models)
            if resolved_m is not None:
                new_model_id = resolved_m
            else:
                console.print(f"[red]Invalid Model '{model_input}'. Keeping current model.[/red]")

        status_input = Prompt.ask("Status ID or Name", default=curr_status_name or str(curr_status_id or "")).strip()
        if status_input != (curr_status_name or str(curr_status_id or "")):
            resolved_s = resolve_id_or_name(status_input, client.statuses)
            if resolved_s is not None:
                new_status_id = resolved_s
            else:
                console.print(f"[red]Invalid Status '{status_input}'. Keeping current status.[/red]")

        loc_input = Prompt.ask("Location ID or Name", default=curr_loc_name or str(curr_loc_id or "")).strip()
        if loc_input != (curr_loc_name or str(curr_loc_id or "")):
            new_loc_id = resolve_id_or_name(loc_input, client.locations) if loc_input else None

        for field_key, prompt_label, _ in ASSET_TEXT_FIELDS:
            new_text_values[field_key] = Prompt.ask(prompt_label, default=curr_text_values[field_key]).strip()
    else:
        if tag is not None:
            new_tag = tag.strip()
        if model_id is not None:
            resolved_m = resolve_id_or_name(model_id, client.models)
            if resolved_m is not None:
                new_model_id = resolved_m
            else:
                console.print(f"[red]Error: Model '{model_id}' not found.[/red]")
                raise typer.Exit(1)
        if status_id is not None:
            resolved_s = resolve_id_or_name(status_id, client.statuses)
            if resolved_s is not None:
                new_status_id = resolved_s
            else:
                console.print(f"[red]Error: Status '{status_id}' not found.[/red]")
                raise typer.Exit(1)
        if location_id is not None:
            resolved_l = resolve_id_or_name(location_id, client.locations)
            if resolved_l is not None:
                new_loc_id = resolved_l
            else:
                console.print(f"[red]Error: Location '{location_id}' not found.[/red]")
                raise typer.Exit(1)

        for field_key, passed_val in flag_text_inputs.items():
            if passed_val is not None:
                new_text_values[field_key] = passed_val.strip()

    # Phase 4: Data-driven diff table generation
    payload = {}
    diff_table = Table(title=f"Proposed Updates for Asset: {curr_tag or target_id}")
    diff_table.add_column("Property", style="dim", width=22)
    diff_table.add_column("Current Value")
    diff_table.add_column("New Value", style="green")

    if new_tag != curr_tag:
        payload["asset_tag"] = new_tag
        diff_table.add_row("Asset Tag", curr_tag or "-", new_tag or "-")

    if new_model_id != curr_model_id:
        payload["model_id"] = new_model_id
        diff_table.add_row("Model", f"{get_name_by_id(curr_model_id, client.models)} (ID: {curr_model_id})", f"{get_name_by_id(new_model_id, client.models)} (ID: {new_model_id})")

    if new_status_id != curr_status_id:
        payload["status_id"] = new_status_id
        diff_table.add_row("Status", f"{get_name_by_id(curr_status_id, client.statuses)} (ID: {curr_status_id})", f"{get_name_by_id(new_status_id, client.statuses)} (ID: {new_status_id})")

    if new_loc_id != curr_loc_id:
        payload["location_id"] = new_loc_id
        diff_table.add_row("Location", f"{get_name_by_id(curr_loc_id, client.locations)} (ID: {curr_loc_id})", f"{get_name_by_id(new_loc_id, client.locations)} (ID: {new_loc_id})")

    for field_key, _, table_label in ASSET_TEXT_FIELDS:
        if new_text_values[field_key] != curr_text_values[field_key]:
            payload[field_key] = new_text_values[field_key]
            diff_table.add_row(table_label, curr_text_values[field_key] or "-", new_text_values[field_key] or "-")

    if not payload:
        console.print("[yellow]No changes detected. Asset was not modified.[/yellow]")
        return

    console.print(diff_table)

    if not yes:
        confirmed = Confirm.ask("Apply these updates to Snipe-IT?", default=True)
        if not confirmed:
            console.print("[yellow]Asset update cancelled.[/yellow]")
            return

    # Phase 5: API execution
    response = client.patch(f"hardware/{target_id}", json=payload)
    res_data = response.json() if "application/json" in response.headers.get("content-type", "") else {}

    if response.status_code in (200, 201) and res_data.get("status") == "success":
        console.print(f"[green][OK] Asset {curr_tag or target_id} updated successfully.[/green]")
    else:
        console.print(f"[red][FAILED] Failed to update asset {curr_tag or target_id}.[/red]")
        errs = format_api_error(res_data, response.status_code)
        for err in errs:
            console.print(f"  - [red]{err}[/red]")
        raise typer.Exit(1)


@asset_app.command("bulk-update")
def bulk_update_assets(
    identifiers: Optional[list[str]] = typer.Argument(None, help="List of Asset Tags, IDs, or Hostnames to update"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to CSV or JSON file containing assets to update"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated list of Asset Tags to update"),
    status_id: Optional[str] = typer.Option(None, "--status-id", "-s", help="New Status ID or Name for all specified targets"),
    model_id: Optional[str] = typer.Option(None, "--model-id", "-m", help="New Model ID or Name for all specified targets"),
    location_id: Optional[str] = typer.Option(None, "--location-id", "-l", help="New Location ID or Name for all specified targets"),
    notes: Optional[str] = typer.Option(None, "--notes", help="New notes for all specified targets"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New hostname/name for all specified targets"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview updates without modifying Snipe-IT"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation"),
):
    """
    Bulk update multiple hardware assets via a CSV/JSON file or a list of Asset Tags.
    """
    # Phase 1: Client initialization & metadata loading
    client = SnipeITClient()
    targets_to_update = []

    # Phase 2: Resolve targets from file or CLI flags
    if file:
        rows = parse_asset_file(file)
        if not rows:
            console.print(f"[yellow]No data rows found in '{file}'.[/yellow]")
            return

        console.print(f"[dim]Resolving {len(rows)} asset(s) from {file.name}...[/dim]")
        for idx, row in enumerate(rows, start=1):
            ident = row.get("id") or row.get("asset_tag") or row.get("name")
            if not ident:
                console.print(f"[yellow]Row {idx}: Missing identifier (id, asset_tag, or name). Skipped.[/yellow]")
                continue

            asset_data, _ = client.resolve_asset(ident)
            if not asset_data:
                console.print(f"[yellow]Row {idx}: Asset '{ident}' not found in Snipe-IT. Skipped.[/yellow]")
                continue

            payload = {}
            desc_parts = []
            for field_key, _, table_label in ASSET_TEXT_FIELDS:
                if field_key in row:
                    payload[field_key] = row[field_key]
                    desc_parts.append(f"{table_label} -> {row[field_key]}")

            if "model_id" in row:
                resolved_m = resolve_id_or_name(row["model_id"], client.models)
                if resolved_m:
                    payload["model_id"] = resolved_m
                    desc_parts.append(f"Model -> {get_name_by_id(resolved_m, client.models)}")

            if "status_id" in row:
                resolved_s = resolve_id_or_name(row["status_id"], client.statuses)
                if resolved_s:
                    payload["status_id"] = resolved_s
                    desc_parts.append(f"Status -> {get_name_by_id(resolved_s, client.statuses)}")

            if "location_id" in row:
                resolved_l = resolve_id_or_name(row["location_id"], client.locations)
                if resolved_l:
                    payload["location_id"] = resolved_l
                    desc_parts.append(f"Location -> {get_name_by_id(resolved_l, client.locations)}")

            if payload:
                targets_to_update.append((
                    asset_data["id"],
                    asset_data.get("asset_tag", ident),
                    asset_data.get("name", "-"),
                    payload,
                    ", ".join(desc_parts),
                ))

    else:
        # Resolve target list from CLI positional arguments and --tags option
        id_list = list(identifiers) if identifiers else []
        if tags:
            id_list.extend([t.strip() for t in tags.split(",") if t.strip()])

        if not id_list:
            console.print("[red]Error: Specify assets via identifiers, --tags, or --file.[/red]")
            raise typer.Exit(1)

        # Build common payload from flags
        common_payload = {}
        desc_parts = []
        if name:
            common_payload["name"] = name
            desc_parts.append(f"Name -> {name}")
        if notes:
            common_payload["notes"] = notes
            desc_parts.append("Notes updated")

        if model_id:
            resolved_m = resolve_id_or_name(model_id, client.models)
            if resolved_m:
                common_payload["model_id"] = resolved_m
                desc_parts.append(f"Model -> {get_name_by_id(resolved_m, client.models)}")
            else:
                console.print(f"[red]Error: Model '{model_id}' not found.[/red]")
                raise typer.Exit(1)

        if status_id:
            resolved_s = resolve_id_or_name(status_id, client.statuses)
            if resolved_s:
                common_payload["status_id"] = resolved_s
                desc_parts.append(f"Status -> {get_name_by_id(resolved_s, client.statuses)}")
            else:
                console.print(f"[red]Error: Status '{status_id}' not found.[/red]")
                raise typer.Exit(1)

        if location_id:
            resolved_l = resolve_id_or_name(location_id, client.locations)
            if resolved_l:
                common_payload["location_id"] = resolved_l
                desc_parts.append(f"Location -> {get_name_by_id(resolved_l, client.locations)}")
            else:
                console.print(f"[red]Error: Location '{location_id}' not found.[/red]")
                raise typer.Exit(1)

        if not common_payload:
            console.print("[red]Error: No update flags specified (use --status-id, --location-id, --notes, etc.).[/red]")
            raise typer.Exit(1)

        console.print(f"[dim]Resolving {len(id_list)} asset(s)...[/dim]")
        for ident in id_list:
            asset_data, _ = client.resolve_asset(ident)
            if not asset_data:
                console.print(f"[yellow]Asset '{ident}' not found in Snipe-IT. Skipped.[/yellow]")
                continue
            targets_to_update.append((
                asset_data["id"],
                asset_data.get("asset_tag", ident),
                asset_data.get("name", "-"),
                common_payload,
                ", ".join(desc_parts),
            ))

    if not targets_to_update:
        console.print("[yellow]No matching assets to update. Aborting.[/yellow]")
        return

    # Phase 3: Preview plan & confirmation gate
    preview_table = Table(title=f"Bulk Update Plan ({len(targets_to_update)} assets)")
    preview_table.add_column("ID", justify="right", style="dim")
    preview_table.add_column("Asset Tag", style="green")
    preview_table.add_column("Current Name")
    preview_table.add_column("Proposed Updates", style="cyan")

    for asset_id, tag, curr_name, _, desc in targets_to_update:
        preview_table.add_row(str(asset_id), tag, curr_name or "-", desc)
    console.print(preview_table)

    if dry_run:
        console.print(f"[cyan][DRY RUN] Simulation complete: {len(targets_to_update)} assets matched. No changes made in Snipe-IT.[/cyan]")
        return

    if not yes:
        confirmed = Confirm.ask(f"Apply updates to {len(targets_to_update)} asset(s) in Snipe-IT?", default=True)
        if not confirmed:
            console.print("[yellow]Bulk update cancelled.[/yellow]")
            return

    # Phase 4: API execution & result rendering
    console.print(f"\n[bold]Updating {len(targets_to_update)} asset(s) in Snipe-IT...[/bold]")
    results = []

    for asset_id, tag, _, payload, _ in targets_to_update:
        try:
            resp = client.patch(f"hardware/{asset_id}", json=payload)
            res_data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            if resp.status_code in (200, 201) and res_data.get("status") == "success":
                results.append({
                    "ref": asset_id,
                    "tag": tag,
                    "name": "-",
                    "status": "success",
                    "verb": "Updated",
                    "details": "Success",
                })
            else:
                errs = format_api_error(res_data, resp.status_code)
                results.append({
                    "ref": asset_id,
                    "tag": tag,
                    "name": "-",
                    "status": "failed",
                    "details": "; ".join(errs),
                })
        except requests.exceptions.RequestException as e:
            results.append({
                "ref": asset_id,
                "tag": tag,
                "name": "-",
                "status": "failed",
                "details": f"Network Error: {e}",
            })

    render_batch_results("Bulk Update Results", results, success_verb="updated")


# -----------------------------------------------------------------------------
# Asset Commands: Template Generator & Aliases
# -----------------------------------------------------------------------------

@asset_app.command("template")
def asset_template(
    template_type: str = typer.Argument("add", help="Template type: 'add' (bulk add) or 'update' (bulk update)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="File path to save the CSV template to"),
):
    """
    Generate a starter CSV template for bulk asset operations.
    """
    if template_type.lower() in ("add", "create"):
        csv_content = (
            "asset_tag,model,status,name,serial,location,notes,order_number,purchase_date,purchase_cost\n"
            "ACEP-00101,MacBook Pro 16,Ready to Deploy,macbook-lab-01,C02G123456,Headquarters,Assigned to IT,PO-98765,2026-01-15,2499.00\n"
            "ACEP-00102,Dell Latitude 7420,Pending,dell-lab-02,8XYZ123,Headquarters,Setup pending,PO-98766,2026-02-01,1399.00\n"
        )
    elif template_type.lower() in ("update", "edit"):
        csv_content = (
            "asset_tag,status,location,notes\n"
            "ACEP-00101,Archived,Storage Room,Decommissioned after hardware audit\n"
            "ACEP-00102,Ready to Deploy,Headquarters,Re-imaged and verified\n"
        )
    else:
        console.print(f"[red]Error: Unknown template type '{template_type}'. Choose 'add' or 'update'.[/red]")
        raise typer.Exit(1)

    if output:
        output.write_text(csv_content, encoding="utf-8")
        console.print(f"[green]CSV template written to {output}[/green]")
    else:
        console.print(csv_content.strip())


# Register ergonomic aliases for asset commands
asset_app.command("add", help="Alias for 'asset create'")(create_asset)
asset_app.command("edit", help="Alias for 'asset update'")(update_asset)
asset_app.command("bulk-create", help="Alias for 'asset bulk-add'")(bulk_add_assets)


# -----------------------------------------------------------------------------
# User Commands
# -----------------------------------------------------------------------------

@user_app.command("me")
def user_me():
    """
    Display account details for the authenticated user.
    """
    client = SnipeITClient()
    response = client.get("users/me")

    if response.status_code == 200:
        data = response.json()
        table = Table(title="User Profile")
        table.add_column("Field", style="dim")
        table.add_column("Value")
        table.add_row("ID", str(data.get("id", "")))
        table.add_row("Name", data.get("name") or "-")
        table.add_row("Username", data.get("username") or "-")
        table.add_row("Email", data.get("email") or "-")
        console.print(table)
    else:
        console.print(f"[yellow]User endpoint returned HTTP {response.status_code}.[/yellow]")


if __name__ == "__main__":
    app()
