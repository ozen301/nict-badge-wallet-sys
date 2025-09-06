import os
from urllib.parse import urljoin
from dotenv import load_dotenv
from .utils import open_session, get_jwt_token
from typing import Any, Optional, Mapping


class ChainClient:
    def __init__(self, base_fqdn: Optional[str] = None, timeout: int = 45):
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
        files: Optional[dict] = None,
        return_in_json: bool = True,
    ) -> Any:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        r = self.session.request(
            method=method.upper(),
            url=url,
            headers=headers or self.public_headers,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=self.timeout,
        )
        r.raise_for_status()
        if not return_in_json:
            return r.content
        return r.json() if r.content else None

    # -------- API callers --------
    @property
    def info(self) -> dict:
        return self._request("GET", "/api/v1/user/info", headers=self.auth_headers)

    @property
    def balance(self) -> dict:
        return self._request(
            "GET",
            "/api/v1/user/wallet/balance",
            headers=self.auth_headers,
        )

    @property
    def nfts(self) -> list[dict]:
        return self._request(
            "GET",
            "/api/v1/user/nfts/info",
            headers=self.auth_headers,
        )

    @property
    def transactions(self) -> list[dict]:
        return self._request(
            "GET",
            "/api/v1/user/transactions",
            headers=self.auth_headers,
        )

    def get_nft_info(
        self, nft_origin: str, data_format: Optional[str] = "binary"
    ) -> dict:
        """
        Retrieve NFT data by origin.

        data_format: "binary" (default) or "base64".
        """
        return_in_json = False if data_format == "binary" else True
        return self._request(
            "GET",
            f"/api/v1/admin/nft/data/{nft_origin}",
            headers=self.auth_headers,
            params={"data_format": data_format},
            return_in_json=return_in_json,
        )

    def get_user_nfts(self, username: str) -> list[dict]:
        # Get NFTs owned by a specific user using admin privileges.
        return self._request(
            "GET",
            f"/api/v1/admin/nfts/info/{username}",
            headers=self.auth_headers,
        )

    def create_nft(
        self,
        app: str,
        name: str,
        file_path: str = os.path.join(os.path.dirname(__file__), "yenpoint_logo.png"),
        recipient_paymail: Optional[str] = None,
        additional_info: Optional[dict] = None,
    ) -> dict:
        with open(file_path, "rb") as f:
            response = self._request(
                "POST",
                "api/v1/nft/create",
                data={
                    "app": app,
                    "name": name,
                    "recipient_paymail": recipient_paymail,
                    "additional_info": additional_info,
                },
                files={"file": f},
                headers=self.auth_headers,
            )
        return response
