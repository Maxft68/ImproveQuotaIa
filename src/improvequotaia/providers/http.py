"""Requêtes HTTP JSON communes aux modules (bibliothèque standard uniquement)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from ..i18n import t
from .base import ProviderError

USER_AGENT = "improvequotaia"


class HttpError(ProviderError):
    def __init__(self, code: int, body: str = ""):
        super().__init__(t("err.http", code=code))
        self.code, self.body = code, body


def request_json(url: str, headers: Optional[dict] = None, body: Optional[dict] = None,
                 method: Optional[str] = None, timeout: float = 15):
    data = None if body is None else json.dumps(body).encode("utf-8")
    all_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    all_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=all_headers, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            text = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            text = ""
        raise HttpError(e.code, text) from e
    except urllib.error.URLError as e:
        raise ProviderError(t("err.network", reason=e.reason)) from e
    except (TimeoutError, ValueError) as e:
        raise ProviderError(t("err.invalid_response", detail=e)) from e
