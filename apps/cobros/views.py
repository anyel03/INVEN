# apps/cobros/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction, models
from decimal import Decimal
import json

from .models import Cobro
from apps.ventas.models import Venta


# ==================== HELPERS ====================

def requiere_login(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def _get_empleado_info(user_id):
    """Devuelve (empleado, ruta_id) para un usuario de tipo empleado."""
    from apps.usuarios.models import Empleado
    try:
        empleado = Empleado.objects.filter(usuario_id=user_id).select_related('ruta').first()
        ruta_id = getattr(empleado, 'ruta_id', None)
        return empleado, ruta_id
    except Exception:
        return None, None


# ==================== COBROS ====================

@requiere_login
def cobro_list(request):
    """Lista de cobros (ADMIN ve todos, EMPLEADO ve solo los de su ruta)"""
    search = request.GET.get('search', '').strip()
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')
    user_id = request.session.get('user_id')

    empleado = None
    ruta_id = None
    ruta_nombre = 'Todas las Rutas'

    if es_admin:
        cobros = Cobro.objects.select_related('venta__cliente', 'venta__ruta', 'venta__cliente__ruta').order_by('-created_at')
    else:
        empleado, ruta_id = _get_empleado_info(user_id)
        if ruta_id:
            ruta_nombre = getattr(empleado.ruta, 'nombre', f'Ruta #{ruta_id}')
            cobros = Cobro.objects.filter(
                models.Q(venta__ruta_id=ruta_id) | models.Q(venta__cliente__ruta_id=ruta_id)
            ).select_related('venta__cliente', 'venta__ruta', 'venta__cliente__ruta').order_by('-created_at')
        else:
            ruta_nombre = 'Sin Ruta Asignada'
            cobros = Cobro.objects.none()

    if search:
        cobros = cobros.filter(
            models.Q(venta__cliente__nombre__icontains=search) |
            models.Q(venta__cliente__numero_documento__icontains=search) |
            models.Q(venta_id__icontains=search) |
            models.Q(id__icontains=search)
        )

    cobros_list = list(cobros)
    total_cobrado = sum((c.monto for c in cobros_list), Decimal('0'))

    return render(request, 'cobros/lista.html', {
        'cobros': cobros_list,
        'total_cobrado': total_cobrado,
        'search': search,
        'es_admin': es_admin,
        'ruta_nombre': ruta_nombre,
        'empleado': empleado
    })


@requiere_login
def cobro_create(request):
    """Registrar nuevo cobro solicitando la cédula del cliente"""
    user_id = request.session.get('user_id')
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')
    empleado, ruta_id = _get_empleado_info(user_id)

    if request.method == 'POST':
        cedula = request.POST.get('cedula', '').strip()
        venta_id = request.POST.get('venta_id', '').strip()
        metodo = request.POST.get('metodo', 'EFECTIVO')
        observacion = request.POST.get('observacion', '').strip()
        monto_raw = request.POST.get('monto', '0').strip()

        try:
            monto = Decimal(monto_raw)
        except Exception:
            monto = Decimal('0')

        if not cedula:
            messages.error(request, 'Debes ingresar el número de cédula del cliente.')
            return redirect('cobro_create')

        if monto <= Decimal('0'):
            messages.error(request, 'El monto debe ser mayor a 0.')
            return redirect('cobro_create')

        # Buscar cliente por número de cédula / documento
        from apps.clientes.models import Cliente
        try:
            cedula_num = int(cedula)
            clientes_qs = Cliente.objects.filter(numero_documento=cedula_num)
        except ValueError:
            clientes_qs = Cliente.objects.filter(numero_documento__icontains=cedula)

        if not es_admin and ruta_id:
            clientes_qs = clientes_qs.filter(models.Q(ruta_id=ruta_id) | models.Q(venta__ruta_id=ruta_id)).distinct()

        cliente = clientes_qs.first()

        if not cliente:
            if not es_admin and ruta_id:
                messages.error(request, f'No se encontró ningún cliente registrado con la cédula "{cedula}" en tu ruta.')
            else:
                messages.error(request, f'No se encontró ningún cliente registrado con la cédula "{cedula}".')
            return redirect('cobro_create')

        # Buscar ventas pendientes del cliente
        ventas_pendientes = Venta.objects.filter(
            cliente=cliente,
            tipo='CREDITO',
            estado='PENDIENTE'
        ).select_related('cliente', 'ruta')

        if not es_admin and ruta_id:
            ventas_pendientes = ventas_pendientes.filter(
                models.Q(ruta_id=ruta_id) | models.Q(cliente__ruta_id=ruta_id)
            )

        if not ventas_pendientes.exists():
            messages.error(request, f'El cliente {cliente.nombre} (Cédula: {cliente.numero_documento}) no tiene ventas pendientes por cobrar.')
            return redirect('cobro_create')

        venta_objetivo = None
        if venta_id:
            try:
                venta_objetivo = ventas_pendientes.get(pk=int(venta_id))
            except (Venta.DoesNotExist, ValueError):
                messages.error(request, 'La venta seleccionada no corresponde a este cliente o ya fue saldada.')
                return redirect('cobro_create')
        else:
            for v in ventas_pendientes.order_by('created_at'):
                cobros_prev = Cobro.objects.filter(venta=v).aggregate(total=models.Sum('monto'))['total'] or Decimal('0')
                if v.total - cobros_prev > Decimal('0'):
                    venta_objetivo = v
                    break

        if not venta_objetivo:
            messages.error(request, f'El cliente {cliente.nombre} no tiene saldos pendientes por cobrar.')
            return redirect('cobro_create')

        cobros_anteriores = Cobro.objects.filter(venta=venta_objetivo).aggregate(total=models.Sum('monto'))['total'] or Decimal('0')
        pendiente = venta_objetivo.total - cobros_anteriores

        if monto > pendiente:
            messages.error(request, f'El monto (${monto}) excede el saldo pendiente de la venta #${venta_objetivo.id} (${pendiente}).')
            return redirect('cobro_create')

        with transaction.atomic():
            Cobro.objects.create(
                venta=venta_objetivo,
                monto=monto,
                metodo=metodo,
                observacion=observacion
            )

            nuevo_cobrado = cobros_anteriores + monto
            if nuevo_cobrado >= venta_objetivo.total:
                venta_objetivo.estado = 'PAGADA'
                venta_objetivo.save()

        messages.success(request, f'Cobro de ${monto} registrado exitosamente para {cliente.nombre} (Venta #{venta_objetivo.id}).')
        return redirect('cobro_list')

    # GET request: Obtener ventas a crédito pendientes y estructurar JSON para frontend
    ventas_qs = Venta.objects.filter(
        tipo='CREDITO',
        estado='PENDIENTE'
    ).select_related('cliente', 'ruta', 'cliente__ruta')

    if not es_admin:
        if ruta_id:
            ventas_qs = ventas_qs.filter(
                models.Q(ruta_id=ruta_id) | models.Q(cliente__ruta_id=ruta_id)
            )
        else:
            ventas_qs = Venta.objects.none()

    clientes_dict = {}
    for v in ventas_qs:
        cobrado = Cobro.objects.filter(venta=v).aggregate(t=models.Sum('monto'))['t'] or Decimal('0')
        pendiente = v.total - cobrado
        if pendiente > Decimal('0'):
            c_doc = str(v.cliente.numero_documento)
            if c_doc not in clientes_dict:
                ruta_nombre = v.cliente.ruta.nombre if (v.cliente and v.cliente.ruta) else (v.ruta.nombre if v.ruta else 'Sin Ruta')
                clientes_dict[c_doc] = {
                    'cedula': c_doc,
                    'nombre': v.cliente.nombre,
                    'telefono': v.cliente.telefono or '',
                    'ruta': ruta_nombre,
                    'deuda_total': 0.0,
                    'ventas': []
                }
            clientes_dict[c_doc]['deuda_total'] += float(pendiente)
            clientes_dict[c_doc]['ventas'].append({
                'id': v.id,
                'fecha': v.created_at.strftime('%d/%m/%Y %H:%M') if v.created_at else '',
                'total': float(v.total),
                'cobrado': float(cobrado),
                'pendiente': float(pendiente)
            })

    clientes_json = json.dumps(list(clientes_dict.values()))

    return render(request, 'cobros/form.html', {
        'clientes_json': clientes_json,
        'clientes_list': list(clientes_dict.values()),
        'es_admin': es_admin,
        'ruta_nombre': getattr(empleado.ruta, 'nombre', 'N/A') if (empleado and empleado.ruta) else ('Todas' if es_admin else 'Sin Ruta')
    })