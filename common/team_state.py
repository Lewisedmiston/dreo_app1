"""Shared workspace state helpers for collaborative pages."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from filelock import FileLock, Timeout

from .constants import DATA_ROOT

# File used to persist shared workspace state across Streamlit sessions.
TEAM_STATE_FILE = DATA_ROOT / "team_state.json"
TEAM_STATE_LOCK = TEAM_STATE_FILE.with_suffix(".lock")
LOCK_TIMEOUT = float(os.getenv("DREO_TEAM_LOCK_TIMEOUT", "5"))

TEAM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Default friendly workspace name used when no explicit workspaces exist yet.
DEFAULT_WORKSPACE_NAME = "Main Floor"


def _json_copy(payload: Dict[str, Any] | list[Any] | None) -> Dict[str, Any] | list[Any]:
    """Return a deep JSON-compatible copy of the provided payload."""

    if payload is None:
        return {}
    return json.loads(json.dumps(payload))


def _normalize_feature(feature: str) -> str:
    feature_key = feature.strip().lower().replace(" ", "_")
    if not feature_key:
        raise ValueError("Feature name must be a non-empty string")
    return feature_key


def _normalize_workspace(name: str) -> str:
    cleaned = " ".join(str(name).strip().split())
    if not cleaned:
        raise ValueError("Workspace name must be a non-empty string")
    return cleaned[:60]


def _read_store() -> Dict[str, Dict[str, Any]]:
    if not TEAM_STATE_FILE.exists():
        return {}
    try:
        with FileLock(str(TEAM_STATE_LOCK), timeout=LOCK_TIMEOUT):
            with TEAM_STATE_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                if isinstance(data, dict):
                    return data
    except (json.JSONDecodeError, Timeout):
        # Corrupt/partial state files or lock timeouts should not crash the app.
        pass
    return {}


def _write_store(store: Dict[str, Dict[str, Any]]) -> None:
    TEAM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = TEAM_STATE_FILE.with_suffix(".tmp")
    try:
        with FileLock(str(TEAM_STATE_LOCK), timeout=LOCK_TIMEOUT):
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(store, handle, indent=2, sort_keys=True)
            temp_path.replace(TEAM_STATE_FILE)
    except Timeout:
        # If we cannot acquire the lock, skip the write to avoid corruption.
        pass


def list_workspaces(feature: str) -> list[str]:
    """Return all workspace names for a feature, sorted alphabetically."""

    feature_key = _normalize_feature(feature)
    store = _read_store()
    workspaces = store.get(feature_key, {})
    return sorted(workspaces, key=str.casefold)


def ensure_workspace(feature: str, name: str, *, default: Dict[str, Any] | None = None) -> str:
    """Ensure a workspace exists and return its normalized name."""

    feature_key = _normalize_feature(feature)
    workspace_name = _normalize_workspace(name)
    store = _read_store()
    feature_bucket = store.setdefault(feature_key, {})
    if workspace_name not in feature_bucket:
        feature_bucket[workspace_name] = _json_copy(default) if default else {}
        _write_store(store)
    return workspace_name


def load_workspace(feature: str, name: str, *, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Load a workspace payload, creating it with the default if missing."""

    feature_key = _normalize_feature(feature)
    workspace_name = _normalize_workspace(name)
    store = _read_store()
    payload = store.get(feature_key, {}).get(workspace_name)
    if payload is None:
        ensure_workspace(feature_key, workspace_name, default=default)
        return _json_copy(default)
    return _json_copy(payload)


def save_workspace(feature: str, name: str, payload: Dict[str, Any]) -> None:
    """Persist a workspace payload in the shared state file."""

    feature_key = _normalize_feature(feature)
    workspace_name = _normalize_workspace(name)
    store = _read_store()
    feature_bucket = store.setdefault(feature_key, {})
    feature_bucket[workspace_name] = _json_copy(payload or {})
    _write_store(store)


def delete_workspace(feature: str, name: str) -> None:
    """Remove a workspace from the store if it exists."""

    feature_key = _normalize_feature(feature)
    workspace_name = _normalize_workspace(name)
    store = _read_store()
    feature_bucket = store.get(feature_key)
    if not feature_bucket or workspace_name not in feature_bucket:
        return
    feature_bucket.pop(workspace_name, None)
    if feature_bucket:
        _write_store(store)
        return
    # Drop the feature key entirely if no workspaces remain.
    store.pop(feature_key, None)
    _write_store(store)


__all__ = [
    "DEFAULT_WORKSPACE_NAME",
    "delete_workspace",
    "ensure_workspace",
    "list_workspaces",
    "load_workspace",
    "save_workspace",
]
