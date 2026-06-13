from django.urls import path
from . import views

urlpatterns = [
    path('', views.cliente_list, name='cliente_list'),
    path('crear/', views.cliente_create, name='cliente_create'),
    path('editar/<str:numero_documento>/', views.cliente_edit, name='cliente_edit'),
    path('eliminar/<str:numero_documento>/', views.cliente_delete, name='cliente_delete'),
]