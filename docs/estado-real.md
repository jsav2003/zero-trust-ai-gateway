# Estado real del repositorio

Referencia: commit `9b3a423`, 2026-08-13.

Este documento describe lo que el código ejecuta hoy. Donde el README difiera, vale
este documento. El README contiene afirmaciones sobre capacidades que no están en el
código; están enumeradas en la sección "Qué no está implementado".

---

## Endpoints

| Método | Path | Auth | Origen |
|---|---|---|---|
| POST | `/v1/security/scan` | `X-API-Key` requerido | `app/main.py:53` |
| GET | `/health` | ninguna | `app/main.py:108` |
| GET | `/docs`, `/redoc`, `/openapi.json` | ninguna | generados por FastAPI |

Son todos. No hay más rutas.

`/health` devuelve `{"status": "healthy", "timestamp": <utc>}`. El valor es fijo: no
consulta la base de datos ni la API de Gemini. Un `200` de `/health` no indica que
esas dependencias estén disponibles.

## Autenticación

Secreto compartido único en el header `X-API-Key`, comparado contra `GATEWAY_API_KEY`
con `secrets.compare_digest` sobre los operandos encodeados a utf-8.

| Condición | Respuesta |
|---|---|
| `GATEWAY_API_KEY` vacío o no seteado | `503` |
| Header ausente o valor distinto | `401` |
| Coincidencia | continúa |

No hay usuarios, roles, scopes ni expiración. Una sola clave para todos los llamantes.
El campo `user_id` viene del body de la request y no se valida contra la identidad
autenticada: cualquier portador de la clave puede escribir registros de auditoría
atribuidos a cualquier `user_id`.

## Flujo de `POST /v1/security/scan`

Entrada aceptada por `SecurityAuditLogCreate`: `user_id`, `original_prompt`,
`sanitized_prompt`, `risk_score`, `pii_detected`. El endpoint usa sólo los dos
primeros; los otros tres se aceptan en el body y se descartan.

1. Construye `initial_state` con `original_prompt`, `risk_score=0.0` y
   `sanitized_prompt=original_prompt`.
2. `await security_audit_graph.ainvoke(initial_state)`. Una excepción acá devuelve
   `500` con `str(e)` incluido en el campo `detail` de la respuesta.
3. Genera `uuid4()` y timestamp UTC en el servidor.
4. Arma el payload combinando entrada y salida del grafo.
5. Encola `persist_audit_log_task` en `BackgroundTasks`.
6. Devuelve el payload, validado contra `SecurityAuditLogRead`.

El `200` se emite antes de que el INSERT termine. Ver "Persistencia".

## El grafo

`app/security_audit/graph.py`. Dos nodos, entry point `analyzer_node`.

**`analyzer_node`** — una llamada a Gemini con structured output forzado al esquema
`AnalyzerOutput` (`risk_score: float`, `pii_detected: bool`). Devuelve ambos valores
al estado.

**`routing_logic`** — función síncrona, sin llamadas externas. Es la única decisión
del router:

```python
if state["pii_detected"] or state["risk_score"] > 5.0:
    return "sanitizer_node"
return END
```

Cualquiera de las dos señales alcanza por sí sola. El umbral es estrictamente mayor:
`risk_score == 5.0` no enruta al sanitizer.

**`sanitizer_node`** — segunda llamada a Gemini que reemplaza contenido sensible por
`[REDACTED]`. Opera sobre `state["original_prompt"]`, no sobre la salida del analyzer.

Consecuencia del diseño: cuando el router va a `END`, `sanitized_prompt` conserva el
valor que se le puso en `initial_state`, o sea **el `original_prompt` sin modificar**.
Un registro con `pii_detected=false` tiene `sanitized_prompt` idéntico a
`original_prompt`; eso no significa que se haya sanitizado nada.

Modelo: `gemini-3.6-flash`. El cliente se construye en la primera llamada y queda
cacheado (`lru_cache`), no en tiempo de import. No se envían `temperature`, `top_p`
ni `top_k`. No hay timeout explícito ni reintentos configurados.

Costo por request: 1 llamada a Gemini si el prompt no se enruta al sanitizer, 2 si
se enruta.

## Persistencia

Tabla `security_audit_logs` en PostgreSQL. Columnas creadas por la migración
`549d9704c09f`:

| Columna | Tipo | Nulo |
|---|---|---|
| `id` | UUID (PK) | no |
| `user_id` | VARCHAR(255) | no |
| `original_prompt` | TEXT | no |
| `sanitized_prompt` | TEXT | sí |
| `risk_score` | FLOAT | no |
| `pii_detected` | BOOLEAN | no |
| `timestamp` | TIMESTAMPTZ, default `now()` | no |

