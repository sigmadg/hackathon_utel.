"""
Aplica instrucciones de diseño (colores, tipografía, título de tienda, etc.) a la copia
del template asociada a un chat_id. Genera custom.css y modifica el HTML de la copia.
"""
import re
import time
from pathlib import Path

from .flow_service import TEMPLATES_DIR, COPIES_SUBDIR, has_chat_copy


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

    # Título / nombre de tienda: "título X", "nombre X", "que sea X", "titulo X", "llamarla X"
    for pattern, group in [
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
    if not chat_id or not design_spec or not isinstance(design_spec, dict):
        return False, "Faltan chat_id o design_spec."
    if not has_chat_copy(chat_id):
        return False, "No hay copia del template para este chat."

    copy_dir = TEMPLATES_DIR / COPIES_SUBDIR / str(chat_id)
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
