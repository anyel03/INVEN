
from django.urls import path
from . import views

urlpatterns = [
    # Productos
    path('', views.producto_list, name='producto_list'),
    path('crear/', views.producto_create, name='producto_create'),
    path('editar/<int:pk>/', views.producto_edit, name='producto_edit'),
    path('eliminar/<int:pk>/', views.producto_delete, name='producto_delete'),
    
    # Inventario por Ruta
    path('ruta/', views.inventario_ruta_list, name='inventario_ruta_list'),
    path('ruta/<int:ruta_id>/', views.inventario_ruta_detalle, name='inventario_ruta_detalle'),
    
    # Transferencias
    path('transferencias/', views.transferencia_list, name='transferencia_list'),
    path('transferencias/crear/', views.transferencia_create, name='transferencia_create'),
    path('transferencias/<int:transferencia_id>/', views.transferencia_detalle, name='transferencia_detalle'),
    path('transferencias/<int:transferencia_id>/eliminar/', views.transferencia_delete, name='transferencia_delete'),
]
