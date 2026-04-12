"""
WordPress JWT Token Manager.

Automatically obtains a fresh JWT token before each pipeline execution
to avoid expiration issues. Uses WP_USER and WP_PASSWORD credentials.
"""

import requests
from typing import Optional

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("wordpress.token_manager")


def refresh_wp_token() -> str:
    """
    Obtain a fresh JWT token from WordPress using credentials.
    
    Returns:
        The new JWT token.
        
    Raises:
        RuntimeError: If credentials are missing or token request fails.
    """
    username = Settings.WP_USER
    password = Settings.WP_PASSWORD
    
    if not username or not password:
        raise RuntimeError(
            "WP_USER and WP_PASSWORD must be configured in .env "
            "to auto-refresh WordPress tokens."
        )
    
    token_url = f"{Settings.WP_HOSTING_API_BASE}/wp-json/jwt-auth/v1/token"
    
    try:
        logger.info("[WP-TOKEN] Requesting fresh JWT token from WordPress...")
        resp = requests.post(
            token_url,
            data='{"username": "' + username + '", "password": "' + password.replace('\\', '\\\\').replace('"', '\\"') + '"}',
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; NBESBot/1.0)",
            },
            timeout=15,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            new_token = data.get("token")
            if new_token:
                # Update Settings with the new token
                Settings.WP_HOSTING_JWT_TOKEN = new_token
                logger.info("[WP-TOKEN] Token refreshed successfully")
                return new_token
            else:
                raise RuntimeError("No token in WordPress response")
        else:
            error_detail = resp.text[:300] if resp.text else "No details"
            raise RuntimeError(
                f"WordPress token request failed (HTTP {resp.status_code}): {error_detail}"
            )
            
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Cannot connect to WordPress token endpoint: {e}")


def get_valid_wp_token() -> str:
    """
    Get a valid WordPress JWT token.
    
    Strategy: Always refresh to avoid expiration. This is called
    before each pipeline execution.
    
    Returns:
        Valid JWT token string.
        
    Raises:
        RuntimeError: If token cannot be obtained.
    """
    # Always refresh to guarantee validity
    return refresh_wp_token()
