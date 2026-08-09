# apps/finanzas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from apps.ventas.models import Venta, DetalleVenta
from apps.cobros.models import Cobro
from apps.inventario.models import Producto
from apps.rutas.models import Ruta
from .models import Compra, DetalleCompra, CajaRuta, Ingreso


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


def get_decimal(value):
    """Convierte valor a Decimal de forma segura"""
    if value is None:
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return Decimal('0')


# ==================== DASHBOARD ====================

@requiere_login
@solo_admin
def dashboard(request):
    """Dashboard financiero integral con filtros de fecha"""
    fecha_inicio_str = request.GET.get('fecha_inicio', '').strip()
    fecha_fin_str = request.GET.get('fecha_fin', '').strip()

    ventas_qs = Venta.objects.all()
    cobros_qs = Cobro.objects.all()
    compras_qs = Compra.objects.all()
    ingresos_qs = Ingreso.objects.all()
    detalles_qs = DetalleVenta.objects.select_related('producto')

    if fecha_inicio_str:
        try:
            f_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            ventas_qs = ventas_qs.filter(created_at__gte=f_inicio)
            cobros_qs = cobros_qs.filter(created_at__gte=f_inicio)
            compras_qs = compras_qs.filter(fecha__gte=f_inicio)
            ingresos_qs = ingresos_qs.filter(fecha__gte=f_inicio)
            detalles_qs = detalles_qs.filter(venta__created_at__gte=f_inicio)
        except ValueError:
            pass

    if fecha_fin_str:
        try:
            f_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            ventas_qs = ventas_qs.filter(created_at__lte=f_fin)
            cobros_qs = cobros_qs.filter(created_at__lte=f_fin)
            compras_qs = compras_qs.filter(fecha__lte=f_fin)
            ingresos_qs = ingresos_qs.filter(fecha__lte=f_fin)
            detalles_qs = detalles_qs.filter(venta__created_at__lte=f_fin)
        except ValueError:
            pass

    # Totales de Ventas
    ventas_subtotal = get_decimal(ventas_qs.aggregate(t=Sum('subtotal'))['t'])
    ventas_descuento = get_decimal(ventas_qs.aggregate(t=Sum('descuento'))['t'])
    ventas_total = get_decimal(ventas_qs.aggregate(t=Sum('total'))['t'])
    ventas_contado = get_decimal(ventas_qs.filter(tipo='CONTADO').aggregate(t=Sum('total'))['t'])
    ventas_credito = get_decimal(ventas_qs.filter(tipo='CREDITO').aggregate(t=Sum('total'))['t'])
    ventas_pendientes = get_decimal(ventas_qs.filter(estado='PENDIENTE').aggregate(t=Sum('total'))['t'])

    # Totales de Cobros por Método
    cobros_total = get_decimal(cobros_qs.aggregate(t=Sum('monto'))['t'])
    cobros_efectivo = get_decimal(cobros_qs.filter(metodo='EFECTIVO').aggregate(t=Sum('monto'))['t'])
    cobros_transferencia = get_decimal(cobros_qs.filter(metodo='TRANSFERENCIA').aggregate(t=Sum('monto'))['t'])
    cobros_yape = get_decimal(cobros_qs.filter(metodo='YAPE').aggregate(t=Sum('monto'))['t'])
    cobros_plin = get_decimal(cobros_qs.filter(metodo='PLIN').aggregate(t=Sum('monto'))['t'])

    # Compras e Ingresos
    compras_total = get_decimal(compras_qs.aggregate(t=Sum('total'))['t'])
    ingresos_extra = get_decimal(ingresos_qs.aggregate(t=Sum('monto'))['t'])

    # Liquidez Disponible
    liquidez = (cobros_total + ingresos_extra) - compras_total

    # Cálculo de Ganancias
    ingresos_ventas = sum(get_decimal(d.subtotal) for d in detalles_qs)
    costos_ventas = sum(get_decimal(getattr(d.producto, 'precio_compra', Decimal('0'))) * d.cantidad for d in detalles_qs)
    ganancias = ingresos_ventas - costos_ventas

    # Métricas de Inventario
    productos_total = Producto.objects.count()
    productos_sin_stock = Producto.objects.filter(stock_principal=0).count()
    productos_bajo_stock = Producto.objects.filter(stock_principal__gt=0, stock_principal__lt=5).count()

    # Cajas por Ruta recientes
    caja_rutas = CajaRuta.objects.all().select_related('ruta')[:10]
    total_caja_rutas = sum(get_decimal(c.total_ventas) for c in caja_rutas)

    context = {
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'ventas_subtotal': ventas_subtotal,
        'ventas_descuento': ventas_descuento,
        'ventas_total': ventas_total,
        'ventas_contado': ventas_contado,
        'ventas_credito': ventas_credito,
        'ventas_pendientes': ventas_pendientes,
        'cobros_total': cobros_total,
        'cobros_efectivo': cobros_efectivo,
        'cobros_transferencia': cobros_transferencia,
        'cobros_yape': cobros_yape,
        'cobros_plin': cobros_plin,
        'compras_total': compras_total,
        'ingresos_extra': ingresos_extra,
        'liquidez': liquidez,
        'ingresos': ingresos_ventas,
        'costos': costos_ventas,
        'ganancias': ganancias,
        'productos_total': productos_total,
        'productos_sin_stock': productos_sin_stock,
        'productos_bajo_stock': productos_bajo_stock,
        'caja_rutas': caja_rutas,
        'total_caja_rutas': total_caja_rutas,
    }

    return render(request, 'finanzas/dashboard.html', context)


