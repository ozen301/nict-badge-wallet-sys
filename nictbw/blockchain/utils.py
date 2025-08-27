import os
import logging
import requests
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

def load_environment():
    load_dotenv()

def open_session():
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
            for i, (name, value) in enumerate(cookies.items()):
                logger.debug(f"Cookie #{i}\t{name}: {value}")
        else:
            raise RuntimeError("Server did not return any cookies")

        csrf_token = response.cookies.get("csrftoken")
        if csrf_token:
            logger.debug(f"CSRF token: {csrf_token}")
            return session, csrf_token
        else:
            raise RuntimeError("Server did not return a CSRF token")

    except Exception as e:
        logger.critical(f"Error occurred while starting session: {e}")

def get_jwt_token(session):
    # Get login credentials from environment variables
    credential = {
        "username": os.environ.get("SERVER_MANAGEMENT_USERNAME"),
        "password": os.environ.get("SERVER_MANAGEMENT_PASSWORD"),
    }
    logger.debug(f"Login with credentials: {credential}")

    # Get JWT token
    fqdn = os.environ.get("BLOCKCHAIN_BASE_FQDN")
    if not fqdn:
        raise RuntimeError("Environment variable 'BLOCKCHAIN_BASE_FQDN' is not set")
    endpoint = "/api/v1/auth/jwt-token"
    url = "https://" + fqdn + endpoint
    response = session.post(url, json=credential)

    logger.debug(f"Request Header: {response.request.headers}")
    logger.debug(f"Request Body  : {response.request.body}")
    logger.debug(f"Response      : {response.text}")

    jwt_token = response.json()["access"]
    return jwt_token
