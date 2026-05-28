"""
URL configuration for INVEN project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from apps.usuarios import views as usuario



urlpatterns = [
    path('admin/', admin.site.urls),

       # ==================== AUTH ====================
    path('', usuario.login_view, name='login'),
    path('logout/', usuario.logout_view, name='logout'),
    path('dashboard/', usuario.dashboard_view, name='dashboard'),
    
    # ==================== ROLES - Solo ADMIN ====================
    path('roles/', usuario.rol_list, name='rol_list'),
    path('roles/crear/', usuario.rol_create, name='rol_create'),
    path('roles/editar/<int:pk>/', usuario.rol_edit, name='rol_edit'),
    path('roles/eliminar/<int:pk>/', usuario.rol_delete, name='rol_delete'),
    
    # ==================== USUARIOS - Solo ADMIN ====================
    path('usuarios/', usuario.usuario_list, name='usuario_list'),
    path('usuarios/crear/', usuario.usuario_create, name='usuario_create'),
    path('usuarios/editar/<int:pk>/', usuario.usuario_edit, name='usuario_edit'),
    path('usuarios/eliminar/<int:pk>/', usuario.usuario_delete, name='usuario_delete'),
    
    # ==================== EMPLEADOS - Solo ADMIN ====================
    path('empleados/', usuario.empleado_list, name='empleado_list'),
    path('empleados/crear/', usuario.empleado_create, name='empleado_create'),
    path('empleados/editar/<int:pk>/', usuario.empleado_edit, name='empleado_edit'),
    path('empleados/eliminar/<int:pk>/', usuario.empleado_delete, name='empleado_delete'),
]
