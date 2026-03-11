"""
Vistas del asistente: página de chat y API para enviar mensajes.
"""
import json
import secrets
import os
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404, HttpResponse
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt  # solo para API JSON en prototipo

from .services.llm_service import chat, extract_action
from .services.intent_handler import execute_action
from .services.flow_service import run_flow, flow_handles
from .services import tiendanube_api


@ensure_csrf_cookie
def chat_page(request):
    """Página principal con la interfaz de chat."""
    return render(request, 'asistente/chat.html')


@require_http_methods(["GET"])
def api_tiendanube_status(request):
    """
    GET /api/tiendanube-status/
    Devuelve { "connected": bool, "store": {...}|null, "error": str|null,
               "counts": { "products", "orders", "scripts", "carriers" } }
    """
    if not tiendanube_api.is_configured(request):
        return JsonResponse({
            "connected": False,
            "store": None,
            "error": "Conecta tu tienda con Tiendanube (OAuth) o configura TIENDANUBE_ACCESS_TOKEN y TIENDANUBE_STORE_ID en .env",
            "counts": {},
            "oauth_available": _oauth_app_configured(),
        })

    store, err = tiendanube_api.get_store(request=request)
    if err or not store:
        return JsonResponse({
            "connected": False,
            "store": None,
            "error": err or "No se pudo obtener la tienda",
            "counts": {},
            "oauth_available": _oauth_app_configured(),
        })

    counts = {}
    prods, _ = tiendanube_api.list_products(request=request, per_page=1, page=1)
    if isinstance(prods, list):
        counts["products_page"] = len(prods)
    orders, _ = tiendanube_api.list_orders(request=request, per_page=1, page=1)
    if isinstance(orders, list):
        counts["orders_page"] = len(orders)
    scripts, _ = tiendanube_api.list_scripts(request=request)
    if isinstance(scripts, list):
        counts["scripts"] = len(scripts)
    carriers, _ = tiendanube_api.list_shipping_carriers(request=request)
    if isinstance(carriers, list):
        counts["carriers"] = len(carriers)

    name = store.get("name")
    if isinstance(name, dict):
        name = name.get("es") or name.get("en") or next(iter(name.values()), "")
    return JsonResponse({
        "connected": True,
        "store": {"id": store.get("id"), "name": name, "country": store.get("country")},
        "error": None,
        "counts": counts,
        "oauth_available": _oauth_app_configured(),
    })


