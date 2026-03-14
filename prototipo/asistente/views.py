"""
Vistas del asistente: página de chat y API para enviar mensajes.
"""
import json
import logging
import secrets
import os
import uuid
import requests

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404, HttpResponse
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt  # solo para API JSON en prototipo

from .services.llm_service import chat
from .services.flow_service import run_flow, flow_handles, has_chat_copy, get_chat_copy_preview_path
from .services.image_handler import save_chat_images, apply_image_to_template
from .services.template_agent import run_agent
from .services.rag_service import get_context_for_query
from .services import tiendanube_api

# Agente LangChain (herramientas + LLM): activar con USE_LANGCHAIN_AGENT=true
def _use_langchain_agent():
    return os.environ.get("USE_LANGCHAIN_AGENT", "").lower() in ("1", "true", "yes")


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

    chat_id = body.get("chat_id") or str(uuid.uuid4())

    # Flujo guiado: qué vender → diseño → qué agregar
    if flow_handles(messages):
        reply, show_templates, templates, show_addons, addons, generated_page_html, preview_path = run_flow(messages, chat_id=chat_id)
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
            "chat_id": chat_id,
        })

    # Imágenes adjuntas: guardar en la copia del chat y opcionalmente aplicar como logo/encabezado
    has_copy = has_chat_copy(chat_id)
    images_data = body.get("images") or []
    saved_image_paths = []
    save_err = None
    image_apply_msg = None
    preview_path = ""
    preview_url = None

    if has_copy and images_data:
        saved_image_paths, save_err = save_chat_images(chat_id, images_data)
        if save_err and not saved_image_paths:
            pass  # opcional: devolver save_err en la respuesta
        elif saved_image_paths:
            last_user = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")
            last_lower = last_user.lower()
            role = "logo" if any(k in last_lower for k in ("logo", "como logo", "esta imagen es el logo", "usa esta como logo")) else None
            if not role and any(k in last_lower for k in ("encabezado", "banner", "cabecera", "header", "imagen del encabezado", "fondo del encabezado")):
                role = "banner"
            if role:
                ok, image_apply_msg = apply_image_to_template(chat_id, saved_image_paths[0], role=role)
                if ok:
                    preview_path = get_chat_copy_preview_path(chat_id) or ""
                    if preview_path:
                        try:
                            preview_url = request.build_absolute_uri(reverse("asistente:template_preview", args=[preview_path]))
                        except Exception:
                            pass

    last_user_message = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")

    action_result = None
    template_updated = False
    if image_apply_msg:
        action_result = {"success": True, "message": image_apply_msg, "detail": {"images_applied": True}}
        template_updated = True

    # Opción 1: Agente LangChain (herramientas + decisión del LLM) si está activado y hay copia del template
    agent_result = None
    if has_copy and _use_langchain_agent():
        try:
            from .services.langchain_agent import run_langchain_agent
            agent_result = run_langchain_agent(chat_id, last_user_message, history_messages=messages, has_copy=has_copy)
        except Exception as e:
            logger.warning("LangChain agent failed, using default flow: %s", e)
            agent_result = None

    # Opción 2: Flujo por defecto (LLM + agente que parsea ACCION)
    if agent_result is None:
        rag_context = get_context_for_query(last_user_message)
        reply_text = chat(messages, has_template_copy=has_copy, rag_context=rag_context)
        agent_result = run_agent(chat_id, reply_text, last_user_message, has_copy, request=request)

    # Mostrar siempre el mensaje del agente cuando ejecutó una orden (nunca instrucciones del LLM)
    reply_clean = agent_result.get("reply_override") or agent_result["reply_clean"]
    if agent_result.get("action_result") is not None:
        action_result = agent_result["action_result"]
        if action_result.get("success") and action_result.get("message"):
            reply_clean = (action_result["message"].rstrip(".") + ". ¿Algo más?")
    template_updated = template_updated or agent_result["template_updated"]
    if agent_result.get("preview_path"):
        preview_path = agent_result["preview_path"]
        try:
            preview_url = request.build_absolute_uri(reverse("asistente:template_preview", args=[preview_path]))
        except Exception:
            pass

    if save_err and images_data and not saved_image_paths:
        reply_clean = (save_err + "\n\n" + reply_clean) if reply_clean else save_err
    elif saved_image_paths and not image_apply_msg and reply_clean:
        reply_clean = "He guardado tu(s) imagen(es). Puedes decirme «úsala como logo» o «como imagen del encabezado» para aplicarla.\n\n" + reply_clean
    elif saved_image_paths and not image_apply_msg:
        reply_clean = "He guardado tu(s) imagen(es). Dime «úsala como logo» o «como encabezado» para aplicarla a tu tienda."

    return JsonResponse({
        "reply": reply_clean,
        "action": agent_result.get("action_normalized") or "",
        "action_result": action_result,
        "show_templates": False,
        "templates": [],
        "show_addons": False,
        "addons": [],
        "generated_page_html": None,
        "preview_url": preview_url or "",
        "preview_path": preview_path,
        "chat_id": chat_id,
        "images_saved": saved_image_paths,
        "template_updated": template_updated,
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
    if safe_path.startswith("copies/"):
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
    return response
