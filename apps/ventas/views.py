from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
from datetime import date, timedelta

from .models import Venta, DetalleVenta
from apps.clientes.models import Cliente
from apps.inventario.models import Producto, InventarioRuta
from apps.rutas.models import Ruta


# ==================== HELPERS ====================

def calcular_proximo_cobro(frecuencia, base_date=None):
    if not base_date:
        base_date = date.today()
    if frecuencia == 'SEMANAL':
        return base_date + timedelta(days=7)
    elif frecuencia == 'QUINCENAL':
        return base_date + timedelta(days=15)
    elif frecuencia == 'MENSUAL':
        return base_date + timedelta(days=30)
    elif frecuencia == 'COMPLETO':
        return base_date
    return base_date

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
        empleado = Empleado.objects.filter(
            usuario_id=user_id).select_related('ruta').first()
        ruta_id = getattr(empleado, 'ruta_id', None)
        return empleado, ruta_id
    except Exception:
        return None, None


def _obtener_contexto_venta(request):
    """Obtiene los datos base para los formularios de venta según el rol del usuario."""
    es_admin = request.session.get('rol_nombre') == 'ADMIN'
    empleado, ruta_emp_id = _get_empleado_info(request.session.get('user_id'))

    if es_admin:
        clientes = Cliente.objects.all().select_related('ruta').order_by('nombre')
        productos = Producto.objects.filter(
            stock_principal__gt=0).order_by('nombre')
        stock_por_producto = {}
        # Si el admin envió ruta_id por GET/POST
        ruta_admin_id = request.GET.get('ruta_id') or request.POST.get('ruta_id')
        if ruta_admin_id not in (None, '', 'null'):
            try:
                r_id = int(ruta_admin_id)
                qs = InventarioRuta.objects.filter(ruta_id=r_id).values_list('producto_id', 'cantidad')
                stock_por_producto = {pid: cant for (pid, cant) in qs}
            except (TypeError, ValueError):
                pass
    else:
        if ruta_emp_id:
            clientes = Cliente.objects.filter(ruta_id=ruta_emp_id).select_related('ruta').order_by('nombre')
            productos = (
                Producto.objects.filter(
                    inventarioruta__ruta_id=ruta_emp_id,
                    inventarioruta__cantidad__gt=0,
                )
                .distinct()
                .order_by('nombre')
            )
            qs = InventarioRuta.objects.filter(ruta_id=ruta_emp_id).values_list('producto_id', 'cantidad')
            stock_por_producto = {pid: cant for (pid, cant) in qs}
        else:
            clientes = Cliente.objects.none()
            productos = Producto.objects.none()
            stock_por_producto = {}
            messages.error(request, 'Tu usuario de empleado no tiene una ruta asignada')

    rutas = Ruta.objects.all()

    return {
        'es_admin': es_admin,
        'empleado': empleado,
        'ruta_emp_id': ruta_emp_id,
        'clientes': clientes,
        'productos': productos,
        'rutas': rutas,
        'stock_por_producto': stock_por_producto,
    }


# ==================== VENTAS ====================

@requiere_login
def venta_list(request):
    """Lista de ventas"""
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    tipo = request.GET.get('tipo', '')
    es_admin = request.session.get('rol_nombre') == 'ADMIN'

    ventas = Venta.objects.select_related(
        'cliente', 'usuario', 'ruta').order_by('-created_at')

    if not es_admin:
        empleado, ruta_emp_id = _get_empleado_info(request.session.get('user_id'))
        if ruta_emp_id:
            ventas = ventas.filter(
                Q(usuario_id=request.session['user_id']) | Q(ruta_id=ruta_emp_id)
            )
        else:
            ventas = ventas.filter(usuario_id=request.session['user_id'])

    if search:
        ventas = ventas.filter(
            Q(cliente__nombre__icontains=search) |
            Q(cliente__numero_documento__icontains=search) |
            Q(id__icontains=search)
        )
    if estado:
        ventas = ventas.filter(estado=estado)
    if tipo:
        ventas = ventas.filter(tipo=tipo)

    return render(request, 'ventas/lista.html', {
        'ventas': ventas,
        'search': search,
        'es_admin': es_admin,
        'today': date.today()
    })


