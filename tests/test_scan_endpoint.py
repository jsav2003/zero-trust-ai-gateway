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


def test_non_ascii_api_key_is_rejected_with_401():
    """secrets.compare_digest solo acepta str ASCII, y Starlette decodifica los
    headers como latin-1: sin encodear ambos operandos, una clave con bytes >127
    reventaba con TypeError y salia como 500 en vez de 401."""
    # Se manda como bytes crudos: un str no-ASCII lo rechaza el cliente HTTP antes
    # de salir, asi que no llegaria nunca al server.
    non_ascii_key = "café".encode("latin-1")

    # raise_server_exceptions=False para que una regresion se vea como 500 != 401
    # en vez de un traceback crudo.
    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/security/scan",
            json={"user_id": "emp_992", "original_prompt": "hola"},
            headers={"X-API-Key": non_ascii_key},
        )

    assert response.status_code == 401
