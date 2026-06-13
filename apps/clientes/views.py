
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q

from .models import Cliente
from apps.rutas.models import Ruta


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


# ==================== CLIENTES ====================

@requiere_login
def cliente_list(request):
    """Lista de clientes"""
    search = request.GET.get('search', '')
    ruta_id = request.GET.get('ruta', '')
    
    clientes = Cliente.objects.select_related('ruta').order_by('nombre')
    
    if search:
        clientes = clientes.filter(
            Q(nombre__icontains=search) | 
            Q(telefono__icontains=search) |
            Q(numero_documento__icontains=search)
        )
    
    if ruta_id:
        clientes = clientes.filter(ruta_id=ruta_id)
    
    rutas = Ruta.objects.all()
    return render(request, 'clientes/lista.html', {
        'clientes': clientes,
        'rutas': rutas,
        'search': search
    })


@solo_admin
def cliente_create(request):
    """Crear cliente"""
    if request.method == 'POST':
        numero_documento = request.POST.get('numero_documento', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        ruta_id = request.POST.get('ruta_id') or None
        tipo_documento = request.POST.get('tipo_documento', 'CEDULA')
        
        if not numero_documento:
            messages.error(request, 'El número de documento es requerido')
        elif not nombre:
            messages.error(request, 'El nombre es requerido')
        elif Cliente.objects.filter(pk=numero_documento).exists():
            messages.error(request, 'Ya existe un cliente con ese documento')
        else:
            cliente = Cliente.objects.create(
                numero_documento=numero_documento,
                nombre=nombre,
                telefono=telefono,
                direccion=direccion,
                ruta_id=ruta_id,
                tipo_documento=tipo_documento,
            )
            
            # Guardar foto si se subió
            if request.FILES.get('foto_documento'):
                cliente.foto_documento = request.FILES['foto_documento']
                cliente.save()
            
            messages.success(request, f'Cliente "{nombre}" criado correctamente')
            return redirect('cliente_list')
        
        # Mantener valores en formulario
        cliente_data = {
            'numero_documento': request.POST.get('numero_documento', ''),
            'nombre': request.POST.get('nombre', ''),
            'telefono': request.POST.get('telefono', ''),
            'direccion': request.POST.get('direccion', ''),
            'tipo_documento': request.POST.get('tipo_documento', 'CEDULA'),
        }
    else:
        cliente_data = None
    
    rutas = Ruta.objects.all()
    return render(request, 'clientes/form.html', {
        'action': 'crear',
        'cliente': cliente_data,
        'rutas': rutas
    })


@solo_admin
def cliente_edit(request, numero_documento):
    """Editar cliente"""
    cliente = get_object_or_404(Cliente, pk=numero_documento)
    
    if request.method == 'POST':
        cliente.nombre = request.POST.get('nombre', '').strip()
        cliente.telefono = request.POST.get('telefono', '').strip()
        cliente.direccion = request.POST.get('direccion', '').strip()
        cliente.ruta_id = request.POST.get('ruta_id') or None
        cliente.tipo_documento = request.POST.get('tipo_documento', 'CEDULA')
        
        if request.FILES.get('foto_documento'):
            cliente.foto_documento = request.FILES['foto_documento']
        
        cliente.save()
        messages.success(request, 'Cliente atualizado correctamente')
        return redirect('cliente_list')
    
    rutas = Ruta.objects.all()
    return render(request, 'clientes/form.html', {
        'action': 'editar',
        'cliente': cliente,
        'rutas': rutas
    })


@solo_admin
def cliente_delete(request, numero_documento):
    """Eliminar cliente"""
    cliente = get_object_or_404(Cliente, pk=numero_documento)
    
    if request.method == 'POST':
        nombre = cliente.nombre
        # Eliminar foto si existe
        if cliente.foto_documento:
            cliente.foto_documento.delete()
        cliente.delete()
        messages.success(request, f'Cliente "{nombre}" eliminado correctamente')
        return redirect('cliente_list')
    
    return render(request, 'clientes/delete.html', {'cliente': cliente})