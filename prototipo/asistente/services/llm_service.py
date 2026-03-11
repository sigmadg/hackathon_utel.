"""
Servicio de integración con LLM (OpenAI-compatible) para interpretar
la intención del usuario y generar respuestas del asistente.
"""
import os
from django.conf import settings

SYSTEM_PROMPT = """Eres un asistente que ayuda a configurar una tienda en línea en Tiendanube.
El usuario puede pedirte en lenguaje natural cosas como:
- Activar o configurar un chatbot para preguntas frecuentes
- Integrar validación de identidad o APIs de validación
- Añadir reconocimiento facial para verificación
- Configurar envíos, pagos u otras secciones de la tienda

Responde en español, de forma clara y breve. Cuando detectes una intención concreta
(por ejemplo "quiero un chatbot", "necesito validar clientes", "reconocimiento facial"),
incluye al final de tu respuesta una línea que empiece exactamente con:
ACCION: <nombre_accion>
donde nombre_accion puede ser: chatbot, api_validacion, reconocimiento_facial, envios, pagos, dropshipping, otro.
Si no hay una intención clara, usa ACCION: otro.

Ejemplo de respuesta:
"Puedo ayudarte a activar un chatbot para tu tienda. El chatbot podrá responder preguntas frecuentes
sobre productos y envíos. ¿Quieres que lo active ahora?
ACCION: chatbot"
"""


def get_llm_client():
    """Devuelve cliente OpenAI (para OpenAI o para Ollama con API compatible)."""
    use_ollama = os.environ.get("OLLAMA_MODEL", getattr(settings, "OLLAMA_MODEL", "")).strip()
    if use_ollama:
        try:
            from openai import OpenAI
            base_url = os.environ.get("OLLAMA_BASE_URL", getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1"))
            return OpenAI(base_url=base_url.rstrip("/"), api_key="ollama")
        except Exception:
            return None
    if getattr(settings, 'OPENAI_API_KEY', None):
        try:
            from openai import OpenAI
            return OpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception:
            return None
    return None


def _get_model():
    """Modelo a usar: Ollama o OpenAI."""
    if os.environ.get("OLLAMA_MODEL", getattr(settings, "OLLAMA_MODEL", "")).strip():
        return os.environ.get("OLLAMA_MODEL", getattr(settings, "OLLAMA_MODEL", "qwen2.5-coder:1.5b"))
    return os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')


def chat(messages):
    client = get_llm_client()
    if not client:
        return _fallback_response(messages)

    try:
        model = _get_model()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            max_tokens=500,
        )
        text = (response.choices[0].message.content or "").strip()
        return text
    except Exception as e:
        return f"Error al conectar con el asistente: {str(e)}. Puedes seguir describiendo lo que necesitas."


def _fallback_response(messages):
    last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    last_lower = last_user.lower()

    if "chatbot" in last_lower or "chat" in last_lower:
        return (
            "Puedo ayudarte a configurar un chatbot para tu tienda. "
            "El chatbot podrá responder preguntas frecuentes sobre productos y envíos. "
            "¿Quieres que lo active ahora?\nACCION: chatbot"
        )
    if "validar" in last_lower or "validación" in last_lower or "api" in last_lower:
        return (
            "Puedo guiarte para integrar una API de validación (por ejemplo identidad o datos). "
            "Indica qué tipo de validación necesitas y te indico los pasos.\nACCION: api_validacion"
        )
    if "reconocimiento facial" in last_lower or "facial" in last_lower or "rostro" in last_lower:
        return (
            "Puedo ayudarte a integrar reconocimiento facial para verificación de clientes. "
            "Se configurará un módulo que podrás usar en el checkout o en áreas privadas.\nACCION: reconocimiento_facial"
        )
    if "envío" in last_lower or "envíos" in last_lower:
        return "Puedo ayudarte a configurar opciones de envío para tu tienda.\nACCION: envios"
    if "pago" in last_lower or "pagos" in last_lower:
        return "Puedo guiarte para configurar métodos de pago en tu tienda.\nACCION: pagos"
    if "dropship" in last_lower:
        return (
            "Puedo configurar la integración con APIs de dropshipping para sincronizar inventario y pedidos con proveedores.\nACCION: dropshipping"
        )

    return (
        "Cuéntame qué necesitas en tu tienda: por ejemplo un chatbot, validación de clientes, "
        "reconocimiento facial, envíos o pagos. Te guío paso a paso.\nACCION: otro"
    )


def extract_action(response_text):
    for line in response_text.splitlines():
        line = line.strip()
        if line.upper().startswith("ACCION:"):
            return line[7:].strip().lower() or "otro"
    return "otro"
