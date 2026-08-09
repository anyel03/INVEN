from django.urls import path
from . import views

urlpatterns = [
    path('', views.cobro_list, name='cobro_list'),
    path('nuevo/', views.cobro_create, name='cobro_create'),
    path('pendientes/', views.cobros_pendientes, name='cobros_pendientes'),
    path('ruta-mapa/', views.cobro_ruta_mapa, name='cobro_ruta_mapa'),
]