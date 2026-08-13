from starlette.testclient import TestClient

from app import main
from tests.conftest import API_KEY_HEADER


class _StubGraph:
    """Stands in for the compiled LangGraph. Replaces the whole object rather
    than patching .ainvoke, since CompiledStateGraph does not accept setattr."""

    async def ainvoke(self, state: dict) -> dict:
        return {
            "sanitized_prompt": "La password es [REDACTED].",
            "risk_score": 9.8,
            "pii_detected": True,
        }


def test_pii_detected_is_persisted_when_analyzer_flags_pii(monkeypatch):
    """Regression test for a bug that shipped silently: pii_detected was derived
    from a non-existent 'pii_entities' key, so every audit row was written with
    pii_detected=False even when the analyzer flagged PII."""
    captured: dict = {}

    async def fake_persist(log_data: dict) -> None:
        captured.update(log_data)

    monkeypatch.setattr(main, "security_audit_graph", _StubGraph())
    monkeypatch.setattr(main, "persist_audit_log_task", fake_persist)

    with TestClient(main.app) as client:
        response = client.post(
            "/v1/security/scan",
            json={"user_id": "emp_992", "original_prompt": "La password es hunter2."},
            headers=API_KEY_HEADER,
        )

    assert response.status_code == 200
    assert response.json()["pii_detected"] is True

    # Lo que realmente importa: el flag que se persiste en PostgreSQL.
    # TestClient corre las BackgroundTasks antes de devolver la respuesta.
    assert captured["pii_detected"] is True
    assert captured["risk_score"] == 9.8
    assert captured["sanitized_prompt"] == "La password es [REDACTED]."
