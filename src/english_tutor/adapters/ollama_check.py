"""Connection test for the Settings window: is Ollama up, and is the model installed?"""

from __future__ import annotations

import logging
from collections.abc import Collection

import requests

from ..ports import ConnectionResult, ConnectionStatus
from ..settings.model import validate_ollama_url

logger = logging.getLogger(__name__)

CHECK_TIMEOUT_S = 3.0


def model_installed(names: Collection[str], model: str) -> bool:
    """Whether ``model`` is listed; a name without a tag means ``name:latest``."""
    wanted = model if ":" in model else f"{model}:latest"
    return wanted in names or model in names


def check_connection(
    url: str,
    model: str,
    session: requests.Session | None = None,
    timeout_s: float = CHECK_TIMEOUT_S,
) -> ConnectionResult:
    """Ask the server at ``url`` for its models and classify the answer; never raises."""
    error, _warning = validate_ollama_url(url)
    if error is not None:
        return ConnectionResult(ConnectionStatus.BAD_URL, error)
    base = url.strip().rstrip("/")
    http = session if session is not None else requests.Session()
    try:
        response = http.get(f"{base}/api/tags", timeout=timeout_s)
        response.raise_for_status()
        payload = response.json()
        names = {m.get("name", "") for m in payload.get("models") or []}
    except requests.Timeout as exc:  # also covers ConnectTimeout, which is a ConnectionError too
        return ConnectionResult(ConnectionStatus.TIMEOUT, f"No answer from {base}: {exc}")
    except requests.ConnectionError as exc:
        return ConnectionResult(ConnectionStatus.UNREACHABLE, f"Cannot connect to {base}: {exc}")
    except (requests.RequestException, ValueError, AttributeError, TypeError) as exc:
        logger.debug("Unexpected answer from %s: %s", base, exc)
        detail = f"Unexpected answer from {base}: {exc}"
        return ConnectionResult(ConnectionStatus.UNREACHABLE, detail)
    if not model.strip() or not model_installed(names, model.strip()):
        return ConnectionResult(ConnectionStatus.MODEL_MISSING, f"Model {model.strip()} not found")
    return ConnectionResult(ConnectionStatus.OK)
