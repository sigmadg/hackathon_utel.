from django.urls import path
from . import views

app_name = 'asistente'

urlpatterns = [
    path('', views.chat_page, name='chat_page'),
    path('api/chat/', views.api_chat, name='api_chat'),
    path('api/tiendanube-status/', views.api_tiendanube_status, name='api_tiendanube_status'),
    path('oauth/tiendanube/authorize/', views.tiendanube_oauth_authorize, name='tiendanube_oauth_authorize'),
    path('oauth/tiendanube/callback/', views.tiendanube_oauth_callback, name='tiendanube_oauth_callback'),
    path('templates-preview/<path:path>', views.serve_template_preview, name='template_preview'),
]
