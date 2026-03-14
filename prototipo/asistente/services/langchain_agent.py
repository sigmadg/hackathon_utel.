"""
Agente LangChain que configura la copia del template de la sesión.
Usa herramientas (tools) para aplicar diseño, integraciones (pagos, chatbot, dropshipping)
y opcionalmente RAG. Se puede activar con LANGCHAIN_AGENT=true.
"""
import asyncio
import json
import logging
import os
from functools import partial

from django.conf import settings

logger = logging.getLogger(__name__)

def _get_llm():
    """ChatOpenAI configurado como el proyecto (Ollama o OpenAI)."""
    use_ollama = os.environ.get("OLLAMA_MODEL", getattr(settings, "OLLAMA_MODEL", "")).strip()
    if use_ollama:
        from langchain_openai import ChatOpenAI
        base_url = os.environ.get("OLLAMA_BASE_URL", getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"))
        return ChatOpenAI(
            model=use_ollama or "llama3.2",
            base_url=base_url.rstrip("/"),
            api_key="ollama",
            temperature=0,
        )
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=api_key,
            temperature=0,
        )
    return None


def _make_tools(chat_id, effects):
    """Crea las herramientas del agente con chat_id y effects (dict mutable) fijados."""
    from langchain_core.tools import tool
    from .flow_service import has_chat_copy, get_chat_copy_preview_path
    from .design_applier import apply_design_to_copy, apply_integration_badge
    from .rag_service import get_context_for_query

    cid = str(chat_id)

    @tool
    def apply_design(store_name: str = "", primary_color: str = "", secondary_color: str = "", background_color: str = "", language: str = "") -> str:
        """Aplica diseño a la copia del template de la tienda: título (store_name), colores (primary_color, secondary_color, background_color en hex #XXX), idioma (language: es para español). Usa este tool cuando el usuario pida cambiar título, colores o idioma."""
        if not has_chat_copy(cid):
            return "No hay copia del template para este chat."
        spec = {}
        if store_name:
            spec["store_name"] = store_name
        if primary_color:
            spec["primary_color"] = primary_color if primary_color.startswith("#") else "#" + primary_color
        if secondary_color:
            spec["secondary_color"] = secondary_color if secondary_color.startswith("#") else "#" + secondary_color
        if background_color:
            spec["background_color"] = background_color if background_color.startswith("#") else "#" + background_color
        if language:
            spec["language"] = language
        if not spec:
            return "Faltan parámetros de diseño (store_name, primary_color, etc.)."
        ok, msg = apply_design_to_copy(cid, spec)
        if ok:
            effects["template_updated"] = True
            effects["preview_path"] = get_chat_copy_preview_path(cid) or ""
            effects["message"] = msg
        return msg

    @tool
    def apply_integration(integration_type: str) -> str:
        """Integra una funcionalidad en la copia del template. integration_type debe ser uno de: pagos, chatbot, dropshipping. Usa este tool cuando el usuario pida integrar métodos de pago, activar chatbot o dropshipping."""
        if integration_type not in ("pagos", "chatbot", "dropshipping"):
            return f"Tipo no válido. Usa: pagos, chatbot o dropshipping."
        if not has_chat_copy(cid):
            return "No hay copia del template para este chat."
        ok, msg = apply_integration_badge(cid, integration_type)
        if ok:
            effects["template_updated"] = True
            effects["preview_path"] = get_chat_copy_preview_path(cid) or ""
            effects["message"] = msg
        return msg

    @tool
    def search_docs(query: str) -> str:
        """Busca en la documentación sobre métodos de pago, chats automatizados y dropshipping. Usa cuando el usuario pregunte cómo funcionan o qué opciones hay."""
        return get_context_for_query(query) or "No hay documentación relevante para esa consulta."

    return [apply_design, apply_integration, search_docs]


SYSTEM_PROMPT = """Eres un agente que configura la tienda en línea del usuario. Tienes una copia del template de la tienda en edición.

Cuando el usuario pida:
- Cambiar título, colores o idioma de la tienda → usa la herramienta apply_design con los parámetros que indique.
- Integrar métodos de pago, chatbot o dropshipping → usa apply_integration con el tipo (pagos, chatbot o dropshipping).

No des instrucciones de "cómo hacerlo"; ejecuta la herramienta correspondiente y luego responde en una frase que ya está hecho y que revise la vista previa. Responde siempre en español. Termina invitando: ¿Algo más?"""


def run_langchain_agent(chat_id, user_message, history_messages=None, has_copy=True):
    """
    Ejecuta el agente LangChain con herramientas sobre la copia del template.
    history_messages: lista de dicts {"role": "user"|"assistant", "content": "..."}.

    Returns:
        dict con reply_clean, template_updated, preview_path, action_result, reply_override.
    """
    effects = {"template_updated": False, "preview_path": "", "message": ""}

    llm = _get_llm()
    if not llm:
        return None  # Fallback al flujo actual

    try:
        from langchain.agents import create_agent
        from langchain_core.messages import HumanMessage, AIMessage
    except ImportError:
        logger.warning("LangChain no disponible para el agente.")
        return None

    tools = _make_tools(chat_id, effects)
    agent = create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)

    # El agente espera una lista de mensajes (el system ya lo inyecta create_agent)
    messages = []
    if history_messages:
        for m in history_messages[-10:]:
            role = (m.get("role") or "user").lower()
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_message))

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(agent.ainvoke({"messages": messages}))
        loop.close()
    except Exception as e:
        logger.exception("Error al ejecutar agente LangChain: %s", e)
        return None

    out_messages = result.get("messages") or []
    reply_parts = []
    for m in out_messages:
        if hasattr(m, "content") and m.content and isinstance(m.content, str):
            reply_parts.append(m.content)
    reply_clean = (reply_parts[-1] if reply_parts else "").strip() if out_messages else ""

    return {
        "reply_clean": reply_clean or "Listo. Revisa la vista previa. ¿Algo más?",
        "template_updated": effects["template_updated"],
        "preview_path": effects.get("preview_path", ""),
        "action_result": {"success": True, "message": effects.get("message", ""), "detail": {"integration_applied": effects["template_updated"]}} if effects.get("message") else None,
        "reply_override": (effects.get("message") or "").rstrip(".") + ". ¿Algo más?" if effects.get("message") else None,
        "action_normalized": "",
    }
