"""
Mapeo de intenciones (ACCION) a pasos ejecutables.
En el prototipo se simula la ejecución y se devuelve un mensaje de confirmación.
"""
from . import tiendanube_api


def execute_action(action, context=None):
    """
    Ejecuta la acción indicada y devuelve (éxito: bool, mensaje: str, detalle: dict).
    detalle incluye "implementation" con title, type y snippet para el visor.
    """
    context = context or {}
    action = (action or "").strip().lower()

    if action == "chatbot":
        return _do_chatbot(context)
    if action == "api_validacion":
        return _do_api_validacion(context)
    if action == "reconocimiento_facial":
        return _do_reconocimiento_facial(context)
    if action == "envios":
        return _do_envios(context)
    if action == "pagos":
        return _do_pagos(context)
    if action == "dropshipping":
        return _do_dropshipping(context)

    return False, "Acción no implementada en este prototipo.", {"action": action}


def _do_chatbot(context):
    """Intenta registrar un script de ejemplo para chatbot (o simula)."""
    request = context.get("request")
    implementation = {
        "title": "Chatbot de atención",
        "type": "script",
        "snippet": """<!-- Script agregado a tu tienda -->
<script src="https://ejemplo.com/chatbot.js"></script>
<!-- Configuración -->
{ "widget": "chat", "position": "bottom-right" }""",
    }
    store, err = tiendanube_api.get_store(request=request)
    if err and not store:
        return True, (
            "Chatbot preparado para tu tienda. En un entorno con credenciales de Tiendanube "
            "se registraría un script de atención automática. Por ahora queda configurado en modo demo."
        ), {"simulated": True, "error_api": err, "implementation": implementation}

    script_src = "https://ejemplo.com/chatbot.js"  # placeholder
    created, err = tiendanube_api.create_script(
        name="Asistente Chat (prototipo)",
        src=script_src,
        description="Chatbot de preguntas frecuentes",
        request=request,
    )
    if err:
        return True, (
            "La intención de activar el chatbot fue registrada. "
            f"Para activarlo en tu tienda real necesitas configurar la API: {err}"
        ), {"simulated": True, "error": err, "implementation": implementation}
    return True, "Chatbot configurado correctamente en tu tienda.", {"script": created, "implementation": implementation}


def _do_api_validacion(context):
    implementation = {
        "title": "API de validación",
        "type": "webhook",
        "snippet": """// Webhook registrado: order/created
POST https://tu-app.com/validate
Headers: { "X-Store-Id": "{{store_id}}" }
Body: { "customer_id": "{{customer.id}}" }""",
    }
    return True, (
        "Integración de API de validación registrada. "
        "En producción se conectaría con tu proveedor de validación (identidad, datos, etc.)."
    ), {"simulated": True, "implementation": implementation}


def _do_reconocimiento_facial(context):
    implementation = {
        "title": "Reconocimiento facial",
        "type": "module",
        "snippet": """// Módulo de verificación en checkout
import { FaceVerification } from '@tienda/face-verify';

FaceVerification.init({
  endpoint: '/api/verify-face',
  onSuccess: () => allowCheckout(),
});""",
    }
    return True, (
        "Módulo de reconocimiento facial preparado. "
        "Se podría integrar con un servicio de verificación por rostro en el checkout o en área de clientes."
    ), {"simulated": True, "implementation": implementation}


def _do_envios(context):
    request = context.get("request")
    implementation = {
        "title": "Configuración de envíos",
        "type": "config",
        "snippet": """# Carriers disponibles
- Envío Nube (integrado)
- DHL, FedEx (API)
# Variables: weight, zip_origin, zip_dest""",
    }
    carriers, err = tiendanube_api.list_shipping_carriers(request=request)
    if not err and isinstance(carriers, list) and len(carriers) > 0:
        names = []
        for c in carriers[:5]:
            n = c.get("name") or c.get("carrier") or str(c.get("id", ""))
            if isinstance(n, dict):
                n = n.get("es") or n.get("en") or next(iter(n.values()), "")
            if n:
                names.append(n)
        if names:
            implementation["snippet"] = "# Carriers en tu tienda:\n" + "\n".join(f"- {n}" for n in names)
        return True, (
            "Carriers de envío consultados desde tu tienda. Puedes añadir más en Tiendanube → Envíos."
        ), {"simulated": False, "implementation": implementation}
    store, err_store = tiendanube_api.get_store(request=request)
    if err_store and not store:
        return True, (
            "Opciones de envío listas para configurar. "
            "Conecta tu tienda con Tiendanube para ver carriers y costos."
        ), {"simulated": True, "implementation": implementation}
    return True, "Puedes configurar envíos desde el panel de Tiendanube en la sección Envíos.", {"simulated": False, "implementation": implementation}


def _do_pagos(context):
    request = context.get("request")
    implementation = {
        "title": "Métodos de pago",
        "type": "config",
        "snippet": """# Pasarelas sugeridas
- Pago Nube (sin comisión por transacción)
- Mercado Pago
- PayPal
# Activar en: Tienda → Pagos""",
    }
    providers, err = tiendanube_api.list_payment_providers(request=request)
    if not err and isinstance(providers, list) and len(providers) > 0:
        names = []
        for p in providers[:5]:
            n = p.get("name") or p.get("provider") or str(p.get("id", ""))
            if isinstance(n, dict):
                n = n.get("es") or n.get("en") or next(iter(n.values()), "")
            if n:
                names.append(n)
        if names:
            implementation["snippet"] = "# Pasarelas en tu tienda:\n" + "\n".join(f"- {n}" for n in names)
        return True, (
            "Métodos de pago consultados desde tu tienda. Puedes activar más en Tiendanube → Pagos."
        ), {"simulated": False, "implementation": implementation}
    return True, (
        "Métodos de pago: puedes activar Pago Nube, Mercado Pago u otros desde el panel de tu tienda."
    ), {"simulated": True, "implementation": implementation}


def _do_dropshipping(context):
    implementation = {
        "title": "APIs de dropshipping",
        "type": "integration",
        "snippet": """# Conexión con proveedor dropshipping
POST /api/orders → notificar al proveedor
GET /api/inventory → sincronizar stock
# Webhooks: order/paid, product/updated""",
    }
    return True, (
        "APIs de dropshipping configuradas. Conecta tu tienda con proveedores para sincronizar inventario y enviar pedidos automáticamente."
    ), {"simulated": True, "implementation": implementation}
