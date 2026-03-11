"""
Genera la página HTML de vista previa compilando solo la plantilla elegida (minimal, moderno, tienda).
No usa LLM: se rellena con el tipo de tienda que dijo el usuario y textos por defecto.
"""
from pathlib import Path

from django.conf import settings

# Carpeta Templates del prototipo (desde settings o BASE_DIR)
TEMPLATES_DIR = getattr(settings, "TIENDANUBE_TEMPLATES_DIR", None) or getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent) / "Templates"

# Plantillas HTML por diseño (placeholders: store_name, tagline, product1, product2, product3)
TEMPLATE_MINIMAL = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{store_name}}</title>
    <style>
        * { box-sizing: border-box; margin: 0; }
        body { font-family: system-ui, sans-serif; background: #fafafa; color: #111; padding: 2rem; max-width: 600px; margin: 0 auto; }
        h1 { font-size: 1.75rem; font-weight: 600; margin-bottom: 0.5rem; }
        .tagline { color: #666; margin-bottom: 2rem; font-size: 0.95rem; }
        .products { display: flex; flex-direction: column; gap: 1rem; }
        .product { background: #fff; padding: 1rem; border: 1px solid #eee; border-radius: 8px; font-weight: 500; }
    </style>
</head>
<body>
    <h1>{{store_name}}</h1>
    <p class="tagline">{{tagline}}</p>
    <div class="products">
        <div class="product">{{product1}}</div>
        <div class="product">{{product2}}</div>
        <div class="product">{{product3}}</div>
    </div>
</body>
</html>"""

TEMPLATE_MODERNO = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{store_name}}</title>
    <style>
        * { box-sizing: border-box; margin: 0; }
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #f1f5f9; min-height: 100vh; }
        .hero { background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 3rem 2rem; text-align: center; }
        h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        .tagline { color: #94a3b8; margin-bottom: 2rem; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; padding: 2rem; max-width: 900px; margin: 0 auto; }
        .card { background: #1e293b; padding: 1.25rem; border-radius: 12px; text-align: center; border: 1px solid #334155; }
    </style>
</head>
<body>
    <div class="hero">
        <h1>{{store_name}}</h1>
        <p class="tagline">{{tagline}}</p>
    </div>
    <div class="grid">
        <div class="card">{{product1}}</div>
        <div class="card">{{product2}}</div>
        <div class="card">{{product3}}</div>
    </div>
</body>
</html>"""

TEMPLATE_TIENDA = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{store_name}}</title>
    <style>
        * { box-sizing: border-box; margin: 0; }
        body { font-family: system-ui, sans-serif; background: #fff; color: #222; }
        header { background: #1a1a2e; color: #eee; padding: 1rem 2rem; }
        h1 { font-size: 1.25rem; }
        nav { background: #f5f5f5; padding: 0.5rem 2rem; border-bottom: 1px solid #ddd; }
        .products { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; padding: 2rem; }
        .product { border: 1px solid #ddd; padding: 1rem; border-radius: 6px; }
        .product strong { display: block; margin-bottom: 0.25rem; }
    </style>
</head>
<body>
    <header><h1>{{store_name}}</h1></header>
    <nav>Inicio | Productos | Contacto</nav>
    <div class="products">
        <div class="product"><strong>{{product1}}</strong> Ver más</div>
        <div class="product"><strong>{{product2}}</strong> Ver más</div>
        <div class="product"><strong>{{product3}}</strong> Ver más</div>
    </div>
</body>
</html>"""

TEMPLATES = {
    "minimal": TEMPLATE_MINIMAL,
    "moderno": TEMPLATE_MODERNO,
    "tienda": TEMPLATE_TIENDA,
}


def _load_template_file(design_id):
    """Carga la plantilla HTML desde Templates/{design_id}.html. Si no existe, usa la embebida."""
    if design_id not in ("minimal", "moderno", "tienda"):
        return TEMPLATES.get("minimal", TEMPLATE_MINIMAL)
    path = TEMPLATES_DIR / f"{design_id}.html"
    try:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if content and content.strip():
                return content
    except Exception:
        pass
    return TEMPLATES.get(design_id, TEMPLATE_MINIMAL)


def _design_id_from_message(text):
    """Mapea el mensaje del usuario al id del diseño. Si el texto es exactamente el id, se usa ese."""
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


def _store_type_from_message(text):
    """Extrae o formatea el tipo de tienda del primer mensaje para mostrar (sin LLM)."""
    if not text:
        return "Mi Tienda"
    t = text.strip()
    if not t:
        return "Mi Tienda"
    # "tienda de zapatos" -> "Tienda de zapatos"; "ropa" -> "Ropa"
    for prefix in ["tienda de ", "vender ", "negocio de ", "una tienda de ", "quiero "]:
        if t.lower().startswith(prefix):
            rest = t[len(prefix):].strip()
            if rest:
                return rest[:1].upper() + rest[1:80].lower()
    return t[:1].upper() + t[1:80].lower() if len(t) > 1 else t.upper()


def generate_page_html(messages):
    """
    Compila en el visor solo la plantilla seleccionada. No llama al LLM.
    Rellena store_name desde el primer mensaje del usuario y valores por defecto.
    """
    if not messages or _count_user(messages) < 2:
        return _default_page(), None

    first_user = _first_user_content(messages)
    second_user = _last_user_content(messages)
    design_id = _design_id_from_message(second_user)

    store_name = _store_type_from_message(first_user) or "Mi Tienda"
    tagline = "Bienvenido a tu tienda."
    product1, product2, product3 = "Producto 1", "Producto 2", "Producto 3"

    template = _load_template_file(design_id)
    html = template.replace("{{store_name}}", _escape(store_name))
    html = html.replace("{{tagline}}", _escape(tagline))
    html = html.replace("{{product1}}", _escape(product1))
    html = html.replace("{{product2}}", _escape(product2))
    html = html.replace("{{product3}}", _escape(product3))
    if not html or "{{" in html:
        html = _default_page()
    return html, None


def _escape(s):
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _count_user(messages):
    return sum(1 for m in messages if m.get("role") == "user")


def _first_user_content(messages):
    for m in messages:
        if m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""


def _last_user_content(messages):
    for m in reversed(messages):
        if m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""


def _default_page():
    return (
        _load_template_file("minimal")
        .replace("{{store_name}}", "Mi Tienda")
        .replace("{{tagline}}", "Vista previa.")
        .replace("{{product1}}", "Producto 1")
        .replace("{{product2}}", "Producto 2")
        .replace("{{product3}}", "Producto 3")
    )