@requiere_login
def venta_create(request):
    """Crear nueva venta"""
    ctx = _obtener_contexto_venta(request)
    es_admin = ctx['es_admin']
    ruta_emp_id = ctx['ruta_emp_id']

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        tipo = request.POST.get('tipo', 'CONTADO')
        descuento = Decimal(request.POST.get('descuento', '0') or '0')
        observaciones = request.POST.get('observaciones', '').strip()

        producto_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')

        if not cliente_id:
            messages.error(request, 'Selecciona un cliente')
            return redirect('venta_create')

        if not es_admin:
            if not ruta_emp_id:
                messages.error(request, 'Tu usuario no tiene una ruta asignada')
                return redirect('venta_create')
            if not Cliente.objects.filter(pk=cliente_id, ruta_id=ruta_emp_id).exists():
                messages.error(request, 'El cliente seleccionado no pertenece a tu ruta')
                return redirect('venta_create')
            ruta_id = ruta_emp_id
        else:
            ruta_id_raw = request.POST.get('ruta_id')
            if ruta_id_raw in (None, '', 'null'):
                messages.error(request, 'Selecciona una ruta para descontar inventario')
                return redirect('venta_create')
            try:
                ruta_id = int(ruta_id_raw)
            except (TypeError, ValueError):
                messages.error(request, 'Ruta inválida')
                return redirect('venta_create')

        if not producto_ids:
            messages.error(request, 'Agrega al menos un producto')
            return redirect('venta_create')

        pares_validos = []
        for i, prod_id in enumerate(producto_ids):
            if not prod_id:
                continue
            cant = cantidades[i] if i < len(cantidades) else '0'
            try:
                cant_int = int(cant)
            except (TypeError, ValueError):
                cant_int = 0

            if cant_int > 0:
                pares_validos.append((prod_id, cant_int))

        if not pares_validos:
            messages.error(request, 'Agrega al menos un producto con cantidad mayor a 0')
            return redirect('venta_create')

        total = Decimal('0')
        detalles = []

        for prod_id, cantidad in pares_validos:
            producto = Producto.objects.get(pk=prod_id)

            inv_ruta = InventarioRuta.objects.filter(
                ruta_id=ruta_id, producto_id=prod_id).first()
            stock = inv_ruta.cantidad if inv_ruta else 0

            if cantidad > stock:
                messages.error(
                    request, f'Stock insuficiente para {producto.nombre}. Stock en ruta: {stock}')
                return redirect('venta_create')

            subtotal = producto.precio_venta * cantidad
            total += subtotal

            detalles.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio': producto.precio_venta,
                'subtotal': subtotal
            })

        total -= descuento
        if total < Decimal('0'):
            total = Decimal('0')

        frecuencia_cobro = request.POST.get('frecuencia_cobro', 'SEMANAL')
        proximo_cobro = calcular_proximo_cobro(frecuencia_cobro)

        with transaction.atomic():
            venta = Venta.objects.create(
                cliente_id=cliente_id,
                usuario_id=request.session['user_id'],
                ruta_id=ruta_id,
                tipo=tipo,
                frecuencia_cobro=frecuencia_cobro,
                proximo_cobro=proximo_cobro,
                subtotal=total + descuento,
                descuento=descuento,
                total=total,
                saldo=Decimal('0') if tipo == 'CONTADO' else total,
                estado='PAGADA' if tipo == 'CONTADO' else 'PENDIENTE',
                observaciones=observaciones
            )

            for det in detalles:
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=det['producto'],
                    cantidad=det['cantidad'],
                    precio=det['precio'],
                    subtotal=det['subtotal']
                )

                inv_ruta = InventarioRuta.objects.select_for_update().get(
                    ruta_id=ruta_id, producto_id=det['producto'].id)
                inv_ruta.cantidad -= det['cantidad']
                if inv_ruta.cantidad <= 0:
                    inv_ruta.delete()
                else:
                    inv_ruta.save()

        messages.success(request, f'Venta #{venta.id} creada correctamente')
        return redirect('venta_list')

    return render(request, 'ventas/form.html', ctx)


