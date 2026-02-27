import os
from dotenv import load_dotenv
from urllib.parse import urljoin
from typing import Any, Optional, Mapping

from .utils import open_session, get_jwt_token


class ChainClient:
    """Client for interacting with the blockchain service.

    Parameters
    ----------
    base_fqdn : Optional[str]
        Base FQDN for the blockchain API (e.g. ``api.example.com``). If not
        provided, the value is read from the ``BLOCKCHAIN_BASE_FQDN``
        environment variable.
    timeout : int
        Per-request timeout in seconds. Defaults to ``45``.
    """

    def __init__(self, base_fqdn: Optional[str] = None, timeout: int = 45):
        load_dotenv()
        fqdn = base_fqdn or os.getenv("BLOCKCHAIN_BASE_FQDN")
        if not fqdn:
            raise ValueError("Environment variable 'BLOCKCHAIN_BASE_FQDN' is not set")

        self.base_url = f"https://{fqdn}".rstrip("/")
        try:
            self.session, self.csrf = open_session()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ChainClient session: {e}") from e
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
        """Send an HTTP request and normalize the response.

        Parameters
        ----------
        method : str
            HTTP method, e.g. ``"GET"`` or ``"POST"``.
        path : str
            URL path appended to the client's base URL.
        headers : Optional[Mapping[str, str]]
            Request headers. If not provided, public or auth headers are used by callers.
        params : Optional[dict]
            Query parameters to append to the URL.
        json : Optional[dict]
            JSON body for the request.
        data : Optional[dict]
            Form-encoded body for the request.
        files : Optional[dict]
            Files mapping for multipart upload.
        return_in_json : bool
            If ``True``, parse JSON and return Python objects. If ``False``,
            return raw ``bytes``.

        Returns
        -------
        Any
            Parsed JSON response, raw bytes, or ``None`` if the body is empty.

        Raises
        ------
        requests.HTTPError
            If the response status is not successful.
        """
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
    def all_transactions(self) -> list[dict]:
        return self._request(
            "GET",
            "/api/v1/user/transactions",
            headers=self.auth_headers,
        )

    def get_nft_info(
        self, nft_origin: str, data_format: Optional[str] = "binary"
    ) -> Any:
        """
        Retrieve NFTDefinition data by origin.

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
        """Get NFTs owned by a specific user using admin privileges."""
        return self._request(
            "GET",
            f"/api/v1/admin/nfts/info/{username}",
            headers=self.auth_headers,
        )

    def get_sorted_user_nfts(
        self, username: str, sort_key: str = "created_at", reverse: bool = False
    ) -> list[dict]:
        """Return user's NFTs sorted by a specific key."""
        nfts = self.get_user_nfts(username)
        return sorted(nfts, key=lambda x: x.get(sort_key, ""), reverse=reverse)

    def create_nft(
        self,
        app: str,
        name: str,
        file_path: str = os.path.join(os.path.dirname(__file__), "yenpoint_logo.png"),
        recipient_paymail: Optional[str] = None,
        additional_info: Optional[dict] = None,
    ) -> dict:
        """Create a new NFTDefinition via the blockchain API.

        Parameters
        ----------
        app : str
            Application identifier to tag the NFTDefinition.
        name : str
            Human-readable name of the NFTDefinition.
        file_path : str, default: module ``yenpoint_logo.png``
            Path to the file to attach and mint as NFTDefinition content.
        recipient_paymail : Optional[str]
            If provided, transfer the minted NFTDefinition to this paymail.
            If not provided, the NFTDefinition is transferred to the current client user.
        additional_info : Optional[dict]
            Additional metadata to include in the minting request.

        Returns
        -------
        dict
            Response payload in JSON format from the service containing transaction and NFTDefinition info.
        """
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

    def signup_user(
        self,
        username: str,
        email: str,
        password: str,
        profile_pic_filepath: Optional[str] = None,
        group: Optional[str] = None,
    ) -> dict[str, Any]:
        """Sign up a new user via the blockchain API.

        Parameters
        ----------
        username : str
            Desired username for the new user.
        email : str
            Email address for the new user.
        password : str
            Password for the new user.
        profile_pic_filepath : Optional[str]
            Path to a profile picture file to upload. If not provided, no picture is uploaded.
        group : Optional[str]
            User group to assign.

        Returns
        -------
        dict
            Response payload in JSON format from the service containing user info.
        """
        if profile_pic_filepath:
            with open(profile_pic_filepath, "rb") as f:
                response = self._request(
                    "POST",
                    "api/v1/auth/sign-up",
                    data={
                        "username": username,
                        "email": email,
                        "password": password,
                        "group": group,
                    },
                    files={"profile_pic": f} if f else None,
                    headers=self.auth_headers,
                )
        else:
            response = self._request(
                "POST",
                "api/v1/auth/sign-up",
                json={
                    "username": username,
                    "email": email,
                    "password": password,
                    "group": group,
                },
                headers=self.auth_headers,
            )
        return response