# ==================== REPORTE DE VENTAS ====================

@requiere_login
@solo_admin
def reporte_ventas(request):
    """Reporte detallado y filtrable de ventas y cobros"""
    fecha_inicio_str = request.GET.get('fecha_inicio', '').strip()
    fecha_fin_str = request.GET.get('fecha_fin', '').strip()
    ruta_id = request.GET.get('ruta_id', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    estado = request.GET.get('estado', '').strip()

    ventas_qs = Venta.objects.select_related('cliente', 'ruta', 'cliente__ruta').order_by('-created_at')

    if fecha_inicio_str:
        try:
            ventas_qs = ventas_qs.filter(created_at__gte=datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        except ValueError: pass

    if fecha_fin_str:
        try:
            ventas_qs = ventas_qs.filter(created_at__lte=datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except ValueError: pass

    if ruta_id:
        ventas_qs = ventas_qs.filter(Q(ruta_id=ruta_id) | Q(cliente__ruta_id=ruta_id))

    if tipo:
        ventas_qs = ventas_qs.filter(tipo=tipo)

    if estado:
        ventas_qs = ventas_qs.filter(estado=estado)

    ventas = list(ventas_qs)
    total_ventas_subtotal = Decimal('0')
    total_ventas_descuento = Decimal('0')
    total_ventas_monto = Decimal('0')
    total_cobrado_monto = Decimal('0')
    total_pendiente_monto = Decimal('0')

    for v in ventas:
        cobros_sum = Cobro.objects.filter(venta=v).aggregate(t=Sum('monto'))['t'] or Decimal('0')
        v.cobrado = cobros_sum
        v.pendiente = (v.total - cobros_sum) if (v.total - cobros_sum) > Decimal('0') else Decimal('0')
        
        total_ventas_subtotal += v.subtotal
        total_ventas_descuento += v.descuento
        total_ventas_monto += v.total
        total_cobrado_monto += v.cobrado
        total_pendiente_monto += v.pendiente

    rutas = Ruta.objects.all().order_by('nombre')

    return render(request, 'finanzas/reporte_ventas.html', {
        'ventas': ventas,
        'rutas': rutas,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'ruta_id': ruta_id,
        'tipo': tipo,
        'estado': estado,
        'total_ventas_subtotal': total_ventas_subtotal,
        'total_ventas_descuento': total_ventas_descuento,
        'total_ventas_monto': total_ventas_monto,
        'total_cobrado_monto': total_cobrado_monto,
        'total_pendiente_monto': total_pendiente_monto,
    })


# ==================== COMPRAS ====================

@requiere_login
@solo_admin
def compra_list(request):
    """Lista de compras realizadas"""
    compras = Compra.objects.all().order_by('-fecha')
    total_compras = sum((c.total for c in compras), Decimal('0'))

    return render(request, 'finanzas/compras/lista.html', {
        'compras': compras,
        'total_compras': total_compras
    })


@requiere_login
@solo_admin
def compra_create(request):
    """Crear nueva compra a proveedor"""
    if request.method == 'POST':
        proveedor = request.POST.get('proveedor', '').strip()

        if not proveedor:
            messages.error(request, 'El nombre del proveedor es obligatorio.')
            return redirect('compra_create')

        producto_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')
        precios = request.POST.getlist('precio[]')

        if not producto_ids:
            messages.error(request, 'Debes agregar al menos un producto.')
            return redirect('compra_create')

        items_validos = []
        for i, p_id in enumerate(producto_ids):
            if not p_id:
                continue
            cant_str = cantidades[i] if i < len(cantidades) else '1'
            prec_str = precios[i] if i < len(precios) else '0'
            try:
                cant = int(cant_str)
                prec = Decimal(prec_str)
                if cant > 0 and prec >= Decimal('0'):
                    items_validos.append((p_id, cant, prec))
            except (ValueError, TypeError):
                pass

        if not items_validos:
            messages.error(request, 'Ingresa productos con cantidades y precios válidos.')
            return redirect('compra_create')

        total = Decimal('0')
        compra = Compra.objects.create(proveedor=proveedor, total=Decimal('0'))

        for p_id, cantidad, precio in items_validos:
            try:
                producto = Producto.objects.get(pk=p_id)
                subtotal = precio * cantidad
                total += subtotal

                DetalleCompra.objects.create(
                    compra=compra,
                    producto=producto,
                    cantidad=cantidad,
                    precio=precio
                )

                # Incrementar stock principal y actualizar precio de compra
                producto.stock_principal += cantidad
                if precio > Decimal('0'):
                    producto.precio_compra = precio
                producto.save()
            except Producto.DoesNotExist:
                pass

        compra.total = total
        compra.save()

        messages.success(request, f'Compra #{compra.id} a "{proveedor}" por ${total|floatformat:2} guardada correctamente.')
        return redirect('compra_list')

    productos = Producto.objects.all().order_by('nombre')
    return render(request, 'finanzas/compras/form.html', {'productos': productos})


@requiere_login
@solo_admin
def compra_detail(request, pk):
    """Detalle de una compra registrada"""
    compra = get_object_or_404(Compra, pk=pk)
    detalles = DetalleCompra.objects.filter(compra=compra).select_related('producto')

    for d in detalles:
        d.subtotal = d.precio * d.cantidad

    return render(request, 'finanzas/compras/detalle.html', {
        'compra': compra,
        'detalles': detalles
    })


# ==================== INGRESOS ====================

@requiere_login
@solo_admin
def ingreso_list(request):
    """Lista de otros ingresos"""
    ingresos = Ingreso.objects.all().order_by('-fecha')
    total_ingresos = sum((i.monto for i in ingresos), Decimal('0'))

    return render(request, 'finanzas/ingresos/lista.html', {
        'ingresos': ingresos,
        'total_ingresos': total_ingresos
    })


@requiere_login
@solo_admin
def ingreso_create(request):
    """Registrar un nuevo ingreso extra"""
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion', '').strip()
        monto_raw = request.POST.get('monto', '0').strip()

        try:
            monto = Decimal(monto_raw)
        except Exception:
            monto = Decimal('0')

        if not descripcion or monto <= Decimal('0'):
            messages.error(request, 'Ingresa una descripción válida y un monto mayor a 0.')
            return redirect('ingreso_create')

        Ingreso.objects.create(descripcion=descripcion, monto=monto)
        messages.success(request, f'Ingreso "{descripcion}" por ${monto} registrado exitosamente.')
        return redirect('ingreso_list')

    return render(request, 'finanzas/ingresos/form.html')


@requiere_login
@solo_admin
def ingreso_delete(request, pk):
    """Eliminar un registro de ingreso"""
    ingreso = get_object_or_404(Ingreso, pk=pk)
    if request.method == 'POST':
        ingreso.delete()
        messages.success(request, 'Registro de ingreso eliminado.')
        return redirect('ingreso_list')
    return render(request, 'finanzas/ingresos/delete.html', {'ingreso': ingreso})


# ==================== CAJA RUTAS ====================

@requiere_login
@solo_admin
def caja_ruta_list(request):
    """Lista de cierres de caja por rutas"""
    cajas = CajaRuta.objects.all().select_related('ruta').order_by('-fecha')

    cajas_list = []
    for c in cajas:
        diferencia = c.total_entregado - c.total_cobros
        cajas_list.append({
            'caja': c,
            'diferencia': diferencia,
            'estado_cuadre': 'CUADRADO' if diferencia == Decimal('0') else ('SOBRANTE' if diferencia > Decimal('0') else 'FALTANTE')
        })

    return render(request, 'finanzas/caja_ruta/lista.html', {'cajas_list': cajas_list})


@requiere_login
@solo_admin
def caja_ruta_create(request):
    """Registrar arqueo y cierre de caja por ruta"""
    if request.method == 'POST':
        ruta_id = request.POST.get('ruta_id')
        fecha_str = request.POST.get('fecha', '').strip()
        entregado_raw = request.POST.get('total_entregado', '0').strip()

        if not ruta_id or not fecha_str:
            messages.error(request, 'Selecciona una ruta y una fecha.')
            return redirect('caja_ruta_create')

        try:
            total_entregado = Decimal(entregado_raw)
            fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Formato de fecha u monto inválido.')
            return redirect('caja_ruta_create')

        ruta = get_object_or_404(Ruta, pk=ruta_id)

        # Ventas del día en esa ruta
        ventas_dia = Venta.objects.filter(
            Q(ruta=ruta) | Q(cliente__ruta=ruta),
            created_at__date=fecha_dt
        )
        total_ventas = ventas_dia.aggregate(t=Sum('total'))['t'] or Decimal('0')

        # Cobros del día en esa ruta
        cobros_dia = Cobro.objects.filter(
            Q(venta__ruta=ruta) | Q(venta__cliente__ruta=ruta),
            created_at__date=fecha_dt
        )
        total_cobros = cobros_dia.aggregate(t=Sum('monto'))['t'] or Decimal('0')

        # Crear o actualizar CajaRuta para ese día y ruta
        caja, created = CajaRuta.objects.update_or_create(
            ruta=ruta,
            fecha=fecha_dt,
            defaults={
                'total_ventas': total_ventas,
                'total_cobros': total_cobros,
                'total_entregado': total_entregado
            }
        )

        accion_msg = "creado" if created else "actualizado"
        messages.success(request, f'Cierre de caja {accion_msg} para la ruta {ruta.nombre} ({fecha_str}).')
        return redirect('caja_ruta_list')

    rutas = Ruta.objects.all().order_by('nombre')
    fecha_hoy = timezone.now().strftime('%Y-%m-%d')
    return render(request, 'finanzas/caja_ruta/form.html', {
        'rutas': rutas,
        'fecha_hoy': fecha_hoy
    })