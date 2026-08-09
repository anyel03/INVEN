from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.usuarios.urls')),
    path('rutas/', include('apps.rutas.urls')),
    path('clientes/', include('apps.clientes.urls')),
    path('inventario/', include('apps.inventario.urls')),
    path('ventas/', include('apps.ventas.urls')),
    path('cobros/', include('apps.cobros.urls')),
    path('finanzas/', include('apps.finanzas.urls')),
]

handler404 = 'INVEN.views.error_404'
handler500 = 'INVEN.views.error_500'
handler403 = 'INVEN.views.error_403'
handler400 = 'INVEN.views.error_400'