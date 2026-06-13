
from django.urls import path
from . import views

urlpatterns = [
    path('', views.cobro_list, name='cobro_list'),
    path('nuevo/', views.cobro_create, name='cobro_create'),
]