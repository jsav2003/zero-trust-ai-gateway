import pytest
from langgraph.graph import END

from app.security_audit.graph import routing_logic


def _state(pii_detected: bool, risk_score: float) -> dict:
    return {
        "original_prompt": "irrelevante para el enrutamiento",
        "sanitized_prompt": "",
        "risk_score": risk_score,
        "pii_detected": pii_detected,
    }


@pytest.mark.parametrize(
    "pii_detected, risk_score",
    [
        (True, 0.0),   # PII sola alcanza, aunque el riesgo sea nulo
        (False, 9.0),  # riesgo alto solo alcanza, aunque no haya PII
    ],
)
def test_routes_to_sanitizer_when_flagged(pii_detected: bool, risk_score: float):
    assert routing_logic(_state(pii_detected, risk_score)) == "sanitizer_node"


@pytest.mark.parametrize(
    "pii_detected, risk_score",
    [
        (False, 1.0),  # texto inofensivo
        (False, 5.0),  # borde exacto: la condicion es > 5.0, no >= 5.0
    ],
)
def test_ends_when_clean(pii_detected: bool, risk_score: float):
    assert routing_logic(_state(pii_detected, risk_score)) == END
