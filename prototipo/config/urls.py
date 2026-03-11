"""
URL configuration for Asistente Tienda.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('asistente.urls')),
]