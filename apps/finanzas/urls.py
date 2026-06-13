# apps/finanzas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='finanzas_dashboard'),
    path('compras/', views.compra_list, name='compra_list'),
    path('compras/nueva/', views.compra_create, name='compra_create'),
    path('ingresos/', views.ingreso_list, name='ingreso_list'),
    path('ingresos/nuevo/', views.ingreso_create, name='ingreso_create'),
    path('caja-rutas/', views.caja_ruta_list, name='caja_ruta_list'),
]