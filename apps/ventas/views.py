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
        
        if not producto_ids or all(int(c) == 0 for c in cantidades):
            messages.error(request, 'Agrega al menos un producto')
            return redirect('venta_create')
        
        cliente = Cliente.objects.get(pk=cliente_id)
        ruta_id = cliente.ruta_id if cliente.ruta_id else None
        
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
                    try:
                        inv_ruta = InventarioRuta.objects.get(ruta_id=ruta_id, producto_id=det['producto'].id)
                        inv_ruta.cantidad -= det['cantidad']
                        inv_ruta.save()
                    except:
                        pass
                    
                    det['producto'].stock_principal -= det['cantidad']
                    det['producto'].save()
        
        messages.success(request, f'Venta #{venta.id} creada correctamente')
        return redirect('venta_list')
    
    clientes = Cliente.objects.all().order_by('nombre')
    productos = Producto.objects.filter(stock_principal__gt=0).order_by('nombre')
    rutas = Ruta.objects.all()
    
    return render(request, 'ventas/form.html', {
        'clientes': clientes,
        'productos': productos,
        'rutas': rutas
    })


@requiere_login
def venta_detalle(request, pk):
    """Detalle de una venta"""
    venta = get_object_or_404(Venta, pk=pk)
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('producto')
    return render(request, 'ventas/detalle.html', {'venta': venta, 'detalles': detalles})