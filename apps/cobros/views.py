# apps/cobros/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction, models
from django.core.paginator import Paginator
from django.http import HttpResponse
from decimal import Decimal
import json

from .models import Cobro
from apps.ventas.models import Venta
from apps.ventas.utils_pdf import generar_pdf_cobro
from apps.rutas.models import Ruta


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

    total_cobrado = sum((c.monto for c in cobros), Decimal('0'))

    paginator = Paginator(cobros, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'cobros/lista.html', {
        'cobros': page_obj,
        'page_obj': page_obj,
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

            venta_objetivo.saldo = max(Decimal('0'), venta_objetivo.saldo - monto)
            if venta_objetivo.saldo <= Decimal('0'):
                venta_objetivo.estado = 'PAGADA'
                venta_objetivo.saldo = Decimal('0')
                venta_objetivo.proximo_cobro = None
            else:
                from apps.ventas.views import calcular_proximo_cobro
                venta_objetivo.proximo_cobro = calcular_proximo_cobro(venta_objetivo.frecuencia_cobro)
            venta_objetivo.save()

        messages.success(request, f'Cobro de ${monto} registrado exitosamente para {cliente.nombre} (Venta #{venta_objetivo.id}).')
        return redirect('cobro_list')

    # GET request: Obtener ventas a crédito pendientes y estructurar JSON para frontend
    ventas_qs = Venta.objects.filter(
        tipo='CREDITO',
        estado='PENDIENTE'
    ).select_related('cliente', 'ruta', 'cliente__ruta').order_by(
        models.F('proximo_cobro').asc(nulls_last=True), '-created_at'
    )

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
                'frecuencia': v.get_frecuencia_cobro_display(),
                'proximo_cobro': v.proximo_cobro.strftime('%d/%m/%Y') if v.proximo_cobro else 'Sin fecha',
                'proximo_cobro_iso': v.proximo_cobro.strftime('%Y-%m-%d') if v.proximo_cobro else '',
                'total': float(v.total),
                'cobrado': float(cobrado),
                'pendiente': float(pendiente)
            })

    clientes_json = json.dumps(list(clientes_dict.values()))

    cedula_param = request.GET.get('cedula', '').strip()
    venta_id_param = request.GET.get('venta_id', '').strip()

    from datetime import date
    return render(request, 'cobros/form.html', {
        'clientes_json': clientes_json,
        'clientes_list': list(clientes_dict.values()),
        'es_admin': es_admin,
        'ruta_nombre': getattr(empleado.ruta, 'nombre', 'N/A') if (empleado and empleado.ruta) else ('Todas' if es_admin else 'Sin Ruta'),
        'today_iso': date.today().strftime('%Y-%m-%d'),
        'cedula_param': cedula_param,
        'venta_id_param': venta_id_param,
    })


