import os
import requests

class UcampusClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("UCAMPUS_BASE_URL")
        self.token = os.getenv("UCAMPUS_TOKEN")
        self.timeout = int(os.getenv("UCAMPUS_TIMEOUT_S", "30"))

        if not self.base_url or not self.token:
            raise RuntimeError("Faltan UCAMPUS_BASE_URL / UCAMPUS_TOKEN en .env")

    def get(self, path: str, params: dict | None = None) -> dict:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()
