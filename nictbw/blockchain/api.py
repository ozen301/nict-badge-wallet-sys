import os
from .utils import open_session, get_jwt_token
from typing import Any, Optional

class ChainClient:
    def __init__(self, base_fqdn: Optional[str] = None, timeout: int = 15):
        self.base_url = (
            f"https://{(base_fqdn or os.getenv('BLOCKCHAIN_BASE_FQDN'))}".rstrip("/")
        )
        if not self.base_url or self.base_url == "https://None":
            raise ValueError("Environment variable 'BLOCKCHAIN_BASE_FQDN' is not set")

        session_info = open_session()
        if not session_info:
            raise ValueError(
                "open_session() returned None, expected (session, csrf_token)"
            )
        self.session, self.csrf = session_info
        self.jwt = get_jwt_token(self.session)
        self.timeout = timeout

    @property
    def public_headers(self):
        return {"Accept": "application/json"}

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.jwt}", "Accept": "application/json"}

    @property
    def auth_csrf_headers(self):
        return {**self.auth_headers, "X-CSRFTOKEN": self.csrf}

    def _get(self, headers: dict, path: str) -> Any:
        r = self.session.get(
            f"{self.base_url}{path}", headers=headers, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    # API
    def get_user_info(self) -> Any:
        return self._get(self.public_headers, "/api/v1/user/info")

    def get_user_nfts(self, username: str) -> Any:
        return self._get(self.auth_headers, f"/api/v1/admin/nfts/info/{username}")
