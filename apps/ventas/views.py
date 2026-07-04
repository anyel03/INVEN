# apps/ventas/views.py - CORREGIDO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from decimal import Decimal

from .models import Venta, DetalleVenta
from apps.clientes.models import Cliente
from apps.inventario.models import Producto, InventarioRuta
from apps.rutas.models import Ruta


# ==================== HELPERS ====================

def requiere_login(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== VENTAS ====================

@requiere_login
def venta_list(request):
    """Lista de ventas"""
    search = request.GET.get('search', '')
    estado = request.GET.get('estado', '')
    tipo = request.GET.get('tipo', '')
    
    ventas = Venta.objects.select_related('cliente', 'usuario').order_by('-created_at')
    
    if search:
        ventas = ventas.filter(
            Q(cliente__nombre__icontains=search) |
            Q(id__icontains=search)
        )
    if estado:
        ventas = ventas.filter(estado=estado)
    if tipo:
        ventas = ventas.filter(tipo=tipo)
    
    return render(request, 'ventas/lista.html', {
        'ventas': ventas,
        'search': search
    })


@requiere_login
def venta_create(request):
    """Crear nueva venta"""

    def _get_ruta_id_para_usuario():
        # ADMIN: usar ruta seleccionada desde el formulario
        if request.session.get('rol_nombre') == 'ADMIN':
            return request.POST.get('ruta_id') or None

        # NO ADMIN: SIEMPRE usar la ruta del empleado
        from apps.usuarios.models import Empleado
        empleado = Empleado.objects.filter(usuario_id=request.session['user_id']).select_related('ruta').first()
        ruta_id_local = getattr(empleado, 'ruta_id', None) if empleado else None
        if not ruta_id_local:
            messages.error(request, 'Tu empleado no tiene una ruta asignada')
            return None
        return ruta_id_local


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

        if not producto_ids:
            messages.error(request, 'Agrega al menos un producto')
            return redirect('venta_create')

        pares_validos = []
        for i, prod_id in enumerate(producto_ids):
            try:
                cant = cantidades[i]
            except IndexError:
                cant = '0'

            if not prod_id:
                continue

            try:
                cant_int = int(cant)
            except (TypeError, ValueError):
                cant_int = 0

            if cant_int > 0:
                pares_validos.append((prod_id, cant_int))

        if not pares_validos:
            messages.error(request, 'Agrega al menos un producto')
            return redirect('venta_create')

        ruta_id = _get_ruta_id_para_usuario()
        if request.session.get('rol_nombre') != 'ADMIN' and ruta_id is None:
            return redirect('venta_create')


        total = Decimal('0')
        detalles = []

        for prod_id, cantidad in pares_validos:
            producto = Producto.objects.get(pk=prod_id)

            if ruta_id:
                inv_ruta = InventarioRuta.objects.filter(ruta_id=ruta_id, producto_id=prod_id).first()
                stock = inv_ruta.cantidad if inv_ruta else 0
            else:
                stock = 0

            if cantidad > stock:
                messages.error(request, f'Stock insuficiente para {producto.nombre}. Stock: {stock}')
                return redirect('venta_create')

            subtotal = producto.precio_venta * cantidad
            total += subtotal

            detalles.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio': producto.precio_venta,
                'subtotal': subtotal
            })

        if not detalles:
            messages.error(request, 'No hay productos con stock disponible')
            return redirect('venta_create')

        total -= descuento

        with transaction.atomic():
            venta = Venta.objects.create(
                cliente_id=cliente_id,
                usuario_id=request.session['user_id'],
                ruta_id=ruta_id,
                tipo=tipo,
                subtotal=total + descuento,
                descuento=descuento,
                total=total,
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

                if ruta_id:
                    inv_ruta = InventarioRuta.objects.select_for_update().get(ruta_id=ruta_id, producto_id=det['producto'].id)
                    inv_ruta.cantidad -= det['cantidad']
                    if inv_ruta.cantidad <= 0:
                        inv_ruta.delete()
                    else:
                        inv_ruta.save()

        messages.success(request, f'Venta #{venta.id} creada correctamente')
        return redirect('venta_list')

    clientes = Cliente.objects.all().order_by('nombre')

    if request.session.get('rol_nombre') == 'ADMIN':
        productos = Producto.objects.filter(stock_principal__gt=0).order_by('nombre')
    else:

        try:

            from apps.usuarios.models import Empleado
            empleado = Empleado.objects.get(usuario_id=request.session['user_id'])
            ruta_emp = getattr(empleado, 'ruta_id', None)
        except:
            ruta_emp = None

        if ruta_emp:
            productos = (
                Producto.objects.filter(
                    inventarioruta__ruta_id=ruta_emp,
                    inventarioruta__cantidad__gt=0,
                )
                .distinct()
                .order_by('nombre')
            )
        else:
            productos = Producto.objects.filter(stock_principal__gt=0).order_by('nombre')

    rutas = Ruta.objects.all()

    es_admin = request.session.get('rol_nombre') == 'ADMIN'

    stock_por_producto = {}

    if not es_admin:

        try:
            from apps.usuarios.models import Empleado
            empleado = Empleado.objects.get(usuario_id=request.session['user_id'])
            ruta_emp_id = getattr(empleado, 'ruta_id', None)
        except:
            ruta_emp_id = None

        if ruta_emp_id:
            qs = InventarioRuta.objects.filter(ruta_id=ruta_emp_id).values_list('producto_id', 'cantidad')
            stock_por_producto = {pid: cant for (pid, cant) in qs}

    return render(request, 'ventas/form.html', {
        'clientes': clientes,
        'productos': productos,
        'rutas': rutas,
        'es_admin': es_admin,
        'stock_por_producto': stock_por_producto,
    })



@requiere_login
def venta_create_con_cliente(request):
    """Nueva venta permitiendo crear cliente en la misma vista"""
    if request.method == 'POST':
        form_type = request.POST.get('form_type')


        # ================= CREAR CLIENTE =================
        if form_type == 'cliente':
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

                if request.FILES.get('foto_documento'):
                    cliente.foto_documento = request.FILES['foto_documento']
                    cliente.save()

                messages.success(request, f'Cliente "{nombre}" creado correctamente')

            # Renderizar nuevamente la página manteniendo listas
            clientes = Cliente.objects.all().order_by('nombre')
            productos = Producto.objects.filter(stock_principal__gt=0).order_by('nombre')
            rutas = Ruta.objects.all()

            # Dict de stock por producto para mostrar en el template.
            stock_por_producto = {}
            try:
                from apps.usuarios.models import Empleado
                empleado = Empleado.objects.get(usuario_id=request.session['user_id'])
                ruta_emp_id = getattr(empleado, 'ruta_id', None)
            except:
                ruta_emp_id = None

            if ruta_emp_id:
                qs = InventarioRuta.objects.filter(ruta_id=ruta_emp_id).values_list('producto_id', 'cantidad')
                stock_por_producto = {pid: cant for (pid, cant) in qs}

            return render(request, 'ventas/form_cliente_venta.html', {
                'clientes': clientes,
                'productos': productos,
                'rutas': rutas,
                'stock_por_producto': stock_por_producto,
            })

        # ================= CREAR VENTA (igual lógica) =================

        tipo = request.POST.get('tipo', 'CONTADO')
        descuento = Decimal(request.POST.get('descuento', '0') or '0')
        observaciones = request.POST.get('observaciones', '').strip()

        producto_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')

        if not cliente_id:
            messages.error(request, 'Selecciona un cliente')
            return redirect('venta_create_con_cliente')

        if not producto_ids or all(int(c) == 0 for c in cantidades):
            messages.error(request, 'Agrega al menos un producto')
            return redirect('venta_create_con_cliente')

        # Para NO ADMIN SIEMPRE usar la ruta del empleado
        if request.session.get('rol_nombre') == 'ADMIN':
            ruta_id = request.POST.get('ruta_id') or None
        else:
            from apps.usuarios.models import Empleado
            empleado = Empleado.objects.filter(usuario_id=request.session['user_id']).select_related('ruta').first()
            ruta_id = getattr(empleado, 'ruta_id', None) if empleado else None
            if not ruta_id:
                messages.error(request, 'Tu empleado no tiene una ruta asignada')
                return redirect('venta_create_con_cliente')


        total = Decimal('0')
        detalles = []

        for prod_id, cant in zip(producto_ids, cantidades):
            if prod_id and cant and int(cant) > 0:
                producto = Producto.objects.get(pk=prod_id)
                cantidad = int(cant)

                if ruta_id:
                    try:
                        inv_ruta = InventarioRuta.objects.get(ruta_id=ruta_id, producto_id=prod_id)
                        stock = inv_ruta.cantidad
                    except:
                        stock = 0
                else:
                    stock = 0

                if cantidad > stock:
                    messages.error(request, f'Stock insuficiente para {producto.nombre}. Stock: {stock}')
                    return redirect('venta_create_con_cliente')

                subtotal = producto.precio_venta * cantidad
                total += subtotal

                detalles.append({
                    'producto': producto,
                    'cantidad': cantidad,
                    'precio': producto.precio_venta,
                    'subtotal': subtotal
                })

        if not detalles:
            messages.error(request, 'No hay productos con stock disponible')
            return redirect('venta_create_con_cliente')

        total -= descuento

        with transaction.atomic():
            venta = Venta.objects.create(
                cliente_id=cliente_id,
                usuario_id=request.session['user_id'],
                ruta_id=ruta_id,
                tipo=tipo,
                subtotal=total + descuento,
                descuento=descuento,
                total=total,
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

                if ruta_id:
                    try:
                        inv_ruta = InventarioRuta.objects.get(ruta_id=ruta_id, producto_id=det['producto'].id)
                        inv_ruta.cantidad -= det['cantidad']
                        inv_ruta.save()
                    except:
                        pass

        messages.success(request, f'Venta #{venta.id} creada correctamente')
        return redirect('venta_list')

    # Dict de stock por producto para mostrar en el template.

    stock_por_producto = {}

    # Si es ADMIN, el stock del template debe respetar la ruta seleccionada.
    # Para que sea dinámico en UI, el stock se recarga al cambiar la ruta (GET con querystring).
    if request.session.get('rol_nombre') == 'ADMIN':
        ruta_admin_id = request.POST.get('ruta_id') or request.GET.get('ruta_id') or None
        if ruta_admin_id:
            qs = InventarioRuta.objects.filter(ruta_id=ruta_admin_id).values_list('producto_id', 'cantidad')
            stock_por_producto = {pid: cant for (pid, cant) in qs}

    else:
        try:
            from apps.usuarios.models import Empleado
            empleado = Empleado.objects.get(usuario_id=request.session['user_id'])
            ruta_emp_id = getattr(empleado, 'ruta_id', None)
        except:
            ruta_emp_id = None

        if ruta_emp_id:
            qs = InventarioRuta.objects.filter(ruta_id=ruta_emp_id).values_list('producto_id', 'cantidad')
            stock_por_producto = {pid: cant for (pid, cant) in qs}


    return render(request, 'ventas/form_cliente_venta.html', {
        'clientes': clientes,
        'productos': productos,
        'rutas': rutas,
        'es_admin': request.session.get('rol_nombre') == 'ADMIN',
        'stock_por_producto': stock_por_producto,
    })



@requiere_login
def venta_detalle(request, pk):
    """Detalle de una venta"""
    venta = get_object_or_404(Venta, pk=pk)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('producto')
    return render(request, 'ventas/detalle.html', {'venta': venta, 'detalles': detalles})


@requiere_login
def ajax_stock_por_ruta(request):
    """Devuelve stock por producto para una ruta dada (solo ADMIN)."""
    if request.session.get('rol_nombre') != 'ADMIN':
        return redirect('venta_create')

    ruta_id = request.GET.get('ruta_id') or request.POST.get('ruta_id')
    try:
        ruta_id_int = int(ruta_id) if ruta_id not in (None, '', 'null') else None
    except (TypeError, ValueError):
        ruta_id_int = None

    if not ruta_id_int:
        return render(request, 'ventas/form.html')

    qs = InventarioRuta.objects.filter(ruta_id=ruta_id_int).values_list('producto_id', 'cantidad')
    stock_por_producto = {pid: cant for (pid, cant) in qs}

    # Respuesta JSON simple.
    from django.http import JsonResponse
    return JsonResponse({'stocks': stock_por_producto})

