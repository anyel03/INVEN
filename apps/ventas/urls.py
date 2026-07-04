
from django.urls import path
from . import views

urlpatterns = [
    path('', views.venta_list, name='venta_list'),
    path('nueva/', views.venta_create, name='venta_create'),
    path('nueva-con-cliente/', views.venta_create_con_cliente, name='venta_create_con_cliente'),
    path('<int:pk>/', views.venta_detalle, name='venta_detalle'),
    path('ajax/stock-ruta/', views.ajax_stock_por_ruta, name='ajax_stock_por_ruta'),
]


