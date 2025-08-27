import os
from urllib.parse import urljoin
from dotenv import load_dotenv
from .utils import open_session, get_jwt_token
from typing import Any, Optional, Mapping


class ChainClient:
    def __init__(self, base_fqdn: Optional[str] = None, timeout: int = 15):
        load_dotenv()
        fqdn = base_fqdn or os.getenv("BLOCKCHAIN_BASE_FQDN")
        if not fqdn:
            raise ValueError("Environment variable 'BLOCKCHAIN_BASE_FQDN' is not set")

        self.base_url = f"https://{fqdn}".rstrip("/")
        session_info = open_session()
        if not session_info or len(session_info) != 2:
            raise ValueError("open_session() must return (session, csrf_token)")
        self.session, self.csrf = session_info
        self.jwt = get_jwt_token(self.session)
        self.timeout = timeout

    # -------- headers --------
    @property
    def public_headers(self) -> Mapping[str, str]:
        return {"Accept": "application/json"}

    @property
    def auth_headers(self) -> Mapping[str, str]:
        return {"Accept": "application/json", "Authorization": f"Bearer {self.jwt}"}

    @property
    def auth_csrf_headers(self) -> Mapping[str, str]:
        return {**self.auth_headers, "X-CSRFTOKEN": self.csrf}

    # -------- core request --------
    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Any:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        r = self.session.request(
            method=method.upper(),
            url=url,
            headers=headers or self.public_headers,
            params=params,
            json=json,
            data=data,
            timeout=self.timeout,
        )
        r.raise_for_status()
        # If some endpoints return non-JSON (e.g., 204), handle gracefully.
        return r.json() if r.content else None

    # -------- API helpers --------
    def get_user_info(self) -> Any:
        return self._request("GET", "/api/v1/user/info", headers=self.auth_headers)

    def get_user_nfts(self, nft_origin: Optional[str] = None) -> Any:
        params = {"nft_origin": nft_origin} if nft_origin else None
        return self._request(
            "GET",
            "/api/v1/user/nfts/info",
            headers=self.auth_headers,
            params=params,
        )
