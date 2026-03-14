"""
Servicio de integración con LLM (OpenAI-compatible) para interpretar
la intención del usuario y generar respuestas del asistente.
"""
import json
import os
import re
from django.conf import settings

SYSTEM_PROMPT = """Eres un asistente que interpreta lo que el usuario pide y emite la orden para el agente.
1. LEE e INTERPRETA el mensaje del usuario (qué quiere: pagos, colores, chatbot, idioma, etc.).
2. Responde en español con una frase breve y al final incluye la orden: ACCION: <nombre_accion>
Acciones: chatbot, api_validacion, reconocimiento_facial, envios, pagos, dropshipping, diseno, otro.
Si no entiendes o no hay intención clara, usa ACCION: otro y pregunta qué necesita.
"""

# Con template en edición: interpreta lo que pide el usuario y emite la orden correspondiente.
AGENT_CONTEXT_PROMPT = """

IMPORTANTE: Interpreta siempre lo que el usuario escribe. Si pide métodos de pago, integrar pagos, activar chatbot, dropshipping, colores, título o idioma, emite la orden correcta.

Si pide algo relacionado con:
- pagos, métodos de pago, mercadopago, paypal → ACCION: pagos
- chatbot, chat automático, atención automática → ACCION: chatbot
- dropshipping, proveedores → ACCION: dropshipping
- colores, título, nombre de tienda, idioma español → ACCION: diseno (y si es diseño, añade el JSON en la línea siguiente)

Responde en una frase y termina con la orden. Ejemplo:
Usuario: "quiero agregar métodos de pago"
Listo. Revisa la vista previa.
ACCION: pagos
"""

DESIGN_CONTEXT_PROMPT = """

Cuando el usuario pida título, colores o idioma: INTERPRETA qué pide y emite ACCION: diseno más el JSON en la línea siguiente.
- Si dice un nombre o título → incluye "store_name" en el JSON.
- Si dice colores (ej. azul, rojo y blanco) → primary_color, secondary_color en hex (#2563eb, #dc2626, #ffffff).
- Si dice idioma español o en español → "language": "es".

Formato al final:
ACCION: diseno
{"store_name": "...", "primary_color": "#hex", "secondary_color": "#hex", "background_color": "#hex", "language": "es"}

Ejemplos:
Usuario: "quiero título Mi Tienda y colores azul y blanco"
Listo. Revisa la vista previa.
ACCION: diseno
{"store_name": "Mi Tienda", "primary_color": "#2563eb", "secondary_color": "#ffffff", "background_color": "#f8fafc"}

Usuario: "pon el idioma en español"
Listo. Revisa la vista previa.
ACCION: diseno
{"language": "es"}
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


def chat(messages, has_template_copy=False, rag_context=None):
    client = get_llm_client()
    if not client:
        return _fallback_response(messages, has_template_copy)

    system = SYSTEM_PROMPT + (AGENT_CONTEXT_PROMPT + DESIGN_CONTEXT_PROMPT if has_template_copy else "")
    if rag_context and isinstance(rag_context, str) and rag_context.strip():
        system += "\n\n--- Contexto de la documentación (usa esta información para responder sobre métodos de pago, chats automatizados o dropshipping si es relevante para la pregunta del usuario):\n\n"
        system += rag_context.strip()
        system += "\n\nResponde con base en este contexto cuando aplique, sin inventar datos."
    try:
        model = _get_model()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}] + messages,
            max_tokens=600,
        )
        text = (response.choices[0].message.content or "").strip()
        return text
    except Exception as e:
        return f"Error al conectar con el asistente: {str(e)}. Puedes seguir describiendo lo que necesitas."


def _fallback_response(messages, has_template_copy=False):
    last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    last_lower = last_user.lower()

    if has_template_copy and any(k in last_lower for k in ("color", "colores", "azul", "rojo", "verde", "blanco", "negro", "diseño", "diseño", "fondo", "estilo", "minimalista", "oscuro")):
        primary = "#2563eb" if "azul" in last_lower else "#dc2626" if "rojo" in last_lower else "#16a34a" if "verde" in last_lower else "#000000" if "negro" in last_lower else "#ffffff" if "blanco" in last_lower else "#2563eb"
        secondary = "#ffffff" if "blanco" in last_lower or "azul" in last_lower else "#f8fafc"
        return (
            f"Aplicando los colores que pediste a tu tienda."
            "\nACCION: diseno\n"
            f'{{"primary_color": "{primary}", "secondary_color": "{secondary}", "background_color": "#f8fafc"}}'
        )
    if "chatbot" in last_lower or "chat" in last_lower:
        return "Listo, chatbot implementado en tu tienda. Revisa la vista previa. ¿Algo más?\nACCION: chatbot"
    if "validar" in last_lower or "validación" in last_lower or "api" in last_lower:
        return "Listo, registrado. ¿Algo más?\nACCION: api_validacion"
    if "reconocimiento facial" in last_lower or "facial" in last_lower or "rostro" in last_lower:
        return "Listo, registrado. ¿Algo más?\nACCION: reconocimiento_facial"
    if "envío" in last_lower or "envíos" in last_lower:
        return "Listo, aplicado. Revisa la vista previa. ¿Algo más?\nACCION: envios"
    if "pago" in last_lower or "pagos" in last_lower:
        return "Ya se integraron los métodos de pago en tu tienda. Revisa la vista previa. ¿Algo más?\nACCION: pagos"
    if "dropship" in last_lower:
        return "Listo, dropshipping implementado en tu tienda. Revisa la vista previa. ¿Algo más?\nACCION: dropshipping"

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


def extract_design_spec(response_text):
    """
    Si la respuesta incluye ACCION: diseno/diseño, extrae el JSON de diseño (objeto {...}).
    Busca el JSON en texto plano o dentro de bloques ```json ... ```.
    Devuelve dict con store_name, primary_color, etc. o None si no hay diseño.
    """
    text_upper = response_text.upper().replace("Ñ", "N")
    if "ACCION:" not in text_upper or "DISENO" not in text_upper:
        return None

    # Intentar extraer de bloque ```json ... ``` o ``` ... ```
    for pattern in [r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", r"```(?:json)?\s*([\s\S]*?)\s*```"]:
        match = re.search(pattern, response_text)
        if match:
            raw = match.group(1).strip()
            if raw.startswith("{"):
                start = raw.find("{")
                depth = 0
                for i, c in enumerate(raw[start:], start):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(raw[start : i + 1])
                            except json.JSONDecodeError:
                                break
                break

    # Buscar primer objeto {...} en el texto
    start = response_text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, c in enumerate(response_text[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(response_text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def extract_design_spec_fallback(response_text):
    """
    Busca cualquier objeto JSON en la respuesta que parezca un design_spec
    (store_name, primary_color, etc.), por si el LLM no escribió ACCION: diseno.
    """
    start = response_text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, c in enumerate(response_text[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(response_text[start : i + 1])
                    if isinstance(obj, dict) and (
                        "store_name" in obj or "title" in obj or "primary_color" in obj
                        or "secondary_color" in obj or "background_color" in obj
                        or "language" in obj or "idioma" in obj
                    ):
                        return obj
                except json.JSONDecodeError:
                    pass
    return None
