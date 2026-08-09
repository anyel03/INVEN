from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
import hashlib
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Usuario, Rol, Empleado
from apps.rutas.models import Ruta
from apps.clientes.models import Cliente
from apps.ventas.models import Venta
from apps.cobros.models import Cobro


from decimal import Decimal

# ==================== HELPERS ====================

def _get_empleado_info(user_id):
    """Devuelve (empleado, ruta_id) para un usuario de tipo empleado."""
    try:
        empleado = Empleado.objects.filter(usuario_id=user_id).select_related('ruta').first()
        ruta_id = getattr(empleado, 'ruta_id', None)
        return empleado, ruta_id
    except Exception:
        return None, None


def es_admin(request):
    return request.session.get('rol_nombre') == 'ADMIN'


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


# ==================== AUTH ====================

def login_view(request):
    """Vista de login"""
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
    
    return render(request, 'usuarios/login.html')


def logout_view(request):
    """Cerrar sesión"""
    request.session.flush()
    return redirect('login')


@requiere_login
def dashboard_view(request):
    """Dashboard principal adaptado por Rol (ADMIN o EMPLEADO)"""
    user_id = request.session.get('user_id')
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')

    now = timezone.localtime(timezone.now())
    inicio_hoy = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_hoy = inicio_hoy + timezone.timedelta(days=1)

    ventas_qs = Venta.objects.all()
    cobros_qs = Cobro.objects.all()
    clientes_qs = Cliente.objects.all()

    empleado = None
    ruta_id = None
    ruta_nombre = 'Todas las Rutas'

    if es_admin:
        rutas_count = Ruta.objects.count()
    else:
        empleado, ruta_id = _get_empleado_info(user_id)
        if ruta_id:
            ruta_nombre = getattr(empleado.ruta, 'nombre', f'Ruta #{ruta_id}')
            rutas_count = 1
            ventas_qs = ventas_qs.filter(Q(ruta_id=ruta_id) | Q(cliente__ruta_id=ruta_id))
            cobros_qs = cobros_qs.filter(Q(venta__ruta_id=ruta_id) | Q(venta__cliente__ruta_id=ruta_id))
            clientes_qs = clientes_qs.filter(ruta_id=ruta_id)
        else:
            ruta_nombre = 'Sin Ruta Asignada'
            rutas_count = 0
            ventas_qs = Venta.objects.none()
            cobros_qs = Cobro.objects.none()
            clientes_qs = Cliente.objects.none()

    clientes_count = clientes_qs.count()

    # Fechas de hoy
    today = now.date()

    # Ventas de hoy
    ventas_hoy_contado = ventas_qs.filter(
        created_at__gte=inicio_hoy, 
        created_at__lt=fin_hoy,
        tipo='CONTADO'
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    ventas_hoy_credito = ventas_qs.filter(
        created_at__gte=inicio_hoy, 
        created_at__lt=fin_hoy,
        tipo='CREDITO'
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    ventas_hoy_total = ventas_qs.filter(
        created_at__gte=inicio_hoy, 
        created_at__lt=fin_hoy
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    # Cobros / Abonos recaudados hoy
    cobros_hoy = cobros_qs.filter(
        created_at__gte=inicio_hoy, 
        created_at__lt=fin_hoy
    ).aggregate(t=Sum('monto'))['t'] or Decimal('0')

    # INGRESOS DEL DÍA (Efectivo/Transferencia real recolectado hoy = Contado + Cobros)
    ingresos_hoy = ventas_hoy_contado + cobros_hoy

    # LO QUE HAY POR COBRAR DEL DÍA (Ventas pendientes programadas para hoy o vencidas)
    ventas_cobro_hoy = ventas_qs.filter(
        estado='PENDIENTE',
        proximo_cobro__lte=today
    )
    por_cobrar_hoy = ventas_cobro_hoy.aggregate(t=Sum('saldo'))['t'] or Decimal('0')
    cobros_hoy_count = ventas_cobro_hoy.count()

    # Saldo acumulado total por cobrar
    por_cobrar_total = ventas_qs.filter(estado='PENDIENTE').aggregate(t=Sum('saldo'))['t'] or Decimal('0')

    # Tablas de actividad reciente
    ultimas_ventas = ventas_qs.select_related('cliente', 'ruta').order_by('-created_at')[:5]
    ultimos_cobros = cobros_qs.select_related('venta__cliente', 'venta__ruta').order_by('-created_at')[:5]

    context = {
        'user': request.session.get('user_name'),
        'rol': rol_nombre,
        'es_admin': es_admin,
        'ruta_nombre': ruta_nombre,
        'rutas_count': rutas_count,
        'clientes_count': clientes_count,
        'today': today,
        'ventas_hoy_contado': ventas_hoy_contado,
        'ventas_hoy_credito': ventas_hoy_credito,
        'ventas_hoy_total': ventas_hoy_total,
        'cobros_hoy': cobros_hoy,
        'ingresos_hoy': ingresos_hoy,
        'por_cobrar_hoy': por_cobrar_hoy,
        'cobros_hoy_count': cobros_hoy_count,
        'por_cobrar_total': por_cobrar_total,
        'ultimas_ventas': ultimas_ventas,
        'ultimos_cobros': ultimos_cobros,
    }

    return render(request, 'usuarios/dashboard.html', context)



# ==================== ROLES ====================

@solo_admin
def rol_list(request):
    roles = Rol.objects.all().order_by('nombre')
    return render(request, 'usuarios/roles/lista.html', {'roles': roles})





@solo_admin
def rol_create(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if nombre:
            Rol.objects.create(nombre=nombre)
            messages.success(request, f'Rol "{nombre}" creado')
            return redirect('rol_list')
    return render(request, 'usuarios/roles/form.html', {'action': 'crear', 'rol': None})


@solo_admin
def rol_edit(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == 'POST':
        rol.nombre = request.POST.get('nombre', '').strip()
        rol.save()
        messages.success(request, 'Rol actualizado')
        return redirect('rol_list')
    return render(request, 'usuarios/roles/form.html', {'action': 'editar', 'rol': rol})


@solo_admin
def rol_delete(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    if request.method == 'POST':
        if Usuario.objects.filter(rol=rol).exists():
            messages.error(request, 'No se puede eliminar')
        else:
            rol.delete()
            messages.success(request, 'Rol eliminado')
        return redirect('rol_list')
    return render(request, 'usuarios/roles/delete.html', {'rol': rol})


# ==================== USUARIOS ====================

@solo_admin
def usuario_list(request):
    search = request.GET.get('search', '')
    usuarios = Usuario.objects.select_related('rol').order_by('nombre')
    if search:
        usuarios = usuarios.filter(Q(nombre__icontains=search) | Q(email__icontains=search))
    return render(request, 'usuarios/usuarios/lista.html', {'usuarios': usuarios, 'roles': Rol.objects.all(), 'search': search})


@solo_admin
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


@solo_admin
def usuario_edit(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre', '').strip()
        usuario.email = request.POST.get('email', '').strip().lower()
        usuario.rol_id = request.POST.get('rol_id', '')
        password = request.POST.get('password', '')
        if password:
            usuario.password = hashlib.sha256(password.encode()).hexdigest()
        usuario.save()
        messages.success(request, 'Usuario actualizado')
        return redirect('usuario_list')
    return render(request, 'usuarios/usuarios/form.html', {'action': 'editar', 'usuario': usuario, 'roles': Rol.objects.all()})


@solo_admin
def usuario_delete(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.id == request.session.get('user_id'):
        messages.error(request, 'No puedes eliminarte a ti mismo')
        return redirect('usuario_list')
    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado')
        return redirect('usuario_list')
    return render(request, 'usuarios/usuarios/delete.html', {'usuario': usuario})


# ==================== EMPLEADOS ====================

@solo_admin
def empleado_list(request):
    empleados = Empleado.objects.select_related('usuario__rol', 'ruta').order_by('usuario__nombre')
    return render(request, 'usuarios/empleados/lista.html', {'empleados': empleados, 'rutas': Ruta.objects.all()})


@solo_admin
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
    return render(request, 'usuarios/empleados/form.html', {'action': 'crear', 'empleado': None, 'usuarios': Usuario.objects.filter(activo=True, empleado__isnull=True), 'rutas': Ruta.objects.all()})


@solo_admin
def empleado_edit(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        empleado.telefono = request.POST.get('telefono', '').strip()
        empleado.direccion = request.POST.get('direccion', '').strip()
        empleado.ruta_id = request.POST.get('ruta_id') or None
        empleado.save()
        messages.success(request, 'Empleado actualizado')
        return redirect('empleado_list')
    return render(request, 'usuarios/empleados/form.html', {'action': 'editar', 'empleado': empleado, 'usuarios': [empleado.usuario], 'rutas': Ruta.objects.all()})



@solo_admin
def empleado_delete(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        empleado.delete()
        messages.success(request, 'Empleado eliminado')
        return redirect('empleado_list')
    return render(request, 'usuarios/empleados/delete.html', {'empleado': empleado})
    