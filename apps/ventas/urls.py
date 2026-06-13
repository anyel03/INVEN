
from django.urls import path
from . import views

urlpatterns = [
    path('', views.venta_list, name='venta_list'),
    path('nueva/', views.venta_create, name='venta_create'),
    path('<int:pk>/', views.venta_detalle, name='venta_detalle'),
]