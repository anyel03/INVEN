# apps/finanzas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='finanzas_dashboard'),
    path('reportes/ventas/', views.reporte_ventas, name='reporte_ventas'),
    path('compras/', views.compra_list, name='compra_list'),
    path('compras/nueva/', views.compra_create, name='compra_create'),
    path('compras/<int:pk>/', views.compra_detail, name='compra_detail'),
    path('ingresos/', views.ingreso_list, name='ingreso_list'),
    path('ingresos/nuevo/', views.ingreso_create, name='ingreso_create'),
    path('ingresos/<int:pk>/eliminar/', views.ingreso_delete, name='ingreso_delete'),
    path('caja-rutas/', views.caja_ruta_list, name='caja_ruta_list'),
    path('caja-rutas/nueva/', views.caja_ruta_create, name='caja_ruta_create'),
    path('caja-rutas/ajax-preview/', views.ajax_preview_caja_ruta, name='ajax_preview_caja_ruta'),
]