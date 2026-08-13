# Zero-Trust Cognitive AI Gateway

An asynchronous, cloud-native API Gateway designed to intercept, analyze, and sanitize incoming user prompts in real-time before they reach internal LLM orchestrators. Built with a Zero-Trust security model, this system detects Personal Identifiable Information (PII), assesses security risks using advanced semantic analysis, and redacts sensitive data dynamically.

## 🏗️ Solution Architecture

The gateway separates the core synchronous execution path (low-latency prompt engineering) from the asynchronous database persistence layer using non-blocking I/O workers.

```mermaid
graph TD
    classDef client fill:#2d3436,stroke:#74b9ff,stroke-width:2px,color:#fff;
    classDef api fill:#0984e3,stroke:#74b9ff,stroke-width:2px,color:#fff;
    classDef ai fill:#6c5ce7,stroke:#a29bfe,stroke-width:2px,color:#fff;
    classDef db fill:#00b894,stroke:#55efc4,stroke-width:2px,color:#fff;
    classDef cloud fill:#fdcb6e,stroke:#ffeaa7,stroke-width:2px,color:#2d3436;

    Client["📱 Client / Frontend<br>(REST API Request)"]:::client
    API["⚡ FastAPI (Gateway)<br>Pydantic Validation"]:::api
    
    subgraph "🧠 Cognitive Agent Graph (LangGraph)"
        Analyzer["🔍 analyzer_node<br>(PII & Risk Evaluation)"]:::ai
        Router{"🔀 routing_logic"}:::ai
        Sanitizer["🛡️ sanitizer_node<br>(Contextual Redaction)"]:::ai
    end
    
    Gemini["☁️ Google Gemini 3.6 Flash<br>(LLM / Structured Output)"]:::cloud
    LangSmith["📊 LangSmith<br>(Telemetry & Observability)"]:::cloud
    
    subgraph "🐳 Docker Environment"
        DB[("🐘 PostgreSQL + pgvector<br>(Async Audit Logging)")]:::db
    end

    Client -->|POST /v1/security/scan| API
    API -->|1. Invoke Graph| Analyzer
    API -.->|2. Delegate Task| DB
    
    Analyzer <-->|Prompt + Strict Schema| Gemini
    Analyzer --> Router
    Router -->|Risk > 5.0 or PII| Sanitizer
    Router -->|Clean Flow| API
    Sanitizer <-->|Semantic Masking| Gemini
    Sanitizer --> API
    
    API -->|HTTP 200 Response| Client
    Analyzer -.->|Telemetry Trace| LangSmith
    Sanitizer -.->|Telemetry Trace| LangSmith
```

## 🌟 Key Features
**Cognitive Routing Engine**: Implemented via LangGraph as a deterministic state machine that evaluates security metrics before executing payload redaction.

**Strict Structured Output**: Leverages Pydantic v2 interfacing with Gemini 3.6 Flash to guarantee type-safe, validated JSON structures from the LLM, eliminating hallucinations.

**High-Concurrency Architecture**: Engineered with FastAPI utilizing an asynchronous connection pool (asyncpg + SQLAlchemy) to handle massive request volumes without blocking I/O thresholds.

**Fault-Tolerant Persistence**: Utilizes FastAPI BackgroundTasks to offload relational auditing into isolated Dockerized PostgreSQL containers, ensuring API up-time even during database overhead.

**Production Observability**: Integrated with LangSmith tracing API for comprehensive latency tracking, token financial budgeting, and multi-node logical flow debugging.

## 🛠️ Tech Stack
* **Backend Framework**: FastAPI (Python 3.12+)
* **AI Orchestration**: LangGraph, LangChain Core
* **Cognitive Brain**: Google Gemini 3.6 Flash API
* **Database & Infrastructure**: PostgreSQL (with pgvector readiness), Docker, Docker Compose
* **Data Validation & ORM**: Pydantic v2, SQLAlchemy 2.0, Alembic (Database Migrations)
* **Observability**: LangSmith Telemetry

## 🚀 Getting Started
### 1. Environment Configuration
Create a `.env` file in the root directory:

```env
ENV=development
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/gateway_db

# Google AI Studio
GOOGLE_API_KEY=your_gemini_api_key_here

# LangSmith Telemetry
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=enterprise-ai-gateway
LANGCHAIN_API_KEY=your_langsmith_api_key_here
```

### 2. Infrastructure Deployment (Docker)
Spin up the isolated database infrastructure:

```bash
docker-compose up -d
```

### 3. Database Migrations (Alembic)
Apply the relational schema versioning downstream into the live container:

```bash
alembic upgrade head
```

### 4. Running the Application Server
Execute the asynchronous server worker injecting the environment configuration:

```bash
uvicorn app.main:app --reload --env-file .env
```
The interactive interactive documentation will be available at http://127.0.0.1:8000/docs.

## 📊 API Verification Example
### Request Payload (POST /v1/security/scan)
```json
{
  "user_id": "emp_992_enterprise",
  "original_prompt": "Hey team, here are the production credentials. The user is db_admin and the password is M1S3cr3t0G00gl3. Keep it safe."
}
```

### Sanitized Response (HTTP 200 OK)
```json
{
  "user_id": "emp_992_enterprise",
  "original_prompt": "Hey team, here are the production credentials. The user is db_admin and the password is M1S3cr3t0G00gl3. Keep it safe.",
  "sanitized_prompt": "Hey team, here are the production credentials. The user is [REDACTED] and the password is [REDACTED]. Keep it safe.",
  "risk_score": 9.8,
  "pii_detected": true,
  "id": "72efc80b-3ea1-4753-a9d1-de0c05eec394",
  "timestamp": "2026-07-08T03:19:39.965275Z"
}
```

## 📜 License
This project is licensed under the MIT License.
