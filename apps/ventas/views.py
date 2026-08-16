from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpResponse
from decimal import Decimal
from datetime import date, timedelta

from .models import Venta, DetalleVenta
from .utils_pdf import generar_pdf_venta
from .utils_whatsapp import generar_mensaje_venta, generar_url_whatsapp, enviar_whatsapp_servidor
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


def solo_admin(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        if request.session.get('rol_nombre') != 'ADMIN':
            messages.error(request, 'Solo el Administrador puede realizar esta acción.')
            return redirect('venta_list')
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

    paginator = Paginator(ventas, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'ventas/lista.html', {
        'ventas': page_obj,
        'page_obj': page_obj,
        'search': search,
        'estado': estado,
        'tipo': tipo,
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

            latitud_raw = request.POST.get('latitud', '').strip()
            longitud_raw = request.POST.get('longitud', '').strip()
            latitud = float(latitud_raw) if latitud_raw else None
            longitud = float(longitud_raw) if longitud_raw else None

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
                    latitud=latitud,
                    longitud=longitud,
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

        # Envío y disparo de notificación por WhatsApp
        telefono_cliente = venta.cliente.telefono if venta.cliente else None
        if telefono_cliente:
            msg = generar_mensaje_venta(venta)
            enviado = enviar_whatsapp_servidor(telefono_cliente, msg)
            wa_url = generar_url_whatsapp(telefono_cliente, msg)
            if wa_url:
                request.session['auto_whatsapp_url'] = wa_url
                if enviado:
                    messages.success(request, f'Venta #{venta.id} creada correctamente. Notificación de WhatsApp enviada al cliente.')
                else:
                    messages.success(request, f'Venta #{venta.id} creada correctamente. Abriendo notificación de WhatsApp...')
            else:
                messages.success(request, f'Venta #{venta.id} creada correctamente.')
        else:
            messages.success(request, f'Venta #{venta.id} creada correctamente.')

        return redirect('venta_detalle', pk=venta.id)

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
    
    auto_whatsapp_url = request.session.pop('auto_whatsapp_url', None)
    telefono_cliente = venta.cliente.telefono if venta.cliente else None
    msg = generar_mensaje_venta(venta) if telefono_cliente else None
    whatsapp_url = generar_url_whatsapp(telefono_cliente, msg) if telefono_cliente else None

    return render(request, 'ventas/detalle.html', {
        'venta': venta,
        'detalles': detalles,
        'today': date.today(),
        'auto_whatsapp_url': auto_whatsapp_url,
        'whatsapp_url': whatsapp_url
    })



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


@requiere_login
@solo_admin
def venta_edit(request, pk):
    """Editar una venta existente (solo ADMINISTRADOR)"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'ruta'), pk=pk
    )
    detalles_existentes = DetalleVenta.objects.filter(venta=venta).select_related('producto')

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        ruta_id_raw = request.POST.get('ruta_id')
        tipo = request.POST.get('tipo', 'CONTADO')
        frecuencia_cobro = request.POST.get('frecuencia_cobro', 'SEMANAL')
        descuento = Decimal(request.POST.get('descuento', '0') or '0')
        observaciones = request.POST.get('observaciones', '').strip()

        producto_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')

        if not cliente_id:
            messages.error(request, 'Selecciona un cliente.')
            return redirect('venta_edit', pk=pk)

        try:
            ruta_id = int(ruta_id_raw) if ruta_id_raw else (venta.ruta_id or 1)
        except (TypeError, ValueError):
            messages.error(request, 'Ruta inválida.')
            return redirect('venta_edit', pk=pk)

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
            messages.error(request, 'Agrega al menos un producto con cantidad mayor a 0.')
            return redirect('venta_edit', pk=pk)

        try:
            with transaction.atomic():
                # 1. Devolver el stock actual del inventario de la ruta antes de editar
                old_ruta_id = venta.ruta_id or ruta_id
                for d in detalles_existentes:
                    inv_old, _ = InventarioRuta.objects.get_or_create(
                        ruta_id=old_ruta_id,
                        producto=d.producto,
                        defaults={'cantidad': 0}
                    )
                    inv_old.cantidad += d.cantidad
                    inv_old.save()

                # 2. Verificar y descontar el nuevo stock en la ruta seleccionada
                detalles_nuevos = []
                subtotal_acum = Decimal('0')

                for prod_id, cantidad in pares_validos:
                    producto = Producto.objects.get(pk=prod_id)
                    inv_ruta = InventarioRuta.objects.filter(
                        ruta_id=ruta_id, producto_id=prod_id).first()
                    stock_disp = inv_ruta.cantidad if inv_ruta else 0

                    if cantidad > stock_disp:
                        messages.error(
                            request, f'Stock insuficiente para {producto.nombre}. Stock disponible en ruta: {stock_disp}'
                        )
                        raise ValueError(f'Stock insuficiente para {producto.nombre}')

                    subtotal_item = producto.precio_venta * cantidad
                    subtotal_acum += subtotal_item
                    detalles_nuevos.append({
                        'producto': producto,
                        'cantidad': cantidad,
                        'precio': producto.precio_venta,
                        'subtotal': subtotal_item,
                        'inv_ruta': inv_ruta
                    })

                total_nuevo = max(Decimal('0'), subtotal_acum - descuento)

                # 3. Eliminar los detalles anteriores y crear los nuevos
                DetalleVenta.objects.filter(venta=venta).delete()

                for det in detalles_nuevos:
                    DetalleVenta.objects.create(
                        venta=venta,
                        producto=det['producto'],
                        cantidad=det['cantidad'],
                        precio=det['precio'],
                        subtotal=det['subtotal']
                    )
                    inv_r = det['inv_ruta']
                    inv_r.cantidad -= det['cantidad']
                    if inv_r.cantidad <= 0:
                        inv_r.delete()
                    else:
                        inv_r.save()

                # 4. Recalcular saldo y estado considerando cobros realizados
                total_cobrado = Cobro.objects.filter(venta=venta).aggregate(t=Sum('monto'))['t'] or Decimal('0')

                if tipo == 'CONTADO':
                    saldo_nuevo = Decimal('0')
                    estado_nuevo = 'PAGADA'
                    proximo_cobro_nuevo = None
                else:
                    saldo_nuevo = max(Decimal('0'), total_nuevo - total_cobrado)
                    if saldo_nuevo == Decimal('0'):
                        estado_nuevo = 'PAGADA'
                        proximo_cobro_nuevo = None
                    else:
                        estado_nuevo = 'PENDIENTE'
                        proximo_cobro_nuevo = venta.proximo_cobro or calcular_proximo_cobro(frecuencia_cobro)

                # 5. Actualizar la Venta
                venta.cliente_id = cliente_id
                venta.ruta_id = ruta_id
                venta.tipo = tipo
                venta.frecuencia_cobro = frecuencia_cobro
                venta.proximo_cobro = proximo_cobro_nuevo
                venta.subtotal = subtotal_acum
                venta.descuento = descuento
                venta.total = total_nuevo
                venta.saldo = saldo_nuevo
                venta.estado = estado_nuevo
                venta.observaciones = observaciones
                venta.save()

            messages.success(request, f'Venta #{venta.id} modificada correctamente.')
            return redirect('venta_detalle', pk=venta.id)

        except ValueError:
            return redirect('venta_edit', pk=pk)

    # Contexto para vista GET
    clientes = Cliente.objects.all().order_by('nombre')
    rutas = Ruta.objects.all().order_by('nombre')
    productos = Producto.objects.all().order_by('nombre')

    # Diccionario de cantidades actuales por producto
    cantidades_actuales = {d.producto_id: d.cantidad for d in detalles_existentes}

    # Stock en ruta para la plantilla
    ruta_id_actual = venta.ruta_id
    stock_por_producto = {}
    if ruta_id_actual:
        inventarios = InventarioRuta.objects.filter(ruta_id=ruta_id_actual)
        for inv in inventarios:
            cant_reservada = cantidades_actuales.get(inv.producto_id, 0)
            stock_por_producto[inv.producto_id] = inv.cantidad + cant_reservada

    return render(request, 'ventas/form_edit.html', {
        'venta': venta,
        'detalles_existentes': detalles_existentes,
        'cantidades_actuales': cantidades_actuales,
        'clientes': clientes,
        'rutas': rutas,
        'productos': productos,
        'stock_por_producto': stock_por_producto,
        'es_admin': True,
        'today': date.today()
    })


@requiere_login
@solo_admin
def venta_delete(request, pk):
    """Eliminar una venta y restaurar el stock al inventario de la ruta (solo ADMINISTRADOR)"""
    venta = get_object_or_404(Venta, pk=pk)

    if request.method == 'POST':
        venta_id = venta.id
        ruta_id = venta.ruta_id

        with transaction.atomic():
            detalles = DetalleVenta.objects.filter(venta=venta).select_related('producto')

            # 1. Restaurar stock al inventario de la ruta
            if ruta_id:
                for d in detalles:
                    inv_ruta, _ = InventarioRuta.objects.get_or_create(
                        ruta_id=ruta_id,
                        producto=d.producto,
                        defaults={'cantidad': 0}
                    )
                    inv_ruta.cantidad += d.cantidad
                    inv_ruta.save()

            # 2. Eliminar cobros asociados y la venta
            Cobro.objects.filter(venta=venta).delete()
            detalles.delete()
            venta.delete()

        messages.success(request, f'Venta #{venta_id} eliminada correctamente. El stock fue restaurado al inventario de la ruta.')
        return redirect('venta_list')

    return render(request, 'ventas/confirmar_eliminar.html', {'venta': venta})


@requiere_login
def venta_pdf(request, pk):
    """Generar y descargar comprobante PDF de la venta"""
    venta = get_object_or_404(Venta, pk=pk)
    pdf_buffer = generar_pdf_venta(venta)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="venta_{venta.id}.pdf"'
    return response

