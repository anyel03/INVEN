from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator

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
    """Lista de clientes (ADMIN ve todos, EMPLEADO ve los de su ruta)"""
    search = request.GET.get('search', '')
    ruta_id = request.GET.get('ruta', '')
    user_id = request.session.get('user_id')
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')
    
    clientes = Cliente.objects.select_related('ruta').order_by('nombre')

    if not es_admin:
        from apps.cobros.views import _get_empleado_info
        empleado, ruta_emp_id = _get_empleado_info(user_id)
        if ruta_emp_id:
            clientes = clientes.filter(ruta_id=ruta_emp_id)
        else:
            clientes = Cliente.objects.none()
    elif ruta_id:
        clientes = clientes.filter(ruta_id=ruta_id)
    
    if search:
        clientes = clientes.filter(
            Q(nombre__icontains=search) | 
            Q(telefono__icontains=search) |
            Q(numero_documento__icontains=search)
        )
    
    paginator = Paginator(clientes, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'clientes/lista.html', {
        'clientes': page_obj,
        'page_obj': page_obj,
        'rutas': Ruta.objects.all(),
        'search': search,
        'ruta_id': ruta_id,
        'es_admin': es_admin
    })


@requiere_login
def cliente_create(request):
    """Crear cliente (Accesible por ADMIN y EMPLEADOS)"""
    user_id = request.session.get('user_id')
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')

    if request.method == 'POST':
        numero_documento = request.POST.get('numero_documento', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        tipo_documento = request.POST.get('tipo_documento', 'CEDULA')

        if es_admin:
            ruta_id = request.POST.get('ruta_id') or None
        else:
            from apps.cobros.views import _get_empleado_info
            empleado, ruta_emp_id = _get_empleado_info(user_id)
            if not ruta_emp_id:
                messages.error(request, 'No tienes una ruta asignada para crear clientes')
                return redirect('cliente_list')
            ruta_id = ruta_emp_id
        
        latitud_raw = request.POST.get('latitud', '').strip()
        longitud_raw = request.POST.get('longitud', '').strip()
        latitud = float(latitud_raw) if latitud_raw else None
        longitud = float(longitud_raw) if longitud_raw else None

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
                latitud=latitud,
                longitud=longitud,
            )
            
            # Guardar foto si se subió
            if request.FILES.get('foto_documento'):
                cliente.foto_documento = request.FILES['foto_documento']
                cliente.save()
            
            messages.success(request, f'Cliente "{nombre}" creado correctamente')
            return redirect('cliente_list')
        
        # Mantener valores en formulario
        cliente_data = {
            'numero_documento': request.POST.get('numero_documento', ''),
            'nombre': request.POST.get('nombre', ''),
            'telefono': request.POST.get('telefono', ''),
            'direccion': request.POST.get('direccion', ''),
            'tipo_documento': request.POST.get('tipo_documento', 'CEDULA'),
            'latitud': latitud_raw,
            'longitud': longitud_raw,
        }
    else:
        cliente_data = None
    
    rutas = Ruta.objects.all()
    return render(request, 'clientes/form.html', {
        'action': 'crear',
        'cliente': cliente_data,
        'rutas': rutas,
        'es_admin': es_admin
    })


@requiere_login
def cliente_edit(request, numero_documento):
    """Editar cliente (Accesible por ADMIN y EMPLEADOS de su ruta)"""
    user_id = request.session.get('user_id')
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')

    cliente = get_object_or_404(Cliente, pk=numero_documento)

    if not es_admin:
        from apps.cobros.views import _get_empleado_info
        empleado, ruta_emp_id = _get_empleado_info(user_id)
        if cliente.ruta_id and cliente.ruta_id != ruta_emp_id:
            messages.error(request, 'No tienes permiso para editar clientes de otra ruta')
            return redirect('cliente_list')
    
    if request.method == 'POST':
        cliente.nombre = request.POST.get('nombre', '').strip()
        cliente.telefono = request.POST.get('telefono', '').strip()
        cliente.direccion = request.POST.get('direccion', '').strip()
        cliente.tipo_documento = request.POST.get('tipo_documento', 'CEDULA')

        if es_admin:
            cliente.ruta_id = request.POST.get('ruta_id') or None

        latitud_raw = request.POST.get('latitud', '').strip()
        longitud_raw = request.POST.get('longitud', '').strip()
        cliente.latitud = float(latitud_raw) if latitud_raw else None
        cliente.longitud = float(longitud_raw) if longitud_raw else None
        
        if request.FILES.get('foto_documento'):
            cliente.foto_documento = request.FILES['foto_documento']
        
        cliente.save()
        messages.success(request, 'Cliente actualizado correctamente')
        return redirect('cliente_list')
    
    rutas = Ruta.objects.all()
    return render(request, 'clientes/form.html', {
        'action': 'editar',
        'cliente': cliente,
        'rutas': rutas,
        'es_admin': es_admin
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


@requiere_login
def cliente_guardar_gps(request, numero_documento):
    """Guardar ubicación GPS del cliente vía POST o AJAX"""
    from django.http import JsonResponse
    if request.method == 'POST':
        cliente = get_object_or_404(Cliente, pk=numero_documento)
        lat = request.POST.get('latitud')
        lng = request.POST.get('longitud')
        try:
            cliente.latitud = float(lat)
            cliente.longitud = float(lng)
            cliente.save()
            return JsonResponse({'status': 'ok', 'message': f'Ubicación GPS guardada para {cliente.nombre}'})
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Coordenadas inválidas'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)