@requiere_login
def cobros_pendientes(request):
    """Listado detallado de ventas a crédito con saldo pendiente por cobrar"""
    from datetime import date
    user_id = request.session.get('user_id')
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')
    empleado, ruta_id = _get_empleado_info(user_id)

    search = request.GET.get('search', '').strip()
    ruta_filtro = request.GET.get('ruta_id', '').strip()
    color_filtro = request.GET.get('color', '').strip().upper()
    orden = request.GET.get('orden', 'proximo_asc').strip()

    today = date.today()

    ventas_qs = Venta.objects.filter(
        tipo='CREDITO',
        estado='PENDIENTE'
    ).select_related('cliente', 'ruta', 'cliente__ruta', 'usuario')

    if color_filtro == 'ROJO':
        ventas_qs = ventas_qs.filter(proximo_cobro__isnull=False, proximo_cobro__lt=today)
    elif color_filtro == 'NARANJA':
        ventas_qs = ventas_qs.filter(proximo_cobro=today)
    elif color_filtro == 'VERDE':
        ventas_qs = ventas_qs.filter(proximo_cobro__gt=today)

    if orden == 'proximo_desc':
        ventas_qs = ventas_qs.order_by(models.F('proximo_cobro').desc(nulls_last=True), '-created_at')
    elif orden == 'saldo_desc':
        ventas_qs = ventas_qs.order_by('-saldo', models.F('proximo_cobro').asc(nulls_last=True))
    elif orden == 'fecha_desc':
        ventas_qs = ventas_qs.order_by('-created_at')
    else:  # proximo_asc (default: más urgentes / próximos primero, nulos al final)
        ventas_qs = ventas_qs.order_by(models.F('proximo_cobro').asc(nulls_last=True), '-created_at')

    if not es_admin:
        if ruta_id:
            ventas_qs = ventas_qs.filter(models.Q(ruta_id=ruta_id) | models.Q(cliente__ruta_id=ruta_id))
        else:
            ventas_qs = Venta.objects.none()
    elif ruta_filtro:
        ventas_qs = ventas_qs.filter(models.Q(ruta_id=ruta_filtro) | models.Q(cliente__ruta_id=ruta_filtro))

    if search:
        ventas_qs = ventas_qs.filter(
            models.Q(cliente__nombre__icontains=search) |
            models.Q(cliente__numero_documento__icontains=search) |
            models.Q(id__icontains=search)
        )

    pendientes = []
    total_deuda_pendiente = Decimal('0')
    total_cobrado_acumulado = Decimal('0')
    total_ventas_bruto = Decimal('0')

    for v in ventas_qs:
        if v.saldo > Decimal('0'):
            cobrado_sum = Cobro.objects.filter(venta=v).aggregate(t=models.Sum('monto'))['t'] or Decimal('0')
            v.cobrado = cobrado_sum
            v.saldo_pendiente = v.saldo
            pendientes.append(v)
            total_deuda_pendiente += v.saldo
            total_cobrado_acumulado += cobrado_sum
            total_ventas_bruto += v.subtotal

    rutas = Ruta.objects.all().order_by('nombre')
    ruta_nombre = getattr(empleado.ruta, 'nombre', 'N/A') if (empleado and empleado.ruta) else ('Todas' if es_admin else 'Sin Ruta')

    return render(request, 'cobros/pendientes.html', {
        'pendientes': pendientes,
        'total_deuda_pendiente': total_deuda_pendiente,
        'total_cobrado_acumulado': total_cobrado_acumulado,
        'total_ventas_bruto': total_ventas_bruto,
        'rutas': rutas,
        'search': search,
        'ruta_filtro': ruta_filtro,
        'color_filtro': color_filtro,
        'orden': orden,
        'es_admin': es_admin,
        'ruta_nombre': ruta_nombre,
        'today': today
    })


