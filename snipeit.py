#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Filename:    snipeit.py
# Author:      Lisa Jacklin-Wyatt
# Created:     2026-08-31
# Description: CLI suite for querying and managing Snipe-IT inventory.
# -----------------------------------------------------------------------------

import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

import requests
import typer
from rich.console import Console
from rich.table import Table

console = Console()

# Main application and command groups
app = typer.Typer(help="Snipe-IT CLI Suite", no_args_is_help=True)
test_app = typer.Typer(help="Connectivity and testing commands", no_args_is_help=True)
asset_app = typer.Typer(help="Asset management commands", no_args_is_help=True)
user_app = typer.Typer(help="User management commands", no_args_is_help=True)

app.add_typer(test_app, name="test")
app.add_typer(asset_app, name="asset")
app.add_typer(user_app, name="user")

BASE_DIR = Path(__file__).resolve().parent


def get_config() -> tuple[str, str]:
    """
    Resolve Snipe-IT base URL and API token.
    Checks: environment variables, local config files (dev-config.py, config.py),
    and local credential files (dev.cred, prod.cred).
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
# Commands
# =============================================================================

@test_app.command("auth")
def test_auth(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Override Snipe-IT base URL"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Timeout in seconds"),
):
    """
    Test connectivity and verify API credentials against Snipe-IT.
    """
    default_url, token = get_config()
    target_base = url.rstrip("/") if url else default_url
    if target_base and not target_base.endswith("/api/v1"):
        target_base = f"{target_base}/api/v1"

    if not target_base or "your-snipeit-domain.com" in target_base:
        console.print("[red]Error: Snipe-IT URL is not configured. Set it in config.py or SNIPEIT_URL.[/red]")
        raise typer.Exit(1)

    if not token:
        console.print("[red]Error: API token not found. Set it in config.py, dev.cred, or SNIPEIT_API_TOKEN.[/red]")
        raise typer.Exit(1)

    endpoint = f"{target_base}/hardware"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    console.print(f"Connecting to: {endpoint}...")

    try:
        response = requests.get(endpoint, headers=headers, params={"limit": 1}, timeout=timeout)

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
            console.print(f"[yellow]Endpoint not found at {target_base}. Check base URL.[/yellow]")
            raise typer.Exit(1)
        else:
            table.add_row("Auth Status", f"[yellow][WARNING] HTTP {response.status_code}[/yellow]")
            console.print(table)
            raise typer.Exit(1)

    except requests.exceptions.ConnectionError:
        console.print(f"[red]Connection Error: Could not reach {target_base}. Check network or VPN.[/red]")
        raise typer.Exit(1)
    except requests.exceptions.Timeout:
        console.print(f"[red]Timeout: Server took longer than {timeout} seconds to respond.[/red]")
        raise typer.Exit(1)


@asset_app.command("list")
def list_assets(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of assets to display"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Filter by keyword"),
):
    """
    List hardware assets from Snipe-IT.
    """
    base_url, token = get_config()
    if not token or not base_url:
        console.print("[red]Error: Credentials or URL not configured.[/red]")
        raise typer.Exit(1)

    endpoint = f"{base_url}/hardware"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"limit": limit}
    if search:
        params["search"] = search

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
        if response.status_code != 200:
            console.print(f"[red]Failed to fetch assets (HTTP {response.status_code}).[/red]")
            raise typer.Exit(1)

        payload = response.json()
        rows = payload.get("rows", [])
        total = payload.get("total", len(rows))

        table = Table(title=f"Assets ({len(rows)} of {total})")
        table.add_column("ID", justify="right", style="dim")
        table.add_column("Asset Tag", style="green")
        table.add_column("Name")
        table.add_column("Model")
        table.add_column("Status")

        for r in rows:
            table.add_row(
                str(r.get("id", "")),
                r.get("asset_tag") or "-",
                r.get("name") or "-",
                (r.get("model") or {}).get("name", "-"),
                (r.get("status_label") or {}).get("name", "-"),
            )
        console.print(table)
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Network error: {e}[/red]")
        raise typer.Exit(1)


@user_app.command("me")
def user_me():
    """
    Display account details for the authenticated user.
    """
    base_url, token = get_config()
    if not token or not base_url:
        console.print("[red]Error: Credentials or URL not configured.[/red]")
        raise typer.Exit(1)

    endpoint = f"{base_url}/users/me"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
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
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Network error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()