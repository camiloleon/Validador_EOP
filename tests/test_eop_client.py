from __future__ import annotations

import os

from src.validador_eop.eop_client import submit_to_eop


def test_submit_simulated_mode(monkeypatch) -> None:
    monkeypatch.delenv("EOP_API_URL", raising=False)
    result = submit_to_eop("tecnicos", "a,b\n1,2\n")
    assert result.mode == "simulated"
    assert result.accepted is True
    assert result.external_id.startswith("SIM-")


def test_submit_real_mode_with_mock(monkeypatch) -> None:
    monkeypatch.setenv("EOP_API_URL", "https://fake-eop.local/ingest")
    monkeypatch.setenv("EOP_API_KEY", "token")

    class DummyResponse:
        def __init__(self) -> None:
            self.content = b'{"accepted": true, "message": "ok", "external_id": "EXT-1"}'

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"accepted": True, "message": "ok", "external_id": "EXT-1"}

    class DummyClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url: str, json: dict, headers: dict):
            assert url == "https://fake-eop.local/ingest"
            assert headers["Authorization"] == "Bearer token"
            assert json["template"] == "tecnicos"
            return DummyResponse()

    monkeypatch.setattr("src.validador_eop.eop_client.httpx.Client", DummyClient)

    result = submit_to_eop("tecnicos", "a,b\n1,2\n")
    assert result.mode == "real"
    assert result.accepted is True
    assert result.external_id == "EXT-1"
    assert result.message == "ok"
