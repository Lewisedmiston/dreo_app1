from __future__ import annotations

from pathlib import Path

import pytest

from common import team_state


def _set_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store_path = tmp_path / "team_state.json"
    monkeypatch.setattr(team_state, "TEAM_STATE_FILE", store_path)
    return store_path


def test_workspace_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_store(tmp_path, monkeypatch)

    default_payload = {"draft": {"a": 1}, "last_submitted": {"a": 2}}
    name = team_state.ensure_workspace("inventory", "Line Crew", default=default_payload)

    loaded = team_state.load_workspace("inventory", name)
    assert loaded == default_payload

    updated_payload = {"draft": {"b": 4}, "last_submitted": {"b": 8}}
    team_state.save_workspace("inventory", name, updated_payload)

    roundtrip = team_state.load_workspace("inventory", name)
    assert roundtrip == updated_payload


def test_list_and_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_store(tmp_path, monkeypatch)

    team_state.ensure_workspace("ordering", "Beta Team")
    team_state.ensure_workspace("ordering", " alpha  shift ")

    workspaces = team_state.list_workspaces("ordering")
    assert workspaces == ["alpha shift", "Beta Team"]

    team_state.delete_workspace("ordering", "Beta Team")
    remaining = team_state.list_workspaces("ordering")
    assert remaining == ["alpha shift"]

    team_state.delete_workspace("ordering", "alpha shift")
    assert team_state.list_workspaces("ordering") == []
