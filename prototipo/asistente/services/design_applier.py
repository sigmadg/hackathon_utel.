"""
Aplica instrucciones de diseño (colores, tipografía, título de tienda, etc.) a la copia
del template asociada a un chat_id. Genera custom.css y modifica el HTML de la copia.
"""
import re
import time
from pathlib import Path

from .flow_service import TEMPLATES_DIR, COPIES_SUBDIR, has_chat_copy, get_current_copy_dir


def _normalize_color(value):
    """Acepta hex con o sin #, nombres básicos; devuelve hex con #."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if v.startswith("#"):
        return v if len(v) in (4, 7) else "#" + v[:6]
    # Nombres comunes a hex
    names = {
        "negro": "#000000", "black": "#000000",
        "blanco": "#ffffff", "white": "#ffffff",
        "azul": "#2563eb", "blue": "#2563eb",
        "rojo": "#dc2626", "red": "#dc2626",
        "rosa": "#ff69b4", "pink": "#ff69b4", "rosado": "#ff69b4",
        "verde": "#16a34a", "green": "#16a34a",
        "amarillo": "#eab308", "yellow": "#eab308",
        "naranja": "#ea580c", "orange": "#ea580c",
        "gris": "#6b7280", "gray": "#6b7280", "grey": "#6b7280",
    }
    return names.get(v.lower()) or (v if v.startswith("#") else "#" + v[:6])


# Mapeo nombre -> hex para extraer del mensaje del usuario
COLOR_NAMES = {
    "negro": "#000000", "black": "#000000", "blanco": "#ffffff", "white": "#ffffff",
    "azul": "#2563eb", "blue": "#2563eb", "rojo": "#dc2626", "red": "#dc2626",
    "rosa": "#ff69b4", "pink": "#ff69b4", "rosado": "#ff69b4",
    "verde": "#16a34a", "green": "#16a34a", "amarillo": "#eab308", "yellow": "#eab308",
    "naranja": "#ea580c", "orange": "#ea580c", "gris": "#6b7280", "gray": "#6b7280",
}


def parse_user_design_intent(user_message):
    """
    Extrae intención de diseño (título, colores) del mensaje del usuario.
    Devuelve un dict para apply_design_to_copy o None si no hay nada que aplicar.
    Así, con cada instrucción podemos aplicar cambios aunque el LLM no devuelva JSON.
    """
    if not user_message or not isinstance(user_message, str):
        return None
    text = user_message.strip().lower()
    if len(text) < 2:
        return None
    spec = {}

    # Título / nombre de tienda: "título X", "nombre X", "quiero título X", "que sea X", "titulo X"
    for pattern, group in [
        (r"quiero\s+(?:el\s+)?t[ií]tulo\s+[\"']?([^\"'\n.,]+)[\"']?", 1),
        (r"t[ií]tulo\s+(?:sea\s+)?[\"']?([^\"'\n.,]+)[\"']?", 1),
        (r"nombre\s+(?:de\s+la\s+tienda\s+)?[\"']?([^\"'\n.,]+)[\"']?", 1),
        (r"(?:que\s+sea|ll[aá]mal[oa])\s+[\"']?([^\"'\n.,]+)[\"']?", 1),
        (r"titulo\s+([^\n,]+?)(?:\s+y\s+|\s*,\s*|$)", 1),
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            name = m.group(group).strip()[:80]
            if name and name not in ("y", "o", "el", "la", "los", "las"):
                spec["store_name"] = name
                break

    # Colores: "azul", "rojo y rosa", "colores rojo y rosa", "color azul", "fondo verde", "cambia a azul"
    colors_found = []
    for word, hex_val in COLOR_NAMES.items():
        if word in text:
            colors_found.append(hex_val)
    if not colors_found and re.search(r"#([0-9a-fA-F]{3,6})\b", text):
        for m in re.finditer(r"#([0-9a-fA-F]{3,6})\b", text):
            colors_found.append("#" + (m.group(1) if len(m.group(1)) >= 6 else m.group(1) * 2)[:6])
    if colors_found:
        spec["primary_color"] = colors_found[0]
        if len(colors_found) > 1:
            spec["secondary_color"] = colors_found[1]
        if len(colors_found) > 2:
            spec["background_color"] = colors_found[2]
        if "fondo" in text and colors_found:
            spec["background_color"] = colors_found[0]
            if len(colors_found) > 1:
                spec["primary_color"] = colors_found[1]

    # Idioma: "español", "ajustar idioma", "en español", etc.
    if any(k in text for k in (
        "español", "espanol", "en español", "idioma español", "cambiar idioma",
        "ajustar idioma", "ajustar el idioma", "pon en español", "traducir al español",
        "que sea en español", "en castellano", "todo en español"
    )):
        spec["language"] = "es"

    if spec:
        if "background_color" not in spec and spec.get("primary_color"):
            spec["background_color"] = "#f8fafc"
        return spec
    return None


def _main_entry_path(copy_dir):
    """Ruta del archivo principal (solo index o home) para aplicar cambios del LLM."""
    for entry in ("index.html", "home.html"):
        if (copy_dir / entry).exists():
            return copy_dir / entry
    return None


# Traducción inglés -> español (cadenas más largas primero para no pisar reemplazos)
EN_TO_ES = (
    ("Search for", "Buscar"),
    ("My Account", "Mi cuenta"),
    ("Contact Us", "Contáctanos"),
    ("Home One Light", "Inicio claro"),
    ("Home Two Light", "Inicio 2 claro"),
    ("Home One", "Inicio"),
    ("Home Two", "Inicio 2"),
    ("Home", "Inicio"),
    ("Shop Leftbar", "Tienda"),
    ("Shop Rightbar", "Tienda"),
    ("Shop Single", "Producto"),
    ("Shop Now", "Comprar ahora"),
    ("Shop", "Tienda"),
    ("Cart Page", "Carrito"),
    ("Cart", "Carrito"),
    ("Login", "Iniciar sesión"),
    ("Register", "Registrarse"),
    ("Add to Cart", "Añadir al carrito"),
    ("Add to cart", "Añadir al carrito"),
    ("View cart", "Ver carrito"),
    ("Checkout", "Finalizar compra"),
    ("Search", "Buscar"),
    ("Contact", "Contacto"),
    ("About Us", "Nosotros"),
    ("Blog", "Blog"),
    ("Welcome", "Bienvenido"),
    ("Categories", "Categorías"),
    ("Price", "Precio"),
    ("Sort by", "Ordenar por"),
    ("New Arrivals", "Novedades"),
    ("Best Sellers", "Más vendidos"),
    ("Sale", "Oferta"),
    ("Free Shipping", "Envío gratis"),
    ("Subscribe", "Suscribirse"),
    ("Newsletter", "Newsletter"),
    ("Submit", "Enviar"),
    ("Read More", "Leer más"),
    ("Back to shop", "Volver a la tienda"),
    ("Your cart", "Tu carrito"),
    ("Empty cart", "Carrito vacío"),
    ("Continue shopping", "Seguir comprando"),
)


def _apply_language_to_html(copy_dir, language):
    """Aplica el idioma (ej. es) a la pantalla principal: lang en <html> y textos traducidos."""
    if not language or str(language).lower() not in ("es", "español", "spanish"):
        return
    html_path = _main_entry_path(copy_dir)
    if not html_path:
        return
    content = html_path.read_text(encoding="utf-8")
    if re.search(r"<html\b", content, re.I):
        content = re.sub(r'\blang="[^"]*"', 'lang="es"', content, count=1)
    if 'lang="' not in content[:350]:
        content = content.replace("<html>", "<html lang=\"es\">", 1)
        content = re.sub(r"<html\s+", "<html lang=\"es\" ", content, count=1)
    for en, es in EN_TO_ES:
        content = content.replace(en, es)
    html_path.write_text(content, encoding="utf-8")


def _apply_store_name_to_html(copy_dir, store_name):
    """Reemplaza el título y el nombre visible solo en la pantalla principal (index o home)."""
    if not store_name or not isinstance(store_name, str):
        return
    name = store_name.strip()[:200]
    if not name:
        return
    html_path = _main_entry_path(copy_dir)
    if not html_path:
        return
    escaped = _escape_html(name)
    content = html_path.read_text(encoding="utf-8")
    content = re.sub(r"<title>\s*[^<]*\s*</title>", f"<title>{escaped}</title>", content, count=1, flags=re.I)
    content = re.sub(
        r'(<a[^>]+class="[^"]*main__logo[^"]*"[^>]*>\s*<img\s+[^>]*alt=")[^"]*(")',
        rf'\g<1>{escaped}\g<2>',
        content,
        count=1,
        flags=re.I,
    )
    content = re.sub(r"(<h1[^>]*>)\s*[^<]*(\s*</h1>)", rf"\g<1>{escaped}\g<2>", content, count=1, flags=re.I)
    html_path.write_text(content, encoding="utf-8")


def _escape_html(s):
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def apply_design_to_copy(chat_id, design_spec):
    """
    Aplica el design_spec a la copia del template del chat.
    design_spec: dict con optional keys: store_name, primary_color, secondary_color,
                 background_color, heading_color, text_color, font_family, etc.
    Devuelve (éxito: bool, mensaje: str).
    """
    if not design_spec or not isinstance(design_spec, dict):
        return False, "Falta design_spec."
    if not has_chat_copy():
        return False, "No hay template seleccionado. Elige un diseño primero."

    copy_dir = get_current_copy_dir()
    if not copy_dir.is_dir():
        return False, "Copia no encontrada."

    # Aplicar nombre/título de tienda al HTML
    store_name = design_spec.get("store_name") or design_spec.get("title") or design_spec.get("nombre_tienda")
    if store_name:
        _apply_store_name_to_html(copy_dir, store_name)

    # Aplicar idioma (ej. español) a la pantalla principal
    language = design_spec.get("language") or design_spec.get("idioma") or design_spec.get("lang")
    if language:
        _apply_language_to_html(copy_dir, language)

    # Dónde escribir custom.css: la copia puede tener assets/css/ o css/
    css_dir = copy_dir / "assets" / "css"
    if not css_dir.exists():
        css_dir = copy_dir / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    custom_css_path = css_dir / "custom.css"

    # Ruta relativa desde el HTML (index.html está en copy_dir; los CSS en assets/css o css)
    if (copy_dir / "assets").exists():
        css_href = "assets/css/custom.css"
    else:
        css_href = "css/custom.css"

    # Conservar valores actuales del CSS si el spec es parcial (ej. solo store_name)
    merged = dict(design_spec)
    if custom_css_path.exists():
        try:
            current = custom_css_path.read_text(encoding="utf-8")
            for var, key in [("--primary-color", "primary_color"), ("--secondary-color", "secondary_color"), ("--sub-bg", "background_color")]:
                m = re.search(rf"{re.escape(var)}\s*:\s*([^;}}]+)", current)
                if m and key not in merged:
                    merged[key] = m.group(1).strip()
        except Exception:
            pass

    primary = _normalize_color(merged.get("primary_color") or merged.get("primary"))
    secondary = _normalize_color(merged.get("secondary_color") or merged.get("secondary"))
    background = _normalize_color(merged.get("background_color") or merged.get("background"))
    heading = _normalize_color(merged.get("heading_color") or merged.get("heading"))
    text = _normalize_color(merged.get("text_color") or merged.get("text"))
    font = (merged.get("font_family") or merged.get("font") or "").strip() or None

    lines = ["/* Personalización por instrucciones del usuario */", ""]

    # Variables CSS (templates como odor-buyer las usan)
    if primary:
        lines.append(f":root {{ --primary-color: {primary}; }}")
    if secondary:
        lines.append(f":root {{ --secondary-color: {secondary}; }}")
    if background:
        lines.append(f":root {{ --sub-bg: {background}; }}")
    if heading:
        lines.append(f":root {{ --heading-color: {heading}; }}")
    if text:
        lines.append(f":root {{ --paragraph: {text}; }}")

    # Overrides genéricos por si el template no usa variables
    if background:
        lines.append(f"body {{ background-color: {background} !important; }}")
    if primary:
        lines.append(f"a, .btn-primary, button.primary {{ color: {primary} !important; }}")
        lines.append(f".btn-primary, button.primary {{ background-color: {primary} !important; border-color: {primary}; }}")
    if secondary:
        lines.append(f".header, header, .top__header {{ background-color: {secondary} !important; }}")
    if heading:
        lines.append(f"h1, h2, h3, .heading {{ color: {heading} !important; }}")
    if text:
        lines.append(f"body, p {{ color: {text} !important; }}")
    if font:
        lines.append(f'body {{ font-family: {font}, sans-serif !important; }}')

    custom_css_path.write_text("\n".join(lines), encoding="utf-8")

    # Cache-bust para que el navegador cargue siempre el CSS nuevo
    css_href_bust = f"{css_href}?v={int(time.time() * 1000)}"

    # Inyectar o actualizar link a custom.css solo en la pantalla principal
    html_path = _main_entry_path(copy_dir)
    if html_path:
        content = html_path.read_text(encoding="utf-8")
        if css_href in content or "custom.css" in content:
            content = re.sub(
                r'<link\s+rel="stylesheet"\s+href="[^"]*custom\.css[^"]*"\s*>',
                f'    <link rel="stylesheet" href="{css_href_bust}">',
                content,
                count=1,
                flags=re.I,
            )
        else:
            inject = f'    <link rel="stylesheet" href="{css_href_bust}">\n</head>'
            if "</head>" in content:
                content = content.replace("</head>", inject, 1)
        html_path.write_text(content, encoding="utf-8")

    return True, "Diseño aplicado a tu tienda. Revisa la vista previa."


def _inject_payment_apis_config(content):
    """Inyecta en el HTML el bloque de APIs de pago configuradas (Mercado Pago, PayPal, Pago Nube)."""
    config_block = """<!-- APIs de pago configuradas por el agente -->
