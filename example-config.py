# -----------------------------------------------------------------------------
# Filename:    example-config.py
# Author:      Lisa Jacklin-Wyatt
# Description: Configuration template for SnipeIT-CLI.
#
# Instructions:
#   1. Copy this file to 'config.py':
#        cp example-config.py config.py
#   2. Enter your Snipe-IT server URL and personal API token below.
#   3. 'config.py' is ignored by Git to prevent committing your credentials.
# -----------------------------------------------------------------------------

import os
from pathlib import Path

# Project root directory
BASE_DIR = Path(__file__).resolve().parent

# Set your Snipe-IT server base URL (no trailing slash)
# Example: "https://snipeit.example.com"
snipeit_url = os.getenv("SNIPEIT_URL", "https://your-snipeit-domain.com")

# Optional path to a token file, or set the SNIPEIT_API_TOKEN environment variable
cred_file = BASE_DIR / "dev.cred"


def get_api_token() -> str:
    """
    Look for an API token in environment variables, then in a credential file.
    Returns an empty string if neither is found.
    """
    # 1. Check environment variable
    token_env = os.getenv("SNIPEIT_API_TOKEN") or os.getenv("snipeit_api_token")
    if token_env:
        return token_env.strip()

    # 2. Check local credential file
    if cred_file.exists():
        token = cred_file.read_text().strip()
        if token:
            return token

    return ""


# API token for authenticating requests
snipeit_api_token = get_api_token()

