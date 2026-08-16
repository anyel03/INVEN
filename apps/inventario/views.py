
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator

from .models import Producto, InventarioRuta, TransferenciaInventario, DetalleTransferencia
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


# ==================== PRODUCTOS ====================

@requiere_login
def producto_list(request):
    """Lista de productos"""
    search = request.GET.get('search', '')
    productos = Producto.objects.all().order_by('nombre')
    
    if search:
        productos = productos.filter(nombre__icontains=search)
    
    paginator = Paginator(productos, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'inventario/productos/lista.html', {
        'productos': page_obj,
        'page_obj': page_obj,
        'search': search
    })



@solo_admin
def producto_create(request):
    """Crear producto"""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        precio_compra = request.POST.get('precio_compra', '0')
        precio_venta = request.POST.get('precio_venta', '0')
        stock_principal = request.POST.get('stock_principal', '0')
        
        if not nombre:
            messages.error(request, 'El nombre es requerido')
        elif Producto.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, 'Ya existe un producto con ese nombre')
        else:
            Producto.objects.create(
                nombre=nombre,
                precio_compra=precio_compra,
                precio_venta=precio_venta,
                stock_principal=stock_principal
            )
            messages.success(request, f'Producto "{nombre}" creado correctamente')
            return redirect('producto_list')
    
    return render(request, 'inventario/productos/form.html', {
        'action': 'crear',
        'producto': None
    })


@solo_admin
def producto_edit(request, pk):
    """Editar producto"""
    producto = get_object_or_404(Producto, pk=pk)
    
    if request.method == 'POST':
        producto.nombre = request.POST.get('nombre', '').strip()
        producto.precio_compra = request.POST.get('precio_compra', '0')
        producto.precio_venta = request.POST.get('precio_venta', '0')
        producto.stock_principal = request.POST.get('stock_principal', '0')
        producto.save()
        messages.success(request, 'Producto actualizado correctamente')
        return redirect('producto_list')
    
    return render(request, 'inventario/productos/form.html', {
        'action': 'editar',
        'producto': producto
    })


@solo_admin
def producto_delete(request, pk):
    """Eliminar producto"""
    producto = get_object_or_404(Producto, pk=pk)
    
    if request.method == 'POST':
        producto.delete()
        messages.success(request, 'Producto eliminado correctamente')
        return redirect('producto_list')
    
    return render(request, 'inventario/productos/delete.html', {'producto': producto})


# ==================== INVENTARIO POR RUTA ====================

@requiere_login
def inventario_ruta_list(request):
    """Inventario por rutas"""
    rutas = Ruta.objects.all()
    return render(request, 'inventario/inventario_ruta/lista.html', {'rutas': rutas})


@requiere_login
def inventario_ruta_detalle(request, ruta_id):
    """Detalle de inventario en una ruta"""
    ruta = get_object_or_404(Ruta, pk=ruta_id)
    inventarios = InventarioRuta.objects.filter(ruta=ruta).select_related('producto')
    return render(request, 'inventario/inventario_ruta/detalle.html', {'ruta': ruta, 'inventarios': inventarios})


# ==================== TRANSFERENCIAS ====================

@requiere_login
def transferencia_list(request):
    """Lista de transferencias"""
    transferencias = TransferenciaInventario.objects.all()[:50]
    return render(request, 'inventario/transferencias/lista.html', {'transferencias': transferencias})


@requiere_login
def transferencia_detalle(request, transferencia_id):
    transferencia = get_object_or_404(TransferenciaInventario, pk=transferencia_id)
    detalles = DetalleTransferencia.objects.filter(transferencia=transferencia).select_related('producto')
    return render(request, 'inventario/transferencias/detalle.html', {
        'transferencia': transferencia,
        'detalles': detalles,
    })


@solo_admin
def transferencia_delete(request, transferencia_id):
    transferencia = get_object_or_404(TransferenciaInventario, pk=transferencia_id)

    if request.method == 'POST':
        with transaction.atomic():
            # Revertir stock: devolver a stock_principal y restar de InventarioRuta (ruta destino)
            detalles = list(DetalleTransferencia.objects.filter(transferencia=transferencia).select_related('producto'))
            ruta_id = transferencia.ruta_id

            for d in detalles:
                producto = d.producto
                cantidad = d.cantidad

                # devolver al stock principal
                producto.stock_principal += cantidad
                producto.save()

                # descontar de inventario de la ruta destino
                inv_ruta = InventarioRuta.objects.select_for_update().get(ruta_id=ruta_id, producto=producto)
                inv_ruta.cantidad -= cantidad
                if inv_ruta.cantidad <= 0:
                    inv_ruta.delete()
                else:
                    inv_ruta.save()

            # eliminar la transferencia y sus detalles
            transferencia.delete()

        messages.success(request, f'Transferencia #{transferencia_id} eliminada correctamente')
        return redirect('transferencia_list')

    # Si fuera GET, redirige al detalle (este endpoint solo maneja POST)
    return redirect('transferencia_detalle', transferencia_id=transferencia_id)


@solo_admin
def transferencia_create(request):
    """Crear transferencia"""
    if request.method == 'POST':
        ruta_id = request.POST.get('ruta_id')
        
        if not ruta_id:
            messages.error(request, 'Selecciona una ruta')
            return redirect('transferencia_create')
        
        # Guardar productos
        producto_ids = request.POST.getlist('producto_id[]')
        cantidades = request.POST.getlist('cantidad[]')
        
        if not producto_ids or not cantidades:
            messages.error(request, 'Debes seleccionar al menos un producto para transferir')
            return redirect('transferencia_create')
            
        productos_no_stock = []
        productos_a_transferir = []
        
        for prod_id, cant in zip(producto_ids, cantidades):
            if prod_id and cant and int(cant) > 0:
                try:
                    producto = Producto.objects.get(pk=prod_id)
                    cantidad = int(cant)
                    if producto.stock_principal >= cantidad:
                        productos_a_transferir.append((producto, cantidad))
                    else:
                        productos_no_stock.append(producto.nombre)
                except Producto.DoesNotExist:
                    pass
        
        if productos_no_stock:
            messages.warning(request, f'Stock insuficiente para: {", ".join(productos_no_stock)}')
            
        if not productos_a_transferir:
            messages.error(request, 'No se pudo realizar la transferencia porque ningún producto cuenta con el stock requerido')
            return redirect('transferencia_create')
            
        with transaction.atomic():
            # Crear transferencia
            transferencia = TransferenciaInventario.objects.create(ruta_id=ruta_id)
            
            for producto, cantidad in productos_a_transferir:
                # Descontar del stock principal
                producto.stock_principal -= cantidad
                producto.save()
                
                # Crear detalle
                DetalleTransferencia.objects.create(
                    transferencia=transferencia,
                    producto=producto,
                    cantidad=cantidad
                )
                
                # Agregar a inventario de ruta
                inv_ruta, _ = InventarioRuta.objects.get_or_create(
                    ruta_id=ruta_id,
                    producto=producto,
                    defaults={'cantidad': 0}
                )
                inv_ruta.cantidad += cantidad
                inv_ruta.save()
        
        messages.success(request, 'Transferencia creada correctamente')
        return redirect('transferencia_list')
    
    productos = Producto.objects.filter(stock_principal__gt=0).order_by('nombre')
    rutas = Ruta.objects.all()
    return render(request, 'inventario/transferencias/form.html', {
        'productos': productos,
        'rutas': rutas
    })