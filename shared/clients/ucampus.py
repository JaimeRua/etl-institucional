import os
import requests


class UcampusClient:
    def __init__(self) -> None:
        base_url = os.getenv("UCAMPUS_BASE_URL")
        token = os.getenv("UCAMPUS_TOKEN")
        timeout_s = os.getenv("UCAMPUS_TIMEOUT_S", "30")

        if not base_url or not token:
            raise RuntimeError("Faltan UCAMPUS_BASE_URL / UCAMPUS_TOKEN en .env")

        self.base_url: str = base_url
        self.token: str = token
        self.timeout: int = int(timeout_s)

    def get(self, path: str, params: dict | None = None) -> dict:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()
