import requests

from shared.config import UcampusCfg


class UcampusClient:
    def __init__(self, cfg: UcampusCfg) -> None:
        if not cfg.base_url or not cfg.token:
            raise RuntimeError("Falta configuración o token de Ucampus")

        self.base_url = cfg.base_url
        self.token = cfg.token
        self.timeout = cfg.timeout_s

    def get(self, path: str, params: dict | None = None) -> dict:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()