@requiere_login
def cobro_ruta_mapa(request):
    """Vista interactiva con mapa Leaflet y generador de ruta de navegación en Google Maps"""
    from datetime import date
    import json
    user_id = request.session.get('user_id')
    rol_nombre = request.session.get('rol_nombre')
    es_admin = (rol_nombre == 'ADMIN')
    empleado, ruta_id = _get_empleado_info(user_id)

    search = request.GET.get('search', '').strip()
    ruta_filtro = request.GET.get('ruta_id', '').strip()
    color_filtro = request.GET.get('color', '').strip().upper()

    today = date.today()

    ventas_qs = Venta.objects.filter(
        tipo='CREDITO',
        estado='PENDIENTE'
    ).select_related('cliente', 'ruta', 'cliente__ruta', 'usuario')

    if color_filtro == 'ROJO':
        ventas_qs = ventas_qs.filter(proximo_cobro__isnull=False, proximo_cobro__lt=today)
    elif color_filtro == 'NARANJA':
        ventas_qs = ventas_qs.filter(proximo_cobro=today)
    elif color_filtro == 'VERDE':
        ventas_qs = ventas_qs.filter(models.Q(proximo_cobro__gt=today) | models.Q(proximo_cobro__isnull=True))
    elif color_filtro == 'TODOS':
        pass
    else:
        # MEZCLADOS (Predeterminado): mezcla cobros del día (proximo_cobro == today) y vencidos (proximo_cobro < today)
        ventas_qs = ventas_qs.filter(proximo_cobro__isnull=False, proximo_cobro__lte=today)

    ventas_qs = ventas_qs.order_by(models.F('proximo_cobro').asc(nulls_last=True), '-created_at')

    if not es_admin:
        if ruta_id:
            ventas_qs = ventas_qs.filter(models.Q(ruta_id=ruta_id) | models.Q(cliente__ruta_id=ruta_id))
        else:
            ventas_qs = Venta.objects.none()
    elif ruta_filtro:
        ventas_qs = ventas_qs.filter(models.Q(ruta_id=ruta_filtro) | models.Q(cliente__ruta_id=ruta_filtro))

    if search:
        ventas_qs = ventas_qs.filter(
            models.Q(cliente__nombre__icontains=search) |
            models.Q(cliente__numero_documento__icontains=search) |
            models.Q(id__icontains=search)
        )

    puntos_mapa = []
    total_deuda = Decimal('0')

    for index, v in enumerate(ventas_qs, start=1):
        if v.saldo > Decimal('0'):
            total_deuda += v.saldo
            has_gps = bool(v.cliente.latitud and v.cliente.longitud)
            
            estado_cobro = 'VERDE'
            if v.proximo_cobro:
                if v.proximo_cobro < today:
                    estado_cobro = 'ROJO'
                elif v.proximo_cobro == today:
                    estado_cobro = 'NARANJA'

            puntos_mapa.append({
                'orden': index,
                'venta_id': v.id,
                'cliente_id': v.cliente.numero_documento,
                'cliente_nombre': v.cliente.nombre,
                'telefono': v.cliente.telefono or '',
                'direccion': v.cliente.direccion or '',
                'ruta': v.cliente.ruta.nombre if (v.cliente and v.cliente.ruta) else (v.ruta.nombre if v.ruta else 'Sin Ruta'),
                'saldo': float(v.saldo),
                'subtotal': float(v.subtotal),
                'proximo_cobro': v.proximo_cobro.strftime('%d/%m/%Y') if v.proximo_cobro else 'Sin fecha',
                'proximo_cobro_iso': v.proximo_cobro.strftime('%Y-%m-%d') if v.proximo_cobro else '',
                'estado_cobro': estado_cobro,
                'lat': float(v.cliente.latitud) if has_gps else None,
                'lng': float(v.cliente.longitud) if has_gps else None,
                'has_gps': has_gps,
            })

    # Filtrar solo puntos con GPS para trazar la ruta en Google Maps
    puntos_con_coords = [p for p in puntos_mapa if p['has_gps']]
    google_maps_url = ''
    if puntos_con_coords:
        if len(puntos_con_coords) == 1:
            dest = f"{puntos_con_coords[0]['lat']},{puntos_con_coords[0]['lng']}"
            google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={dest}&travelmode=driving"
        else:
            origin = f"{puntos_con_coords[0]['lat']},{puntos_con_coords[0]['lng']}"
            destination = f"{puntos_con_coords[-1]['lat']},{puntos_con_coords[-1]['lng']}"
            if len(puntos_con_coords) > 2:
                waypoints = "|".join([f"{p['lat']},{p['lng']}" for p in puntos_con_coords[1:-1]])
                google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&waypoints={waypoints}&travelmode=driving"
            else:
                google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&travelmode=driving"

    rutas = Ruta.objects.all().order_by('nombre')
    ruta_nombre = getattr(empleado.ruta, 'nombre', 'N/A') if (empleado and empleado.ruta) else ('Todas' if es_admin else 'Sin Ruta')

    return render(request, 'cobros/ruta_mapa.html', {
        'puntos_mapa_json': json.dumps(puntos_mapa),
        'puntos_mapa': puntos_mapa,
        'puntos_con_coords_count': len(puntos_con_coords),
        'total_puntos_count': len(puntos_mapa),
        'total_deuda': total_deuda,
        'google_maps_url': google_maps_url,
        'rutas': rutas,
        'search': search,
        'ruta_filtro': ruta_filtro,
        'color_filtro': color_filtro,
        'es_admin': es_admin,
        'ruta_nombre': ruta_nombre,
        'today': today
    })


@requiere_login
def cobro_pdf(request, pk):
    """Generar y descargar recibo PDF de un cobro"""
    cobro = get_object_or_404(Cobro, pk=pk)
    pdf_buffer = generar_pdf_cobro(cobro)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="recibo_cobro_{cobro.id}.pdf"'
    return response