@requiere_login
def venta_create_con_cliente(request):
    """Nueva venta permitiendo crear cliente en la misma vista"""
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        es_admin = request.session.get('rol_nombre') == 'ADMIN'
        empleado, ruta_emp_id = _get_empleado_info(request.session.get('user_id'))

        # ================= CREAR CLIENTE =================
        if form_type == 'cliente':
            numero_documento = request.POST.get('numero_documento', '').strip()
            nombre = request.POST.get('nombre', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            tipo_documento = request.POST.get('tipo_documento', 'CEDULA')

            if es_admin:
                ruta_id = request.POST.get('ruta_id') or None
            else:
                if not ruta_emp_id:
                    messages.error(request, 'No tienes una ruta asignada para crear clientes')
                    return redirect('venta_create_con_cliente')
                ruta_id = ruta_emp_id

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

                if request.FILES.get('foto_documento'):
                    cliente.foto_documento = request.FILES['foto_documento']
                    cliente.save()

                messages.success(request, f'Cliente "{nombre}" creado correctamente')

            ctx = _obtener_contexto_venta(request)
            return render(request, 'ventas/form_cliente_venta.html', ctx)

        # ================= CREAR VENTA =================
        cliente_id = request.POST.get('cliente_id')
        tipo = request.POST.get('tipo', 'CONTADO')
        descuento = Decimal(request.POST.get('descuento', '0') or '0')
        observaciones = request.POST.get('observaciones', '').strip()

        producto_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')

        if not cliente_id:
            messages.error(request, 'Selecciona un cliente')
            return redirect('venta_create_con_cliente')

        if not es_admin:
            if not ruta_emp_id:
                messages.error(request, 'Tu usuario no tiene una ruta asignada')
                return redirect('venta_create_con_cliente')
            if not Cliente.objects.filter(pk=cliente_id, ruta_id=ruta_emp_id).exists():
                messages.error(request, 'El cliente seleccionado no pertenece a tu ruta')
                return redirect('venta_create_con_cliente')
            ruta_id = ruta_emp_id
        else:
            ruta_id_raw = request.POST.get('ruta_id')
            if ruta_id_raw in (None, '', 'null'):
                messages.error(request, 'Selecciona una ruta para descontar inventario')
                return redirect('venta_create_con_cliente')
            try:
                ruta_id = int(ruta_id_raw)
            except (TypeError, ValueError):
                messages.error(request, 'Ruta inválida')
                return redirect('venta_create_con_cliente')

        if not producto_ids:
            messages.error(request, 'Agrega al menos un producto')
            return redirect('venta_create_con_cliente')

        pares_validos = []
        for i, prod_id in enumerate(producto_ids):
            if not prod_id:
                continue
            cant = cantidades[i] if i < len(cantidades) else '0'
            try:
                cant_int = int(cant)
            except (TypeError, ValueError):
                cant_int = 0

            if cant_int > 0:
                pares_validos.append((prod_id, cant_int))

        if not pares_validos:
            messages.error(request, 'Agrega al menos un producto con cantidad mayor a 0')
            return redirect('venta_create_con_cliente')

        total = Decimal('0')
        detalles = []

        for prod_id, cantidad in pares_validos:
            producto = Producto.objects.get(pk=prod_id)

            inv_ruta = InventarioRuta.objects.filter(
                ruta_id=ruta_id, producto_id=prod_id).first()
            stock = inv_ruta.cantidad if inv_ruta else 0

            if cantidad > stock:
                messages.error(
                    request, f'Stock insuficiente para {producto.nombre}. Stock en ruta: {stock}')
                return redirect('venta_create_con_cliente')

            subtotal = producto.precio_venta * cantidad
            total += subtotal

            detalles.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio': producto.precio_venta,
                'subtotal': subtotal
            })

        total -= descuento
        if total < Decimal('0'):
            total = Decimal('0')

        frecuencia_cobro = request.POST.get('frecuencia_cobro', 'SEMANAL')
        proximo_cobro = calcular_proximo_cobro(frecuencia_cobro)

        with transaction.atomic():
            venta = Venta.objects.create(
                cliente_id=cliente_id,
                usuario_id=request.session['user_id'],
                ruta_id=ruta_id,
                tipo=tipo,
                frecuencia_cobro=frecuencia_cobro,
                proximo_cobro=proximo_cobro,
                subtotal=total + descuento,
                descuento=descuento,
                total=total,
                saldo=Decimal('0') if tipo == 'CONTADO' else total,
                estado='PAGADA' if tipo == 'CONTADO' else 'PENDIENTE',
                observaciones=observaciones
            )

            for det in detalles:
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=det['producto'],
                    cantidad=det['cantidad'],
                    precio=det['precio'],
                    subtotal=det['subtotal']
                )

                inv_ruta = InventarioRuta.objects.select_for_update().get(
                    ruta_id=ruta_id, producto_id=det['producto'].id)
                inv_ruta.cantidad -= det['cantidad']
                if inv_ruta.cantidad <= 0:
                    inv_ruta.delete()
                else:
                    inv_ruta.save()

        messages.success(request, f'Venta #{venta.id} creada correctamente')
        return redirect('venta_list')

    ctx = _obtener_contexto_venta(request)
    return render(request, 'ventas/form_cliente_venta.html', ctx)


@requiere_login
def venta_detalle(request, pk):
    """Detalle de una venta"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'usuario', 'ruta'), pk=pk
    )
    detalles = DetalleVenta.objects.filter(
        venta=venta).select_related('producto')
    return render(request, 'ventas/detalle.html', {'venta': venta, 'detalles': detalles, 'today': date.today()})


@requiere_login
def ajax_stock_por_ruta(request):
    """Devuelve stock por producto para una ruta dada (solo ADMIN)."""
    if request.session.get('rol_nombre') != 'ADMIN':
        from django.http import JsonResponse
        return JsonResponse({'stocks': {}}, status=403)

    ruta_id = request.GET.get('ruta_id') or request.POST.get('ruta_id')
    try:
        ruta_id_int = int(ruta_id) if ruta_id not in (
            None, '', 'null') else None
    except (TypeError, ValueError):
        ruta_id_int = None

    if not ruta_id_int:
        from django.http import JsonResponse
        return JsonResponse({'stocks': {}})

    qs = InventarioRuta.objects.filter(
        ruta_id=ruta_id_int).values_list('producto_id', 'cantidad')
    stock_por_producto = {pid: cant for (pid, cant) in qs}

    from django.http import JsonResponse
    return JsonResponse({'stocks': stock_por_producto})
