# apps/usuarios/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
import hashlib
from django.db.models import Q

from .models import Usuario, Rol, Empleado
from apps.rutas.models import Ruta


# ==================== PERMISOS ====================

def es_admin(request):
    return request.session.get('rol_nombre') == 'ADMIN'

def es_empleado(request):
    return request.session.get('rol_nombre') == 'EMPLEADO'

def requiere_admin(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        if not es_admin(request):
            messages.error(request, 'No tienes acceso a esta sección')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def puede_acceder_a(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== AUTH ====================

def login_view(request):
    if request.session.get('user_id'):
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        if not email or not password:
            messages.error(request, 'Ingresa email y contraseña')
            return render(request, 'usuarios/login.html')
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            usuario = Usuario.objects.get(email=email, password=hashed_password, activo=True)
            request.session['user_id'] = usuario.id
            request.session['user_name'] = usuario.nombre
            request.session['user_email'] = usuario.email
            request.session['rol_id'] = usuario.rol.id
            request.session['rol_nombre'] = usuario.rol.nombre
            return redirect('dashboard')
        except Usuario.DoesNotExist:
            messages.error(request, 'Credenciales inválidas')
    
    return render(request, 'usuarios/login.html')


def logout_view(request):
    request.session.flush()
    return redirect('login')


def dashboard_view(request):
    if not request.session.get('user_id'):
        return redirect('login')
    
    # El empleado solo puede vender y cobrar
    if es_empleado(request):
        return render(request, 'usuarios/dashboard_empleado.html')
    
    return render(request, 'usuarios/dashboard.html')


# ==================== ROLES - SOLO ADMIN ====================

@requiere_admin
def rol_list(request):
    roles = Rol.objects.all().order_by('nombre')
    return render(request, 'usuarios/roles/lista.html', {'roles': roles})

@requiere_admin
def rol_create(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if nombre:
            Rol.objects.create(nombre=nombre)
            messages.success(request, f'Rol "{nombre}" creado')
            return redirect('rol_list')
    return render(request, 'usuarios/roles/form.html', {'action': 'crear', 'rol': None})

@requiere_admin
def rol_edit(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == 'POST':
        rol.nombre = request.POST.get('nombre', '').strip()
        rol.save()
        messages.success(request, 'Rol actualizado')
        return redirect('rol_list')
    return render(request, 'usuarios/roles/form.html', {'action': 'editar', 'rol': rol})

@requiere_admin
def rol_delete(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == 'POST':
        if Usuario.objects.filter(rol=rol).exists():
            messages.error(request, 'No se puede eliminar. Hay usuarios con este rol')
        else:
            rol.delete()
            messages.success(request, 'Rol eliminado')
        return redirect('rol_list')
    return render(request, 'usuarios/roles/delete.html', {'rol': rol})


# ==================== USUARIOS - SOLO ADMIN ====================

@requiere_admin
def usuario_list(request):
    search = request.GET.get('search', '')
    usuarios = Usuario.objects.select_related('rol').order_by('nombre')
    if search:
        usuarios = usuarios.filter(Q(nombre__icontains=search) | Q(email__icontains=search))
    return render(request, 'usuarios/usuarios/lista.html', {'usuarios': usuarios, 'roles': Rol.objects.all(), 'search': search})

@requiere_admin
def usuario_create(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        rol_id = request.POST.get('rol_id', '')
        
        if nombre and email and password and rol_id:
            if not Usuario.objects.filter(email=email).exists():
                hashed = hashlib.sha256(password.encode()).hexdigest()
                Usuario.objects.create(nombre=nombre, email=email, password=hashed, rol_id=rol_id)
                messages.success(request, f'Usuario "{nombre}" creado')
                return redirect('usuario_list')
        messages.error(request, 'Error al crear usuario')
    return render(request, 'usuarios/usuarios/form.html', {'action': 'crear', 'usuario': None, 'roles': Rol.objects.all()})

@requiere_admin
def usuario_edit(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre', '').strip()
        usuario.email = request.POST.get('email', '').strip().lower()
        usuario.rol_id = request.POST.get('rol_id', '')
        usuario.activo = request.POST.get('activo') == 'on'
        password = request.POST.get('password', '')
        if password:
            usuario.password = hashlib.sha256(password.encode()).hexdigest()
        usuario.save()
        messages.success(request, 'Usuario actualizado')
        return redirect('usuario_list')
    return render(request, 'usuarios/usuarios/form.html', {'action': 'editar', 'usuario': usuario, 'roles': Rol.objects.all()})

@requiere_admin
def usuario_delete(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado')
        return redirect('usuario_list')
    return render(request, 'usuarios/usuarios/delete.html', {'usuario': usuario})


# ==================== EMPLEADOS - SOLO ADMIN ====================

@requiere_admin
def empleado_list(request):
    empleados = Empleado.objects.select_related('usuario__rol', 'ruta').order_by('usuario__nombre')
    return render(request, 'usuarios/empleados/lista.html', {'empleados': empleados, 'rutas': Ruta.objects.all()})

@requiere_admin
def empleado_create(request):
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        ruta_id = request.POST.get('ruta_id') or None
        
        if usuario_id:
            if not Empleado.objects.filter(usuario_id=usuario_id).exists():
                Empleado.objects.create(usuario_id=usuario_id, telefono=telefono, direccion=direccion, ruta_id=ruta_id)
                messages.success(request, 'Empleado creado')
                return redirect('empleado_list')
        messages.error(request, 'Error al crear empleado')
    return render(request, 'usuarios/empleados/form.html', {
        'action': 'crear', 'empleado': None,
        'usuarios': Usuario.objects.filter(activo=True, empleado__isnull=True),
        'rutas': Ruta.objects.all()
    })

@requiere_admin
def empleado_edit(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        empleado.telefono = request.POST.get('telefono', '').strip()
        empleado.direccion = request.POST.get('direccion', '').strip()
        empleado.ruta_id = request.POST.get('ruta_id') or None
        empleado.save()
        messages.success(request, 'Empleado actualizado')
        return redirect('empleado_list')
    return render(request, 'usuarios/empleados/form.html', {
        'action': 'editar', 'empleado': empleado,
        'usuarios': [empleado.usuario], 'rutas': Ruta.objects.all()
    })

@requiere_admin
def empleado_delete(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        empleado.delete()
        messages.success(request, 'Empleado eliminado')
        return redirect('empleado_list')
    return render(request, 'usuarios/empleados/delete.html', {'empleado': empleado})