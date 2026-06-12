# apps/rutas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import Ruta


# ==================== HELPERS ====================

def requiere_login(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_admin(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        if request.session.get('rol_nombre') != 'ADMIN':
            messages.error(request, 'No tienes acceso a esta sección')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== RUTAS ====================

@requiere_login
def ruta_list(request):
    """Lista de rutas"""
    rutas = Ruta.objects.all().order_by('nombre')
    return render(request, 'rutas/lista.html', {'rutas': rutas})


@solo_admin
def ruta_create(request):
    """Crear ruta"""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        
        if not nombre:
            messages.error(request, 'El nombre es requerido')
        elif Ruta.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, 'Ya existe una ruta con ese nombre')
        else:
            Ruta.objects.create(nombre=nombre, descripcion=descripcion)
            messages.success(request, f'Ruta "{nombre}" creada correctamente')
            return redirect('ruta_list')
    
    return render(request, 'rutas/form.html', {'action': 'crear', 'ruta': None})


@solo_admin
def ruta_edit(request, pk):
    """Editar ruta"""
    ruta = get_object_or_404(Ruta, pk=pk)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        
        if not nombre:
            messages.error(request, 'El nombre es requerido')
        elif Ruta.objects.filter(nombre__iexact=nombre).exclude(pk=pk).exists():
            messages.error(request, 'Ya existe una ruta con ese nombre')
        else:
            ruta.nombre = nombre
            ruta.descripcion = descripcion
            ruta.save()
            messages.success(request, 'Ruta actualizada correctamente')
            return redirect('ruta_list')
    
    return render(request, 'rutas/form.html', {'action': 'editar', 'ruta': ruta})


@solo_admin
def ruta_delete(request, pk):
    """Eliminar ruta"""
    ruta = get_object_or_404(Ruta, pk=pk)
    
    if request.method == 'POST':
        ruta.delete()
        messages.success(request, 'Ruta eliminada correctamente')
        return redirect('ruta_list')
    
    return render(request, 'rutas/delete.html', {'ruta': ruta})