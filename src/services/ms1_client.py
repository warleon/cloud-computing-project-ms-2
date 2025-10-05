import os
from typing import Optional
import httpx

class MS1Client:
    def __init__(self):
        self.base_url = os.getenv("MS1_BASE_URL", "").rstrip("/")
        self.enabled = os.getenv("MS1_VALIDATE", "true").lower() == "true"
        self.timeout = float(os.getenv("MS1_TIMEOUT", "3"))
        self._client: Optional[httpx.Client] = None

    def _client_instance(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _looks_like_object_id(self, value: str) -> bool:
        if not isinstance(value, str) or len(value) != 24:
            return False
        try:
            int(value, 16)
            return True
        except Exception:
            return False

    def customer_exists(self, customer_id: str) -> bool:
        if not self.enabled:
            return True
        if not self.base_url:
            raise RuntimeError("MS1_BASE_URL not configured")
        if not self._looks_like_object_id(customer_id):
            return False

        url = f"{self.base_url}/customers/{customer_id}"
        try:
            r = self._client_instance().get(url)
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                return False
            return False
        except httpx.RequestError as e:
            raise ConnectionError(f"MS1 unavailable: {e}") from e

ms1 = MS1Client()
