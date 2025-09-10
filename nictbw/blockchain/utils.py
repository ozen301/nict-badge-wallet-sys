import os
import logging
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure environment variables from .env are loaded when this module is imported.
load_dotenv()


def open_session():
    """Open a requests session to the blockchain service and fetch CSRF.

    Returns
    -------
    tuple[requests.Session, str]
        The initialized session and CSRF token string.

    Raises
    ------
    RuntimeError
        If ``BLOCKCHAIN_BASE_FQDN`` is not set or the session cannot be
        established, including when the server returns no cookies or a CSRF
        token cannot be retrieved. Any underlying exception is re-raised as a
        ``RuntimeError`` with context.
    """
    fqdn = os.environ.get("BLOCKCHAIN_BASE_FQDN")
    if not fqdn:
        raise RuntimeError("Environment variable 'BLOCKCHAIN_BASE_FQDN' is not set")
    url = "https://" + fqdn

    session = requests.Session()
    try:
        response = session.get(url)
        response.raise_for_status()

        cookies = session.cookies
        if cookies:
            # Do not log cookie values; just count for diagnostics.
            logger.debug(f"Received {len(cookies)} cookies from server")
        else:
            raise RuntimeError("Server did not return any cookies")

        csrf_token = response.cookies.get("csrftoken")
        if csrf_token:
            # Do not log the CSRF token value
            logger.debug("CSRF token acquired")
            return session, csrf_token
        else:
            raise RuntimeError("Server did not return a CSRF token")

    except Exception as e:
        logger.critical(f"Error occurred while starting session: {e}")
        raise RuntimeError(f"Failed to establish session: {e}") from e

def get_jwt_token(session: requests.Session) -> str:
    """Obtain a JWT access token using admin credentials.

    Parameters
    ----------
    session : requests.Session
        A live session for the blockchain service.

    Returns
    -------
    str
        The JWT access token string.

    Raises
    ------
    RuntimeError
        If required environment variables are not set.
    requests.HTTPError
        If the login request fails.
    KeyError, ValueError
        If the response payload does not include an ``"access"`` field or is malformed.
    """
    # Get login credentials from environment variables
    credential = {
        "username": os.environ.get("BLOCKCHAIN_ADMIN_USERNAME"),
        "password": os.environ.get("BLOCKCHAIN_ADMIN_PASSWORD"),
    }
    # Never log raw credentials
    logger.debug("Attempting JWT login with configured admin username")

    # Get JWT token
    fqdn = os.environ.get("BLOCKCHAIN_BASE_FQDN")
    if not fqdn:
        raise RuntimeError("Environment variable 'BLOCKCHAIN_BASE_FQDN' is not set")
    endpoint = "/api/v1/auth/jwt-token"
    url = "https://" + fqdn + endpoint
    response = session.post(url, json=credential)
    response.raise_for_status()

    # Avoid logging headers/body/response as they may contain sensitive data
    logger.debug("JWT token response received (content redacted)")

    jwt_token = response.json()["access"]
    return jwt_token
