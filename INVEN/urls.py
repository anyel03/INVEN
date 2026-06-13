# sistema_inventario/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.usuarios.urls')),
    path('rutas/', include('apps.rutas.urls')),
    path('inventario/', include('apps.inventario.urls')),
]