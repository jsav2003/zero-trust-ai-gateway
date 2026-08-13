import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# Nuevos imports de infraestructura
from app.core.database import AsyncSessionLocal
from app.security_audit.models import SecurityAuditLog
from app.security_audit.graph import security_audit_graph
from app.security_audit.schemas import SecurityAuditLogCreate, SecurityAuditLogRead

app = FastAPI(
    title="Zero-Trust Cognitive AI Gateway",
    version="0.1.0",
    description="Enterprise-grade cloud proxy for secure LLM ingestion and real-time PII sanitization."
)

# Configuración estricta de CORS para entornos distribuidos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, reemplazar con dominios específicos (ej. https://ai.enterprise.com)
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)

async def persist_audit_log_task(log_data: Dict[str, Any]) -> None:
    """
    Asynchronous background task to persist security logs into PostgreSQL.
    Utilizes an independent AsyncSession scope to guarantee isolated, non-blocking inserts.
    """
    # Open an isolated session from the connection pool
    async with AsyncSessionLocal() as session:
        try:
            # Open an explicit database transaction context
            async with session.begin():
                # Map the incoming dictionary directly into our SQLAlchemy Model
                audit_log_entry = SecurityAuditLog(**log_data)
                session.add(audit_log_entry)
            
            # Transaction is auto-committed here when leaving the context block successfully
            print(f"[AUDIT DB PERSISTED] - TraceID: {log_data.get('id')}")
            
        except Exception as e:
            # Crucial: Rollback is triggered automatically if an error occurs within session.begin()
            print(f"[CRITICAL] Async database transaction failed for TraceID {log_data.get('id')}: {str(e)}")


@app.post(
    "/v1/security/scan",
    response_model=SecurityAuditLogRead,
    status_code=status.HTTP_200_OK,
    summary="Intercept, evaluate, and sanitize user prompts under Zero-Trust constraints."
)
async def scan_prompt(
    payload: SecurityAuditLogCreate, 
    background_tasks: BackgroundTasks
) -> Any:
    """
    Endpoint Core del Gateway:
    Recibe el payload del cliente, invoca de manera asíncrona el grafo cognitivo 
    de LangGraph para calcular el riesgo y sanitizar el prompt, y despacha 
    la auditoría a un hilo secundario antes de responder.
    """
    # 1. Inicialización del estado requerido por el StateGraph de LangGraph
    initial_state = {
        "original_prompt": payload.original_prompt,
        "risk_score": 0.0,
        "sanitized_prompt": payload.original_prompt
    }

    try:
        # 2. Invocación asíncrona y no bloqueante del flujo agéntico
        graph_output = await security_audit_graph.ainvoke(initial_state)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Safety evaluation graph failed during execution: {str(e)}"
        )

    # 3. Generación de metadatos determinísticos de auditoría corporativa
    record_id = uuid.uuid4()
    processed_timestamp = datetime.now(timezone.utc)

    # 4. Construcción del diccionario de datos alineado exactamente con el modelo de PostgreSQL
    db_log_payload = {
        "id": record_id,
        "user_id": payload.user_id,
        "original_prompt": payload.original_prompt,
        "sanitized_prompt": graph_output.get("sanitized_prompt"),
        "risk_score": graph_output.get("risk_score", 0.0),
        "pii_detected": graph_output.get("pii_detected", False),
        "timestamp": processed_timestamp
    }

    # 5. Delegación del INSERT a la cola de Background Tasks de FastAPI
    background_tasks.add_task(persist_audit_log_task, db_log_payload)

    # 6. Retorno estructurado bajo la validación estricta del esquema Pydantic
    return db_log_payload


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Infrastructure"])
async def health_check() -> Dict[str, str]:
    """Liveness y readiness probe para orquestadores de infraestructura (Kubernetes/AWS)."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
