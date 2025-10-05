import os
from typing import Optional
from uuid import UUID
import httpx

class MS1Client:
    def __init__(self):
        self.base_url = os.getenv("MS1_BASE_URL", "").rstrip("/")
        self.enabled = os.getenv("MS1_VALIDATE", "false").lower() == "true"
        self.timeout = float(os.getenv("MS1_TIMEOUT", "3"))
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def customer_exists(self, customer_id: UUID) -> bool:
        if not self.enabled:
            return True
        if not self.base_url:
            raise RuntimeError("MS1_BASE_URL not configured")
        url = f"{self.base_url}/customers/{customer_id}"
        try:
            r = self._get_client().get(url)
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                return False
            return False
        except httpx.RequestError as e:
            raise ConnectionError(f"MS1 unavailable: {e}") from e

ms1 = MS1Client()
