# INVEN/views.py
from django.shortcuts import render

def error_404(request, exception=None):
    """Manejador personalizado para error 404 (Página No Encontrada)"""
    return render(request, 'errors/404.html', status=404)

def error_500(request):
    """Manejador personalizado para error 500 (Error Interno del Servidor)"""
    return render(request, 'errors/500.html', status=500)

def error_403(request, exception=None):
    """Manejador personalizado para error 403 (Acceso Prohibido / Sin Permisos)"""
    return render(request, 'errors/403.html', status=403)

def error_400(request, exception=None):
    """Manejador personalizado para error 400 (Petición Incorrecta)"""
    return render(request, 'errors/400.html', status=400)
