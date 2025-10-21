from __future__ import annotations

import pytest

from backend.services import retrieval_target as rtarget


def test_invalid_target_backend_raises(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "doesnotexist")
    with pytest.raises(ValueError):
        rtarget.get_target_adapter()