Dos índices: `(user_id, timestamp DESC)` y `(timestamp DESC)`.

La escritura ocurre en `persist_audit_log_task`, encolada como BackgroundTask, con
una `AsyncSession` propia tomada del pool. Implicaciones verificables en el código:

- El cliente recibe `200` antes de que el INSERT se complete.
- Si el INSERT falla, la excepción se captura, se imprime por stdout y no se
  reintenta. El cliente ya recibió `200`. No hay forma de que el llamante sepa que
  el registro no se guardó.
- `original_prompt` se guarda en texto plano, incluido el contenido que el analyzer
  marcó como PII. No hay cifrado a nivel de columna ni política de retención.

## Configuración

`app/core/config.py`, vía pydantic-settings, leído de variables de entorno y `.env`.
`extra="ignore"`.

| Variable | Default | Efecto si falta |
|---|---|---|
| `ENV` | `development` | ninguno; no se usa en lógica |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/gateway_db` | usa el default |
| `GOOGLE_API_KEY` | `""` | el grafo falla en la primera request, no al arrancar |
| `GATEWAY_API_KEY` | `""` | `/v1/security/scan` devuelve `503` |
| `CORS_ALLOW_ORIGINS` | `http://localhost:8000` | usa el default |

`ENV` está declarada pero ninguna rama del código la consulta.

CORS: origenes desde `CORS_ALLOW_ORIGINS` (string separado por comas),
`allow_credentials=False`, métodos `GET`/`POST`, headers `Content-Type` y `X-API-Key`.

## Tests

3 funciones, 6 casos (`pytest`). No abren conexiones de red ni a la base de datos, y
no requieren `GOOGLE_API_KEY`.

- `test_routing_logic.py` — 4 casos sobre `routing_logic`, incluido el borde `5.0`.
- `test_scan_endpoint.py` — persistencia de `pii_detected` con el grafo stubbeado, y
  rechazo con `401` de un `X-API-Key` con bytes no-ASCII.

No hay tests de `analyzer_node`, `sanitizer_node`, la capa de persistencia, ni las
migraciones.

## Infraestructura

`docker-compose.yml` define un solo servicio: `db`, imagen `pgvector/pgvector:pg16`,
puerto 5432 expuesto, credenciales `postgres`/`postgres`. No hay servicio para la
aplicación; se corre a mano con uvicorn.

Alembic con una migración. 23 archivos versionados.

---

## Qué no está implementado

Todo lo de esta lista está ausente del código, verificado por búsqueda:

- **Endpoint de lectura de auditoría.** No existe forma de consultar
  `security_audit_logs` por la API. `SecurityAuditLogRead` se usa únicamente como
  `response_model` del scan. Los registros sólo se leen con SQL directo.
- **Proxy hacia un LLM downstream.** El README describe el sistema como un gateway
  que intercepta prompts "before they reach internal LLM orchestrators". El código no
  reenvía nada a ningún destino: analiza, guarda y responde. No hay upstream configurable.
- **LangSmith / telemetría.** No hay instrumentación en `app/`. Las variables
  `LANGCHAIN_*` que documenta el README no están en `Settings`. LangChain las lee del
  entorno por su cuenta si están seteadas, pero nada en este repo las configura,
  valida ni verifica.
- **pgvector / embeddings.** La imagen de Docker soporta la extensión, pero la
  migración no la crea y no hay columna vector. En `models.py` la columna está
  comentada.
- **Dockerfile** para la aplicación, y **CI** (no hay `.github/`).
- **Rate limiting** y **rotación o multiplicidad de API keys**.
- **Logging estructurado.** Se usa `print()` a stdout, sin niveles ni formato.
- **Timeouts y reintentos** en las llamadas a Gemini.
- **Health check real.** `/health` no verifica dependencias.

## Bordes conocidos

Verificados ejecutando el código:

- `AnalyzerOutput.risk_score` no tiene cota, pero `SecurityAuditLogRead.risk_score`
  exige `0.0 <= x <= 10.0`. Si Gemini devuelve un valor fuera de rango (p. ej. `11.0`),
  la validación de respuesta falla: el cliente recibe **`500`** y el BackgroundTask
  **no llega a ejecutarse**, así que tampoco queda registro. El caso se pierde entero.
- Una excepción del grafo devuelve `500` con `str(e)` interpolado en el body. El
  detalle del error interno queda expuesto a llamantes autenticados.
- El prompt del sanitizer instruye devolver únicamente el texto sanitizado. No hay
  validación de que la salida cumpla eso; lo que devuelva el modelo se persiste tal cual.
