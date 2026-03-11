"""
Django settings for Asistente Tienda (prototipo Hackathon).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-change-in-production')

DEBUG = os.environ.get('DEBUG', '1') == '1'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'asistente',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# API / LLM (desde variables de entorno)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
# Ollama local (prioridad si está definido)
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', '')
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
TIENDANUBE_ACCESS_TOKEN = os.environ.get('TIENDANUBE_ACCESS_TOKEN', '')
TIENDANUBE_STORE_ID = os.environ.get('TIENDANUBE_STORE_ID', '')
TIENDANUBE_API_BASE = os.environ.get('TIENDANUBE_API_BASE', 'https://api.tiendanube.com/2025-03')

# OAuth Tiendanube (authorization code)
TIENDANUBE_APP_ID = os.environ.get('TIENDANUBE_APP_ID', '')
TIENDANUBE_CLIENT_SECRET = os.environ.get('TIENDANUBE_CLIENT_SECRET', '')
TIENDANUBE_REDIRECT_URI = os.environ.get('TIENDANUBE_REDIRECT_URI', '')
TIENDANUBE_OAUTH_DOMAIN = os.environ.get('TIENDANUBE_OAUTH_DOMAIN', 'https://www.tiendanube.com')

# Ruta a las plantillas HTML del visor (minimal, moderno, tienda)
TIENDANUBE_TEMPLATES_DIR = BASE_DIR / 'Templates'

# CORS para desarrollo
CORS_ALLOW_ALL_ORIGINS = DEBUG

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}