@require_http_methods(["POST"])
@csrf_exempt
def api_chat(request):
    """
    API: POST con JSON { "messages": [ {"role": "user"|"assistant", "content": "..." } ] }
    Devuelve { "reply": "...", "action": "...", "action_result": {...},
               "show_templates": bool, "templates": [...], "show_addons": bool, "addons": [...] }
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    messages = body.get("messages") or []
    if not isinstance(messages, list):
        return JsonResponse({"error": "messages debe ser una lista"}, status=400)

    # Flujo guiado: qué vender → diseño → qué agregar
    if flow_handles(messages):
        reply, show_templates, templates, show_addons, addons, generated_page_html, preview_path = run_flow(messages)
        preview_url = None
        if preview_path:
            try:
                preview_url = request.build_absolute_uri(reverse("asistente:template_preview", args=[preview_path]))
            except Exception:
                pass
        return JsonResponse({
            "reply": reply,
            "action": None,
            "action_result": None,
            "show_templates": show_templates,
            "templates": templates,
            "show_addons": show_addons,
            "addons": addons,
            "generated_page_html": generated_page_html,
            "preview_url": preview_url,
            "preview_path": preview_path or "",
        })

    # Respuesta normal por LLM
    reply_text = chat(messages)
    action = extract_action(reply_text)

    reply_clean = "\n".join(
        line for line in reply_text.splitlines()
        if not line.strip().upper().startswith("ACCION:")
    ).strip()

    action_result = None
    if action and action != "otro":
        ok, msg, detail = execute_action(action, context={"request": request})
        action_result = {"success": ok, "message": msg, "detail": detail}

    return JsonResponse({
        "reply": reply_clean,
        "action": action,
        "action_result": action_result,
        "show_templates": False,
        "templates": [],
        "show_addons": False,
        "addons": [],
        "generated_page_html": None,
        "preview_url": None,
        "preview_path": "",
    })


def _oauth_app_configured():
    app_id = getattr(settings, "TIENDANUBE_APP_ID", "") or os.environ.get("TIENDANUBE_APP_ID", "")
    secret = getattr(settings, "TIENDANUBE_CLIENT_SECRET", "") or os.environ.get("TIENDANUBE_CLIENT_SECRET", "")
    redirect_uri = getattr(settings, "TIENDANUBE_REDIRECT_URI", "") or os.environ.get("TIENDANUBE_REDIRECT_URI", "")
    return bool(app_id.strip() and secret.strip() and redirect_uri.strip())


@require_http_methods(["GET"])
def tiendanube_oauth_authorize(request):
    if not _oauth_app_configured():
        return JsonResponse({"error": "OAuth no configurado. Define TIENDANUBE_APP_ID, TIENDANUBE_CLIENT_SECRET y TIENDANUBE_REDIRECT_URI en .env"}, status=400)
    app_id = (getattr(settings, "TIENDANUBE_APP_ID", None) or os.environ.get("TIENDANUBE_APP_ID", "")).strip()
    domain = getattr(settings, "TIENDANUBE_OAUTH_DOMAIN", None) or os.environ.get("TIENDANUBE_OAUTH_DOMAIN", "https://www.tiendanube.com")
    domain = domain.rstrip("/")
    state = secrets.token_urlsafe(32)
    request.session["tiendanube_oauth_state"] = state
    auth_url = f"{domain}/apps/{app_id}/authorize?state={state}"
    return redirect(auth_url)


@require_http_methods(["GET"])
def tiendanube_oauth_callback(request):
    state = request.GET.get("state")
    code = request.GET.get("code")
    if not code:
        return render(request, "asistente/oauth_error.html", {"error": "Falta el parámetro code."})
    saved_state = request.session.get("tiendanube_oauth_state")
    if state != saved_state:
        return render(request, "asistente/oauth_error.html", {"error": "Estado inválido (CSRF)."})
    app_id = (getattr(settings, "TIENDANUBE_APP_ID", None) or os.environ.get("TIENDANUBE_APP_ID", "")).strip()
    client_secret = (getattr(settings, "TIENDANUBE_CLIENT_SECRET", None) or os.environ.get("TIENDANUBE_CLIENT_SECRET", "")).strip()
    redirect_uri = (getattr(settings, "TIENDANUBE_REDIRECT_URI", None) or os.environ.get("TIENDANUBE_REDIRECT_URI", "")).strip()
    if not app_id or not client_secret or not redirect_uri:
        return render(request, "asistente/oauth_error.html", {"error": "OAuth no configurado."})
    token_url = "https://www.tiendanube.com/apps/authorize/token"
    payload = {"client_id": app_id, "client_secret": client_secret, "grant_type": "authorization_code", "code": code}
    try:
        r = requests.post(token_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return render(request, "asistente/oauth_error.html", {"error": str(e)})
    access_token = data.get("access_token")
    user_id = data.get("user_id") or data.get("store_id")
    if not access_token or not user_id:
        return render(request, "asistente/oauth_error.html", {"error": "Falta access_token o user_id en la respuesta."})
    request.session["tiendanube_access_token"] = access_token
    request.session["tiendanube_store_id"] = str(user_id)
    request.session.pop("tiendanube_oauth_state", None)
    return redirect("asistente:chat_page")


# --- Vista previa de plantillas reales (iframe) ---

@xframe_options_exempt
@require_http_methods(["GET"])
def serve_template_preview(request, path):
    """
    Sirve archivos estáticos desde Templates/ para que el iframe del visor
    cargue las plantillas reales (odor-buyer-file, ecomshop, onlinesale) con CSS/JS relativos.
    """
    from pathlib import Path
    import mimetypes

    templates_dir = getattr(settings, "TIENDANUBE_TEMPLATES_DIR", None) or (getattr(settings, "BASE_DIR", None) and settings.BASE_DIR / "Templates")
    if not templates_dir:
        raise Http404("Templates dir not configured")
    templates_dir = Path(templates_dir).resolve()
    # Normalizar path: sin .. y sin arrancar por /
    safe_path = path.strip("/").replace("..", "")
    if not safe_path:
        safe_path = "index.html"
    full_path = (templates_dir / safe_path).resolve()
    if not str(full_path).startswith(str(templates_dir)):
        raise Http404("Invalid path")
    if full_path.is_dir():
        full_path = full_path / "index.html"
    if not full_path.is_file():
        raise Http404("Not found")
    content_type, _ = mimetypes.guess_type(str(full_path))
    content_type = content_type or "application/octet-stream"
    try:
        with open(full_path, "rb") as f:
            content = f.read()
    except (OSError, IOError):
        raise Http404("Cannot read file")
    response = HttpResponse(content, content_type=content_type)
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response
