"""
Agente que ejecuta cambios en la copia del template en edición.
El LLM emite órdenes (ACCION, diseño JSON); este agente ejecuta las herramientas
sobre la copia del template (diseño, integraciones, etc.) y devuelve el resultado.
"""
import logging

from .flow_service import has_chat_copy, get_chat_copy_preview_path
from .design_applier import apply_design_to_copy, parse_user_design_intent, apply_integration_badge
from .llm_service import extract_action, extract_design_spec, extract_design_spec_fallback
from .intent_handler import execute_action

logger = logging.getLogger(__name__)


def run_agent(chat_id, reply_text, last_user_message, has_copy, request=None):
    """
    Ejecuta el agente sobre la copia del template: interpreta la respuesta del LLM,
    ejecuta las herramientas (diseño, integración) en la copia y devuelve el resultado.

    Args:
        chat_id: id del chat (copia en Templates/copies/<chat_id>/)
        reply_text: respuesta cruda del LLM (puede contener ACCION y JSON de diseño)
        last_user_message: último mensaje del usuario (para fallback de intención)
        has_copy: si existe copia del template para este chat
        request: opcional, para execute_action (Tiendanube API)

    Returns:
        dict con:
          reply_clean: texto de respuesta sin ACCION/JSON
          template_updated: bool
          preview_path: str o ""
          action_result: dict o None
          reply_override: str o None (mensaje fijo cuando aplicamos integración)
          action_normalized: str
    """
    action = extract_action(reply_text)
    action_normalized = (action or "").replace("ñ", "n").replace("ó", "o").strip()

    # Si el LLM no emitió una orden clara, interpretar la intención del mensaje del usuario
    if not action_normalized or action_normalized == "otro":
        last_lower = (last_user_message or "").strip().lower()
        if any(k in last_lower for k in ("pago", "pagos", "metodo de pago", "métodos de pago", "mercadopago", "paypal", "integrar pago", "agregar pago")):
            action_normalized = "pagos"
        elif any(k in last_lower for k in ("chatbot", "chat automático", "chat automatico", "activa el chat", "atención automática")):
            action_normalized = "chatbot"
        elif any(k in last_lower for k in ("dropship", "dropshipping", "proveedor")):
            action_normalized = "dropshipping"
        elif any(k in last_lower for k in ("color", "colores", "título", "titulo", "nombre de la tienda", "idioma", "español", "diseño", "diseno")):
            action_normalized = "diseno"

    reply_clean = "\n".join(
        line for line in reply_text.splitlines()
        if not line.strip().upper().startswith("ACCION:")
        and not (line.strip().startswith("{") and line.strip().endswith("}"))
    ).strip()

    result = {
        "reply_clean": reply_clean,
        "template_updated": False,
        "preview_path": "",
        "action_result": None,
        "reply_override": None,
        "action_normalized": action_normalized,
    }

    if not has_copy:
        # Sin copia: solo ejecutar acción genérica (Tiendanube, etc.) si aplica
        if action_normalized and action_normalized != "otro":
            ok, msg, detail = execute_action(action, context={"request": request})
            result["action_result"] = {"success": ok, "message": msg, "detail": detail}
        return result

    # --- Con copia: el agente ejecuta herramientas sobre la copia del template ---

    # 1) Herramienta: aplicar diseño (colores, título, idioma)
    design_spec = (
        extract_design_spec(reply_text)
        or extract_design_spec_fallback(reply_text)
        or parse_user_design_intent(last_user_message)
    )
    if design_spec:
        logger.info("Agente: aplicando diseño en copia chat_id=%s spec=%s", chat_id, design_spec)
        ok, msg = apply_design_to_copy(chat_id, design_spec)
        logger.info("Agente: diseño aplicado ok=%s msg=%s", ok, msg)
        result["action_result"] = {"success": ok, "message": msg, "detail": {"design_applied": ok}}
        if ok:
            result["template_updated"] = True
            result["preview_path"] = get_chat_copy_preview_path(chat_id) or ""

    # 2) Si no hubo diseño pero sí acción de integración: herramienta aplicar integración en la copia
    if not result["template_updated"] and action_normalized in ("pagos", "chatbot", "dropshipping"):
        logger.info("Agente: aplicando integración en copia chat_id=%s tipo=%s", chat_id, action_normalized)
        badge_ok, badge_msg = apply_integration_badge(chat_id, action_normalized)
        if badge_ok:
            result["template_updated"] = True
            result["preview_path"] = get_chat_copy_preview_path(chat_id) or ""
            result["action_result"] = {
                "success": True,
                "message": badge_msg,
                "detail": {"integration_applied": True},
            }
            result["reply_override"] = badge_msg.rstrip(".") + ". ¿Algo más?"
        else:
            # Fallback: ejecutar acción genérica (ej. registrar en Tiendanube)
            ok, msg, detail = execute_action(action, context={"request": request})
            result["action_result"] = {"success": ok, "message": msg, "detail": detail}

    # 3) Otra acción (envíos, api_validacion, etc.): ejecutar pero sin tocar la copia
    if result["action_result"] is None and action_normalized and action_normalized != "otro":
        if action_normalized == "diseno":
            result["action_result"] = {"success": False, "message": "No se pudo interpretar el diseño.", "detail": {}}
        else:
            ok, msg, detail = execute_action(action, context={"request": request})
            result["action_result"] = {"success": ok, "message": msg, "detail": detail}

    return result
