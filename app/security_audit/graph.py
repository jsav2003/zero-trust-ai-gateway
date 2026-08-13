from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# Inyectamos nuestra configuración global estricta
from app.core.config import settings

# 1. El Estado del Grafo (La Bandeja de Entrada)
class SecurityGraphState(TypedDict):
    original_prompt: str
    sanitized_prompt: str
    risk_score: float
    pii_detected: bool

# 2. El Motor de IA (Gemini 3.5 Flash)
# Gemini 3.x deprecó los parámetros de sampling (temperature, top_p, top_k),
# por lo que ya no se envían en la configuración del modelo.
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    api_key=settings.GOOGLE_API_KEY
)

# 3. Esquema Estricto para forzar a Gemini a devolver datos computables
class AnalyzerOutput(BaseModel):
    risk_score: float = Field(description="Nivel de riesgo del 0.0 al 10.0.")
    pii_detected: bool = Field(description="True si se detectan contraseñas, emails, nombres o datos sensibles.")

analyzer_llm = llm.with_structured_output(AnalyzerOutput)

# --- NODOS DEL GRAFO ---

async def analyzer_node(state: SecurityGraphState):
    """Evalúa el texto cognitivamente usando Gemini y devuelve métricas exactas."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un Analista de Seguridad Zero Trust. Inspecciona el texto del usuario en busca de Información de Identificación Personal (PII) o secretos. Eres estricto y preciso."),
        ("user", "{text}")
    ])
    
    chain = prompt | analyzer_llm
    result = await chain.ainvoke({"text": state["original_prompt"]})
    
    return {
        "risk_score": result.risk_score,
        "pii_detected": result.pii_detected
    }

async def sanitizer_node(state: SecurityGraphState):
    """Filtra y censura la información maliciosa manteniendo el contexto original."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un sanitizador de datos. Reemplaza cualquier información sensible (contraseñas, emails, secretos, nombres) en el texto con la palabra [REDACTED]. Devuelve ÚNICAMENTE el texto sanitizado, sin comentarios adicionales."),
        ("user", "{text}")
    ])
    
    chain = prompt | llm
    result = await chain.ainvoke({"text": state["original_prompt"]})
    
    content = result.content
    if isinstance(content, list):
        content = "".join([block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"])
    elif not isinstance(content, str):
        content = str(content)
        
    return {
        "sanitized_prompt": content
    }

# --- LÓGICA DE ENRUTAMIENTO ---

def routing_logic(state: SecurityGraphState):
    """El Switch cognitivo: decide en milisegundos si el texto debe ser censurado."""
    if state["pii_detected"] or state["risk_score"] > 5.0:
        return "sanitizer_node"
    
    # Si es un texto inofensivo, se ahorra el procesamiento de censura y termina.
    return END

# --- ENSAMBLAJE DEL ORQUESTADOR ---

workflow = StateGraph(SecurityGraphState)

workflow.add_node("analyzer_node", analyzer_node)
workflow.add_node("sanitizer_node", sanitizer_node)

workflow.set_entry_point("analyzer_node")
workflow.add_conditional_edges("analyzer_node", routing_logic)
workflow.add_edge("sanitizer_node", END)

# Compilamos el motor
security_audit_graph = workflow.compile()
