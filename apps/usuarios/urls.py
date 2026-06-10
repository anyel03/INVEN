from django.urls import path
from . import views

urlpatterns = [
    # ==================== AUTH ====================
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # ==================== ROLES ====================
    path('roles/', views.rol_list, name='rol_list'),
    path('roles/crear/', views.rol_create, name='rol_create'),
    path('roles/editar/<int:pk>/', views.rol_edit, name='rol_edit'),
    path('roles/eliminar/<int:pk>/', views.rol_delete, name='rol_delete'),
    
    # ==================== USUARIOS ====================
    path('usuarios/', views.usuario_list, name='usuario_list'),
    path('usuarios/crear/', views.usuario_create, name='usuario_create'),
    path('usuarios/editar/<int:pk>/', views.usuario_edit, name='usuario_edit'),
    path('usuarios/eliminar/<int:pk>/', views.usuario_delete, name='usuario_delete'),
    
    # ==================== EMPLEADOS ====================
    path('empleados/', views.empleado_list, name='empleado_list'),
    path('empleados/crear/', views.empleado_create, name='empleado_create'),
    path('empleados/editar/<int:pk>/', views.empleado_edit, name='empleado_edit'),
    path('empleados/eliminar/<int:pk>/', views.empleado_delete, name='empleado_delete'),
]