<div id="payment-apis-config" style="margin:16px auto;max-width:600px;padding:12px 16px;background:#f0fdf4;border:1px solid #16a34a;border-radius:8px;font-size:14px;color:#166534;">
  <strong>Métodos de pago integrados</strong>: Mercado Pago, PayPal, Pago Nube. APIs configuradas en esta tienda.
</div>
<script id="payment-apis-script">/* Configuración de pasarelas: mercadopago, paypal, pago-nube */</script>
"""
    # Insertar antes de </body>
    if "</body>" in content and "payment-apis-config" not in content:
        content = content.replace("</body>", config_block + "\n</body>", 1)
    return content


def _inject_payment_methods_in_cart(content):
    """
    Añade los métodos de pago en la zona del botón del carrito del header.
    Inserta un indicador "Mercado Pago · PayPal · Pago Nube" junto al carrito.
    """
    if "payment-methods-at-cart" in content:
        return content
    cart_badge = (
        '<span id="payment-methods-at-cart" class="ms-2" style="'
        "font-size:11px;color:#16a34a;white-space:nowrap;border-left:1px solid rgba(0,0,0,.1);padding-left:8px;"
        '" title="Métodos de pago: Mercado Pago, PayPal, Pago Nube">'
        "✓ Mercado Pago · PayPal · Pago Nube</span>"
    )
    # Solo si existe el bloque del carrito en el header (cart__icon + span.one)
    if "cart__icon" not in content or 'class="one"' not in content:
        return content
    # Insertar después del primer <span class="one">0</span> que sigue a cart__icon (es el del header)
    pattern = r'(<span\s+class="one">\s*\d+\s*</span>\s*)(</div>\s*<div\s+class="flag__wrap">)'
    match = re.search(pattern, content)
    if match:
        content = content[: match.start()] + match.group(1) + cart_badge + "\n                        " + match.group(2) + content[match.end() :]
    else:
        # Fallback: primer </span> de span.one seguido de </div>
        pattern2 = r'(<span\s+class="one">\s*\d+\s*</span>\s*)(</div>)'
        match2 = re.search(pattern2, content)
        if match2:
            content = content[: match2.start()] + match2.group(1) + cart_badge + "\n                    " + match2.group(2) + content[match2.end() :]
    return content


# Textos y estilos para el badge de integración (pagos, chatbot, dropshipping)
INTEGRATION_BADGES = {
    "pagos": {
        "label": "Métodos de pago integrados",
        "bg": "#16a34a",
        "color": "#fff",
    },
    "chatbot": {
        "label": "Chat disponible",
        "bg": "#0ea5e9",
        "color": "#fff",
    },
    "dropshipping": {
        "label": "Dropshipping activo",
        "bg": "#8b5cf6",
        "color": "#fff",
    },
}


def apply_integration_badge(chat_id, integration_type):
    """
    Añade un indicador visible en el template en edición (pantalla principal)
    para pagos, chatbot o dropshipping. Los cambios se aplican en copies/current/, no por conversación.
    Devuelve (éxito: bool, mensaje: str).
    """
    if not has_chat_copy():
        return False, "No hay template seleccionado. Elige un diseño primero."
    info = INTEGRATION_BADGES.get(integration_type)
    if not info:
        return False, f"Tipo de integración desconocido: {integration_type}."

    copy_dir = get_current_copy_dir()
    html_path = _main_entry_path(copy_dir)
    if not html_path:
        return False, "No se encontró la pantalla principal del template."

    content = html_path.read_text(encoding="utf-8")
    label = info["label"]
    bg = info["bg"]
    color = info["color"]
    id_attr = f"integration-badge-{integration_type}"

    # Ya existe un badge de esta integración: no duplicar
    if id_attr in content:
        return True, "Integración ya mostrada en la vista previa."

    # Bloque HTML del badge (barra llamativa arriba)
    new_badge = (
        f'<div id="{id_attr}" style="'
        "position:relative;z-index:9999;padding:8px 16px;text-align:center;"
        f"background:{bg};color:{color};font-size:14px;font-weight:600;"
        'box-shadow:0 2px 8px rgba(0,0,0,.15);">'
        f"✓ {label}</div>"
    )

    # Contenedor de badges: si existe, insertar dentro; si no, crear después de <body>
    if "integration-badges" in content:
        # Añadir badge justo después de la apertura del contenedor
        content = re.sub(
            r'(<div\s+id="integration-badges"[^>]*>)',
            r'\1' + new_badge,
            content,
            count=1,
            flags=re.I,
        )
    else:
        # Crear contenedor justo después de <body> o <body ...>
        container = f'<div id="integration-badges">{new_badge}</div>'
        content = re.sub(r"<body(\s[^>]*)?>", r"<body\g<1>>\n" + container, content, count=1, flags=re.I)
        if container not in content:
            content = content.replace("<body>", "<body>\n" + container, 1)

    # Para pagos: métodos de pago en el botón del carrito + bloque de APIs configuradas
    if integration_type == "pagos":
        if "payment-methods-at-cart" not in content:
            content = _inject_payment_methods_in_cart(content)
        if "payment-apis-config" not in content:
            content = _inject_payment_apis_config(content)

    html_path.write_text(content, encoding="utf-8")
    if integration_type == "pagos":
        return True, "Ya se integraron los métodos de pago en tu tienda. Revisa la vista previa."
    return True, "Se implementó el cambio en tu tienda. Revisa la vista previa."
