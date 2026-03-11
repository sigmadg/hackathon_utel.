"""
Cliente para la API de Tiendanube/Nuvemshop.
Documentación: https://tiendanube.github.io/api-documentation/
Todas las URLs usan: https://api.tiendanube.com/2025-03/{store_id}/...
Soporta credenciales por .env o por sesión (tras OAuth). Header: Authentication: bearer <token>.
"""
import os
import requests
from django.conf import settings

USER_AGENT = "Asistente Tienda Hackathon (https://github.com)"


def get_credentials(request=None):
    """
    Devuelve dict con access_token y store_id.
    Si request tiene sesión con tiendanube_access_token y tiendanube_store_id, los usa.
    Si no, usa variables de entorno / settings.
    """
    if request and getattr(request, "session", None):
        token = request.session.get("tiendanube_access_token")
        store_id = request.session.get("tiendanube_store_id")
        if token and store_id:
            return {"access_token": token, "store_id": str(store_id)}
    return {
        "access_token": (
            getattr(settings, "TIENDANUBE_ACCESS_TOKEN", None)
            or os.environ.get("TIENDANUBE_ACCESS_TOKEN", "")
        ),
        "store_id": (
            getattr(settings, "TIENDANUBE_STORE_ID", None)
            or os.environ.get("TIENDANUBE_STORE_ID", "")
        ),
    }


def _token(credentials=None):
    if credentials:
        return credentials.get("access_token") or ""
    return (
        getattr(settings, "TIENDANUBE_ACCESS_TOKEN", None)
        or os.environ.get("TIENDANUBE_ACCESS_TOKEN", "")
    )


def _store_id(credentials=None):
    if credentials:
        return credentials.get("store_id") or ""
    return (
        getattr(settings, "TIENDANUBE_STORE_ID", None)
        or os.environ.get("TIENDANUBE_STORE_ID", "")
    )


def _api_base():
    base = (
        getattr(settings, "TIENDANUBE_API_BASE", None)
        or os.environ.get("TIENDANUBE_API_BASE", "https://api.tiendanube.com/2025-03")
    )
    return base.rstrip("/")


def _base_url(credentials=None):
    store_id = _store_id(credentials)
    if not store_id:
        return None
    return f"{_api_base()}/{store_id}"


def get_headers(credentials=None):
    return {
        "Content-Type": "application/json",
        "Authentication": f"bearer {_token(credentials)}",
        "User-Agent": USER_AGENT,
    }


def get_store_id(credentials=None):
    return _store_id(credentials)


def is_configured(request=None):
    """True si hay token y store_id (de sesión o de .env)."""
    creds = get_credentials(request) if request else None
    return bool(_token(creds) and _store_id(creds))


def _request(method, path, credentials=None, **kwargs):
    base = _base_url(credentials)
    if not base:
        return None, "TIENDANUBE_STORE_ID no configurado"
    url = f"{base}/{path.lstrip('/')}"
    kwargs.setdefault("timeout", 15)
    kwargs.setdefault("headers", get_headers(credentials))
    try:
        r = requests.request(method, url, **kwargs)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return {}, None
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)


# --- Store ---
def get_store(request=None):
    creds = get_credentials(request) if request else None
    return _request("GET", "store", credentials=creds)


# --- Products ---
def list_products(request=None, page=1, per_page=30, **params):
    creds = get_credentials(request) if request else None
    params.setdefault("page", page)
    params.setdefault("per_page", per_page)
    return _request("GET", "products", credentials=creds, params=params)


def get_product(product_id, request=None, fields=None):
    creds = get_credentials(request) if request else None
    path = f"products/{product_id}"
    if fields:
        return _request("GET", path, credentials=creds, params={"fields": fields})
    return _request("GET", path, credentials=creds)


def create_product(data, request=None):
    creds = get_credentials(request) if request else None
    return _request("POST", "products", credentials=creds, json=data)


# --- Categories ---
def list_categories(request=None, page=1, per_page=200, **params):
    creds = get_credentials(request) if request else None
    params.setdefault("page", page)
    params.setdefault("per_page", per_page)
    return _request("GET", "categories", credentials=creds, params=params)


def get_category(category_id, request=None):
    creds = get_credentials(request) if request else None
    return _request("GET", f"categories/{category_id}", credentials=creds)


def create_category(data, request=None):
    creds = get_credentials(request) if request else None
    return _request("POST", "categories", credentials=creds, json=data)


# --- Orders ---
def list_orders(request=None, page=1, per_page=30, **params):
    creds = get_credentials(request) if request else None
    params.setdefault("page", page)
    params.setdefault("per_page", per_page)
    return _request("GET", "orders", credentials=creds, params=params)


def get_order(order_id, request=None):
    creds = get_credentials(request) if request else None
    return _request("GET", f"orders/{order_id}", credentials=creds)


# --- Customers ---
def list_customers(request=None, page=1, per_page=30, **params):
    creds = get_credentials(request) if request else None
    params.setdefault("page", page)
    params.setdefault("per_page", per_page)
    return _request("GET", "customers", credentials=creds, params=params)


# --- Scripts ---
def list_scripts(request=None):
    creds = get_credentials(request) if request else None
    return _request("GET", "scripts", credentials=creds)


def create_script(name, src, description="", request=None):
    creds = get_credentials(request) if request else None
    payload = {"name": name, "src": src, "description": description or name}
    return _request("POST", "scripts", credentials=creds, json=payload)


# --- Webhooks ---
def list_webhooks(request=None):
    creds = get_credentials(request) if request else None
    data, err = _request("GET", "webhooks", credentials=creds)
    if err:
        return [], err
    return (data if isinstance(data, list) else []), None


def create_webhook(url_callback, event, request=None):
    creds = get_credentials(request) if request else None
    return _request("POST", "webhooks", credentials=creds, json={"url": url_callback, "event": event})


# --- Coupons ---
def list_coupons(request=None, page=1, per_page=30, **params):
    creds = get_credentials(request) if request else None
    params.setdefault("page", page)
    params.setdefault("per_page", per_page)
    return _request("GET", "coupons", credentials=creds, params=params)


# --- Shipping carriers ---
def list_shipping_carriers(request=None):
    creds = get_credentials(request) if request else None
    data, err = _request("GET", "shipping_carriers", credentials=creds)
    if err:
        return [], err
    return (data if isinstance(data, list) else []), None


# --- Payment providers ---
def list_payment_providers(request=None):
    creds = get_credentials(request) if request else None
    data, err = _request("GET", "payment_providers", credentials=creds)
    if err:
        return [], err
    return (data if isinstance(data, list) else data or []), None
