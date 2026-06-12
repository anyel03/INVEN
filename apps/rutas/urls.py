# apps/rutas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.ruta_list, name='ruta_list'),
    path('crear/', views.ruta_create, name='ruta_create'),
    path('editar/<int:pk>/', views.ruta_edit, name='ruta_edit'),
    path('eliminar/<int:pk>/', views.ruta_delete, name='ruta_delete'),
]