"""
Flujo conversacional: qué vender → elegir diseño (3 templates) → qué agregar (pagos, dropshipping, etc.).
"""
import json
import os
from pathlib import Path

from . import page_generator

# Rutas a las plantillas reales bajo Templates/ (para el iframe del visor)
DESIGN_TEMPLATE_PATHS = {
    "minimal": "odor-buyer-file/index.html",
    "moderno": "ecom-responsive-ecommerce-html-template-2023-11-27-05-15-55-utc/ecomshop/index.html",
    "tienda": "online-sale-responsive-html5-ecommerce-template-2023-11-27-05-02-42-utc/onlinesale/home.html",
}

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "Templates"
DISENOS_JSON = TEMPLATES_DIR / "disenos.json"

ADDONS = [
    {"id": "pagos", "name": "Métodos de pago", "description": "Pago Nube, Mercado Pago, PayPal"},
    {"id": "dropshipping", "name": "APIs de dropshipping", "description": "Conectar con proveedores y automatizar envíos"},
    {"id": "chatbot", "name": "Chatbot", "description": "Atención automática y preguntas frecuentes"},
    {"id": "envios", "name": "Envíos", "description": "Carriers, envío Nube, cálculo por CP"},
    {"id": "api_validacion", "name": "Validación / APIs", "description": "Validación de identidad o datos"},
    {"id": "reconocimiento_facial", "name": "Reconocimiento facial", "description": "Verificación en checkout o área de clientes"},
]


def get_templates():
    """Carga los 3 diseños desde Templates/disenos.json."""
    try:
        if DISENOS_JSON.exists():
            with open(DISENOS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return [
        {"id": "minimal", "name": "Minimal", "description": "Limpio y enfocado en el producto.", "preview": ""},
        {"id": "moderno", "name": "Moderno", "description": "Diseño actual con bloques grandes.", "preview": ""},
        {"id": "tienda", "name": "Tienda clásica", "description": "Catálogo claro y categorías visibles.", "preview": ""},
    ]


def _last_user_content(messages):
    for m in reversed(messages):
        if m.get("role") == "user":
            return (m.get("content") or "").strip().lower()
    return ""


def _count_user_messages(messages):
    return sum(1 for m in messages if m.get("role") == "user")


def _is_que_vender_answer(text):
    """Detecta si el usuario está respondiendo 'qué quiero vender'."""
    if not text:
        return False
    triggers = [
        "quiero", "tienda de", "vender", "una tienda", "negocio de",
        "emprendimiento", "productos", "ropa", "zapatos", "accesorios",
        "comida", "artesanías", "electrónica", "decoración", "belleza",
    ]
    return any(t in text for t in triggers)


def _is_template_choice(text):
    """Detecta si el usuario eligió un diseño (por id o orden)."""
    if not text:
        return False
    by_id = ["minimal", "moderno", "tienda", "clásica", "clasica"]
    by_order = ["primero", "segundo", "tercero", "1", "2", "3", "uno", "dos", "tres"]
    return any(t in text for t in by_id) or any(t in text for t in by_order)


def _design_id_from_last_message(text):
    """Devuelve el id del diseño elegido (minimal, moderno, tienda)."""
    if not text:
        return "minimal"
    t = text.lower().strip()
    if t in ("minimal", "moderno", "tienda"):
        return t
    if "minimal" in t or "primero" in t or "1" in t or "uno" in t:
        return "minimal"
    if "moderno" in t or "segundo" in t or "2" in t or "dos" in t:
        return "moderno"
    if "tienda" in t or "clásica" in t or "clasica" in t or "tercero" in t or "3" in t or "tres" in t:
        return "tienda"
    return "minimal"


def run_flow(messages):
    """
    Devuelve (reply, show_templates, templates, show_addons, addons, generated_page_html, preview_path).
    preview_path es la ruta bajo Templates/ de la plantilla real para el iframe (ej. odor-buyer-file/index.html).
    """
    user_count = _count_user_messages(messages)
    last = _last_user_content(messages)

    # Paso 1: primer mensaje = respuesta a "qué te gustaría vender"
    if user_count == 1 and _is_que_vender_answer(last):
        templates = get_templates()
        reply = (
            "Perfecto. ¿Qué diseño te gusta más? Elige uno de estos tres estilos para tu tienda:"
        )
        return reply, True, templates, False, [], None, None

    # Paso 2: segundo mensaje = elección de diseño → addons y URL de plantilla real
    if user_count == 2 and _is_template_choice(last):
        addons = ADDONS
        reply = (
            "Genial. ¿Qué te gustaría agregar a tu tienda? "
            "Puedes elegir uno o varios: métodos de pago, APIs de dropshipping, chatbot, envíos, validación o reconocimiento facial."
        )
        design_id = _design_id_from_last_message(last)
        preview_path = DESIGN_TEMPLATE_PATHS.get(design_id)
        generated_page_html, _ = page_generator.generate_page_html(messages)
        return reply, False, [], True, addons, generated_page_html or None, preview_path

    return None, False, [], False, [], None, None


def flow_handles(messages):
    """True si el flujo guiado debe responder (y no el LLM)."""
    reply, _, _, _, _, _, _ = run_flow(messages)
    return reply is not None
