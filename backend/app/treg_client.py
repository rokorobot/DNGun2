"""Thin client for the treg.to tool registry (https://github.com/rokorobot/treg).

Relays one catalog call: `{METHOD} {base}/call/{endpoint_id}` with the
`X-Treg-Token` header. treg injects the provider credential server-side and
bills the team balance; the settled charge comes back in `X-Treg-Cost-Micro`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://treg.to"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Minimal .env reader (no dependency): sets only variables not already in the environment."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip().removeprefix("export "), value.strip().strip("'\""))


class TregError(RuntimeError):
    def __init__(self, endpoint_id: str, status: int | None, message: str):
        super().__init__(f"treg {endpoint_id}: HTTP {status}: {message}")
        self.endpoint_id = endpoint_id
        self.status = status


@dataclass
class TregClient:
    token: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 60.0
    spent_micro: int = field(default=0, init=False)
    calls: int = field(default=0, init=False)

    @classmethod
    def from_env(cls) -> "TregClient":
        """TREG_TOKEN / TREG_URL from the environment, falling back to the repo-root .env."""
        load_env_file()
        token = os.environ.get("TREG_TOKEN")
        if not token:
            raise TregError("-", None, "TREG_TOKEN is not set")
        return cls(token=token, base_url=os.environ.get("TREG_URL", DEFAULT_BASE_URL))

    @property
    def spent_usd(self) -> float:
        return self.spent_micro / 1_000_000

    def call(
        self,
        endpoint_id: str,
        *,
        method: str = "GET",
        query: dict[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}/call/{endpoint_id}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {"X-Treg-Token": self.token, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self._record_cost(response.headers)
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            self._record_cost(error.headers)
            raise TregError(endpoint_id, error.code, _error_message(error)) from None
        except urllib.error.URLError as error:
            raise TregError(endpoint_id, None, str(error.reason)) from None
        except (TimeoutError, OSError) as error:
            raise TregError(endpoint_id, None, f"network error: {error}") from None
        try:
            return json.loads(raw) if raw else None
        except json.JSONDecodeError:
            raise TregError(endpoint_id, 200, f"non-JSON response: {raw[:200]}") from None

    def _record_cost(self, headers: Any) -> None:
        self.calls += 1
        cost = headers.get("X-Treg-Cost-Micro") if headers else None
        if cost:
            try:
                self.spent_micro += int(float(cost))
            except ValueError:
                pass


def _error_message(error: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except Exception:
        return error.reason or "request failed"
    if error.code == 402 and isinstance(payload, dict):
        return f"out of balance — top up at {payload.get('topup_url', 'https://treg.to')}"
    if isinstance(payload, dict):
        return str(payload.get("detail") or payload.get("error") or payload)[:300]
    return str(payload)[:300]
