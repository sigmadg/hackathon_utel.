"""
Guarda imágenes subidas y las aplica al template en edición (logo, encabezado, productos).
Las imágenes se guardan en copies/current/uploads/; los cambios no se asocian a la conversación.
"""
import base64
import re
import uuid
from pathlib import Path

from .flow_service import has_chat_copy, get_current_copy_dir

UPLOADS_DIR = "uploads"
ALLOWED_CONTENT_TYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp")
EXT_BY_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}


def save_chat_images(chat_id, images_data):
    """
    images_data: lista de dicts con "data" (data URL base64) y opcional "name".
    Guarda en copies/current/uploads/ y devuelve (list of relative paths, error_msg).
    """
    if not images_data:
        return [], None
    if not has_chat_copy():
        return [], "Primero elige un diseño de tienda para poder agregar imágenes."
    if not isinstance(images_data, list):
        return [], "Formato de imágenes inválido."

    copy_dir = get_current_copy_dir()
    uploads_dir = copy_dir / UPLOADS_DIR
    uploads_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for i, item in enumerate(images_data):
        if not isinstance(item, dict):
            continue
        data_url = item.get("data") or item.get("content")
        if not data_url or not isinstance(data_url, str):
            continue
        match = re.match(r"data:([^;]+);base64,(.+)", data_url.strip())
        if not match:
            continue
        content_type = match.group(1).strip().lower().split(";")[0]
        if content_type not in ALLOWED_CONTENT_TYPES and not content_type.startswith("image/"):
            continue
        ext = EXT_BY_TYPE.get(content_type) or ".png"
        try:
            b64 = match.group(2)
            raw = base64.b64decode(b64, validate=True)
        except Exception:
            continue
        name = (item.get("name") or f"image_{i+1}").strip()
        if not name.endswith(tuple(EXT_BY_TYPE.values())):
            name = f"{uuid.uuid4().hex[:8]}{ext}"
        else:
            name = re.sub(r"[^\w.\-]", "_", name)[:80]
        file_path = uploads_dir / name
        try:
            file_path.write_bytes(raw)
        except Exception as e:
            return paths, str(e)
        paths.append(f"{UPLOADS_DIR}/{name}")

    return paths, None


def apply_image_to_template(chat_id, image_relative_path, role="logo"):
    """
    Actualiza el HTML del template en edición para usar la imagen en el rol indicado.
    role: "logo" | "banner" | "header" (encabezado) | "product"
    """
    if not image_relative_path or not has_chat_copy():
        return False, "Faltan datos o no hay template seleccionado."
    copy_dir = get_current_copy_dir()
    if not (copy_dir / image_relative_path.lstrip("/")).exists():
        return False, "Imagen no encontrada en la copia."

    path_clean = image_relative_path.replace("\\", "/").lstrip("/")
    updated = 0

    # Solo modificar la pantalla principal (index o home)
    main_entries = ["index.html", "home.html"]
    html_path = None
    for entry in main_entries:
        p = copy_dir / entry
        if p.exists():
            html_path = p
            break
    if html_path:
        content = html_path.read_text(encoding="utf-8")
        file_updated = False

        if role == "logo":
            # Logo: main__logo img (odor-buyer) o primer img con logo en el header
            new_content, n = re.subn(
                r'(<a[^>]+class="[^"]*main__logo[^"]*"[^>]*>\s*<img\s+src=")[^"]*(")',
                rf'\g<1>{re.escape(path_clean)}\g<2>',
                content,
                count=1,
                flags=re.I,
            )
            if n:
                content = new_content
                file_updated = True
            if not file_updated:
                new_content, n = re.subn(
                    r'(<img\s+src=")[^"]*("[^>]*alt="[^"]*logo[^"]*")',
                    rf'\g<1>{re.escape(path_clean)}\g<2>',
                    content,
                    count=1,
                    flags=re.I,
                )
                if n:
                    content = new_content
                    file_updated = True
            if not file_updated and "logo" in content.lower():
                # Cualquier img que tenga logo en la ruta o en alt
                new_content, n = re.subn(
                    r'src="(assets/images/logo/[^"]+)"',
                    f'src="{re.escape(path_clean)}"',
                    content,
                    count=1,
                )
                if n:
                    content = new_content
                    file_updated = True

        elif role in ("banner", "header"):
            # Primera imagen de banner/background
            new_content, n = re.subn(
                r'(data-background=")[^"]*(")',
                rf'\g<1>{re.escape(path_clean)}\g<2>',
                content,
                count=1,
            )
            if n:
                content = new_content
                file_updated = True

        if file_updated:
            html_path.write_text(content, encoding="utf-8")
            updated += 1

    if updated:
        return True, "Imagen aplicada al template. Revisa la vista previa."
    return True, "Imagen guardada. Si no ves el cambio, indica 'como logo' o 'como encabezado'."
