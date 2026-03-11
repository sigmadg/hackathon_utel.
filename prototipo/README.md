# Asistente inteligente para configuración de tiendas (prototipo)

Prototipo del **Asistente para tienda** del Hackathon Ecommerce / Tiendanube. El usuario chatea en lenguaje natural para configurar su tienda: chatbot, APIs de validación, reconocimiento facial, envíos, pagos, etc. Un LLM interpreta la intención y se ejecutan (o simulan) las integraciones.

## Stack

- **Python 3.10+**
- **Django 5** (web)
- **OpenAI API** (LLM) — opcional; sin API key hay respuestas por palabras clave
- **Ollama** (LLM local) — opcional; usa por ejemplo Qwen 2.5 Coder sin salir a internet
- **API Tiendanube** — opcional; sin credenciales las acciones se simulan

## Instalación

```bash
cd prototipo
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env y añadir OPENAI_API_KEY si quieres usar el LLM real
python manage.py migrate
python manage.py runserver
```

Abrir: **http://127.0.0.1:8000/**

## Variables de entorno (.env)

| Variable | Descripción |
|----------|-------------|
| `OPENAI_API_KEY` | API key de OpenAI para el asistente (opcional) |
| `OPENAI_MODEL` | Modelo OpenAI (default: gpt-4o-mini) |
| `OLLAMA_MODEL` | Si está definido, se usa Ollama en lugar de OpenAI (ej: `qwen2.5-coder:1.5b`) |
| `OLLAMA_BASE_URL` | URL del API de Ollama (default: http://localhost:11434/v1) |
| `TIENDANUBE_ACCESS_TOKEN` | Token OAuth de la app Tiendanube (opcional) |
| `TIENDANUBE_STORE_ID` | ID de la tienda (opcional) |
| `TIENDANUBE_API_BASE` | Base URL de la API (default: `https://api.tiendanube.com/2025-03`). La URL final es `{API_BASE}/{store_id}`. |
| `TIENDANUBE_APP_ID` | ID de tu app en el panel de partners (para OAuth) |
| `TIENDANUBE_CLIENT_SECRET` | Client secret de la app (para OAuth) |
| `TIENDANUBE_REDIRECT_URI` | URL de redirección configurada en la app (ej: `http://localhost:8000/oauth/tiendanube/callback/`) |

Puedes conectar de dos formas: **OAuth** (el usuario instala la app y autoriza desde la interfaz) o **token manual** (copias `access_token` y `user_id` en .env). Con OAuth configurado, en el chat aparece el enlace "Conectar con Tiendanube"; al hacer clic, el usuario va a Tiendanube, autoriza, y vuelve al asistente con la sesión conectada.

Sin `OPENAI_API_KEY` el asistente responde con lógica por palabras clave. Si defines `OLLAMA_MODEL` (por ejemplo `qwen2.5-coder:1.5b`), se usará tu Ollama local en lugar de OpenAI.

### Usar Ollama con Qwen 2.5 Coder

1. Instala [Ollama](https://ollama.com) y descarga el modelo:
   ```bash
   ollama pull qwen2.5-coder:1.5b
   ```
2. En tu `.env`:
   ```
   OLLAMA_MODEL=qwen2.5-coder:1.5b
   OLLAMA_BASE_URL=http://localhost:11434/v1
   ```
3. Arranca el prototipo; el chat usará el modelo local. Otros tamaños: `qwen2.5-coder:3b`, `qwen2.5-coder:7b`.

## Estructura del proyecto

```
prototipo/
├── config/                 # Proyecto Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── asistente/              # App principal
│   ├── services/
│   │   ├── llm_service.py    # Integración LLM (OpenAI / fallback)
│   │   ├── tiendanube_api.py # Cliente API Tiendanube
│   │   └── intent_handler.py # Ejecución de acciones
│   ├── templates/asistente/
│   │   └── chat.html        # Interfaz del chat
│   ├── views.py
│   └── urls.py
├── manage.py
├── requirements.txt
└── .env.example
```

## API del chat

**POST** `/api/chat/`

Cuerpo (JSON):

```json
{
  "messages": [
    { "role": "user", "content": "Quiero un chatbot para mi tienda" }
  ]
}
```

Respuesta:

```json
{
  "reply": "Puedo ayudarte a configurar un chatbot...",
  "action": "chatbot",
  "action_result": {
    "success": true,
    "message": "Chatbot configurado correctamente...",
    "detail": { ... }
  }
}
```

## Licencia

Prototipo con fines de hackathon.
