"""
Servicio de integración con LLM (OpenAI-compatible) para interpretar
la intención del usuario y generar respuestas del asistente.
"""
import json
import os
import re
from django.conf import settings

SYSTEM_PROMPT = """Eres un asistente que ayuda a configurar una tienda en línea en Tiendanube.
El usuario puede pedirte en lenguaje natural cosas como:
- Activar o configurar un chatbot para preguntas frecuentes
- Integrar validación de identidad o APIs de validación
- Añadir reconocimiento facial para verificación
- Configurar envíos, pagos u otras secciones de la tienda

Responde en español, de forma clara y breve. NUNCA des por terminada la conversación: no digas "Hasta luego", "adiós" ni cierres; invita siempre a seguir (ej: "¿Necesitas algo más?").
Cuando detectes una intención concreta incluye al final: ACCION: <nombre_accion>
(nombre_accion: chatbot, api_validacion, reconocimiento_facial, envios, pagos, dropshipping, diseno, otro).
Si no hay una intención clara, usa ACCION: otro.

Ejemplo: "Puedo ayudarte a activar un chatbot para tu tienda. ¿Quieres que lo active ahora? ¿Algo más?
ACCION: chatbot"
"""

DESIGN_CONTEXT_PROMPT = """

IMPORTANTE: El usuario tiene una copia del template de su tienda en el visor. Los cambios solo se ven si en TU respuesta incluyes ACCION: diseno y el JSON.

REGLAS OBLIGATORIAS (aplican en CADA mensaje, no solo en el primero):
1. NUNCA cierres la conversación. Siempre termina invitando: "¿Quieres cambiar algo más?", "¿Algún otro ajuste?"
2. CADA VEZ que el usuario pida algo de diseño (título, colores, estilo, fondo, idioma, etc.) — sea el primer mensaje, el segundo o el décimo — DEBES incluir al final de tu respuesta exactamente:
   - Una línea: ACCION: diseno
   - La línea siguiente: un solo objeto JSON con store_name, primary_color, secondary_color, background_color, language (según lo que pida). Para idioma español usa "language": "es". Colores en hex con #. Sin ``` ni markdown.
   Si en algún mensaje de diseño no incluyes esas dos líneas, ese cambio NO se aplicará.
3. El usuario puede ir pidiendo varios cambios seguidos (ej: primero "colores azul y blanco", luego "cambia el azul por verde", luego "pon el título MiTienda"). En CADA respuesta a esas peticiones debes poner ACCION: diseno y el JSON con los valores que correspondan a ESE mensaje.
4. En tu texto solo confirma en una frase y no muestres el JSON al usuario.

Ejemplo respuesta 1 (usuario: "quiero título CloudIA y colores rojo y rosa"):
Listo, título CloudIA y colores rojo y rosa aplicados. ¿Quieres cambiar algo más?
ACCION: diseno
{"store_name": "CloudIA", "primary_color": "#FF007D", "secondary_color": "#FFB6C1", "background_color": "#f8fafc"}

Ejemplo respuesta 2 (usuario: "cambia el rojo por azul"):
Hecho, azul aplicado. ¿Algún otro cambio?
ACCION: diseno
{"primary_color": "#2563eb", "secondary_color": "#FFB6C1", "background_color": "#f8fafc"}

Ejemplo respuesta 3 (usuario: "pon el idioma en español" o "ajusta el idioma"):
Listo, idioma en español aplicado. ¿Quieres cambiar algo más?
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


def chat(messages, has_template_copy=False):
    client = get_llm_client()
    if not client:
        return _fallback_response(messages, has_template_copy)

    system = SYSTEM_PROMPT + (DESIGN_CONTEXT_PROMPT if has_template_copy else "")
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
