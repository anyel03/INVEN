# apps/finanzas/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum
from decimal import Decimal

from apps.ventas.models import Venta, DetalleVenta
from apps.cobros.models import Cobro
from apps.inventario.models import Producto


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
    except:
        return Decimal('0')


# ==================== DASHBOARD ====================

@requiere_login
@solo_admin
def dashboard(request):
    """Dashboard financiero"""
    
    # Ventas
    try:
        result = Venta.objects.aggregate(t=Sum('total'))
        ventas_total = get_decimal(result.get('t'))
    except:
        ventas_total = Decimal('0')
    
    try:
        result = Venta.objects.filter(tipo='CONTADO').aggregate(t=Sum('total'))
        ventas_contado = get_decimal(result.get('t'))
    except:
        ventas_contado = Decimal('0')
    
    try:
        result = Venta.objects.filter(tipo='CREDITO').aggregate(t=Sum('total'))
        ventas_credito = get_decimal(result.get('t'))
    except:
        ventas_credito = Decimal('0')
    
    # Cobros
    try:
        result = Cobro.objects.aggregate(t=Sum('monto'))
        cobros_total = get_decimal(result.get('t'))
    except:
        cobros_total = Decimal('0')
    
    try:
        result = Venta.objects.filter(estado='PENDIENTE').aggregate(t=Sum('total'))
        ventas_pendientes = get_decimal(result.get('t'))
    except:
        ventas_pendientes = Decimal('0')
    
    # Métodos de cobro
    for metodo, var in [('EFECTIVO', 'cobros_efectivo'), ('TRANSFERENCIA', 'cobros_transferencia'), ('YAPE', 'cobros_yape'), ('PLIN', 'cobros_plin')]:
        try:
            result = Cobro.objects.filter(metodo=metodo).aggregate(t=Sum('monto'))
            exec(f"{var} = get_decimal(result.get('t'))")
        except:
            exec(f"{var} = Decimal('0')")
    
    cobros_efectivo = Decimal('0')
    cobros_transferencia = Decimal('0')
    cobros_yape = Decimal('0')
    cobros_plin = Decimal('0')
    
    try:
        cobros_efectivo = get_decimal(Cobro.objects.filter(metodo='EFECTIVO').aggregate(t=Sum('monto')).get('t'))
    except: pass
    
    try:
        cobros_transferencia = get_decimal(Cobro.objects.filter(metodo='TRANSFERENCIA').aggregate(t=Sum('monto')).get('t'))
    except: pass
    
    
    # Compras, Ingresos, CajaRutas - contry-except para manejar tabla inexistente
    try:
        from .models import Compra
        compras_total = get_decimal(Compra.objects.aggregate(t=Sum('total')).get('t'))
    except:
        compras_total = Decimal('0')
    
    try:
        from .models import Ingreso
        ingresos_extra = get_decimal(Ingreso.objects.aggregate(t=Sum('monto')).get('t'))
    except:
        ingresos_extra = Decimal('0')
    
    try:
        from .models import CajaRuta
        caja_rutas = CajaRuta.objects.all().select_related('ruta')
    except:
        caja_rutas = []
    
    try:
        from .models import CajaRuta
        total_caja_rutas = sum(get_decimal(c.total_ventas) for c in caja_rutas)
    except:
        total_caja_rutas = Decimal('0')
    
    # Ganancias
    try:
        detalles = DetalleVenta.objects.all()
        ingresos = sum(get_decimal(d.subtotal) for d in detalles)
        costos = sum(get_decimal(d.producto.precio_compra) * d.cantidad for d in detalles)
        ganancias = ingresos - costos
    except:
        ingresos = Decimal('0')
        costos = Decimal('0')
        ganancias = Decimal('0')
    
    # Productos
    try:
        productos_total = Producto.objects.count()
    except:
        productos_total = 0
    
    try:
        productos_sin_stock = Producto.objects.filter(stock_principal=0).count()
    except:
        productos_sin_stock = 0
    
    try:
        productos_bajo_stock = Producto.objects.filter(stock_principal__gt=0, stock_principal__lt=5).count()
    except:
        productos_bajo_stock = 0
    
    # Liquidez
    liquidez = cobros_total + ingresos_extra - compras_total
    
    context = {
        'ventas_total': ventas_total,
        'ventas_contado': ventas_contado,
        'ventas_credito': ventas_credito,
        'cobros_total': cobros_total,
        'ventas_pendientes': ventas_pendientes,
        'cobros_efectivo': cobros_efectivo,
        'cobros_transferencia': cobros_transferencia,
        'cobros_yape': cobros_yape,
        'cobros_plin': cobros_plin,
        'compras_total': compras_total,
        'ingresos_extra': ingresos_extra,
        'caja_rutas': caja_rutas,
        'total_caja_rutas': total_caja_rutas,
        'ingresos': ingresos,
        'costos': costos,
        'ganancias': ganancias,
        'productos_total': productos_total,
        'productos_sin_stock': productos_sin_stock,
        'productos_bajo_stock': productos_bajo_stock,
        'liquidez': liquidez,
    }
    
    return render(request, 'finanzas/dashboard.html', context)


# ==================== REPORTE VENTAS ====================

@requiere_login
@solo_admin
def reporte_ventas(request):
    """Reporte detallado de ventas"""
    ventas = []
    
    try:
        ventas = Venta.objects.select_related('cliente').order_by('-created_at')[:100]
        
        for v in ventas:
            try:
                result = Cobro.objects.filter(venta=v).aggregate(t=Sum('monto'))
                v.cobrado = get_decimal(result.get('t'))
            except:
                v.cobrado = Decimal('0')
    except:
        pass
    
    return render(request, 'finanzas/reporte_ventas.html', {'ventas': ventas})


# ==================== COMPRAS ====================

@requiere_login
@solo_admin
def compra_list(request):
    """Lista de compras"""
    compras = []
    
    try:
        from .models import Compra
        compras = Compra.objects.all()[:50]
    except:
        pass
    
    return render(request, 'finanzas/compras/lista.html', {'compras': compras})


@requiere_login
@solo_admin
def compra_create(request):
    """Crear compra"""
    try:
        from .models import Compra, DetalleCompra
    except ImportError:
        messages.error(request, 'Error: tabla de compras no configurada')
        return redirect('finanzas_dashboard')
    
    if request.method == 'POST':
        proveedor = request.POST.get('proveedor', '').strip()
        
        if not proveedor:
            messages.error(request, 'El proveedor es requerido')
        else:
            compra = Compra.objects.create(proveedor=proveedor, total=0)
            
            producto_ids = request.POST.getlist('producto_id[]')
            cantidades = request.POST.getlist('cantidad[]')
            precios = request.POST.getlist('precio[]')
            
            total = Decimal('0')
            for p_id, cant, prec in zip(producto_ids, cantidades, precios):
                if p_id and cant and prec:
                    try:
                        producto = Producto.objects.get(pk=p_id)
                        cantidad = int(cant)
                        precio = Decimal(prec)
                        
                        DetalleCompra.objects.create(
                            compra=compra,
                            producto=producto,
                            cantidad=cantidad,
                            precio=precio
                        )
                        
                        producto.stock_principal += cantidad
                        producto.save()
                        
                        total += precio * cantidad
                    except:
                        pass
            
            compra.total = total
            compra.save()
            
            messages.success(request, f'Compra #{compra.id} creada correctamente')
            return redirect('compra_list')
    
    try:
        productos = Producto.objects.all().order_by('nombre')
    except:
        productos = []
    
    return render(request, 'finanzas/compras/form.html', {'productos': productos})


# ==================== INGRESOS ====================

@requiere_login
@solo_admin
def ingreso_list(request):
    """Lista de ingresos"""
    ingresos = []
    
    try:
        from .models import Ingreso
        ingresos = Ingreso.objects.all()[:50]
    except:
        pass
    
    return render(request, 'finanzas/ingresos/lista.html', {'ingresos': ingresos})


@requiere_login
@solo_admin
def ingreso_create(request):
    """Crear ingreso"""
    try:
        from .models import Ingreso
    except ImportError:
        messages.error(request, 'Error: tabla de ingresos no configurada')
        return redirect('finanzas_dashboard')
    
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion', '').strip()
        monto = get_decimal(request.POST.get('monto', '0'))
        
        if not descripcion or monto <= 0:
            messages.error(request, 'Descripción y monto son requeridos')
        else:
            Ingreso.objects.create(descripcion=descripcion, monto=monto)
            messages.success(request, 'Ingreso registrado correctamente')
            return redirect('ingreso_list')
    
    return render(request, 'finanzas/ingresos/form.html')


# ==================== CAJA RUTAS ====================

@requiere_login
@solo_admin
def caja_ruta_list(request):
    """Lista de caja por rutas"""
    cajas = []
    
    try:
        from .models import CajaRuta
        cajas = CajaRuta.objects.all().select_related('ruta')
    except:
        pass
    
    return render(request, 'finanzas/caja_ruta/lista.html', {'cajas': cajas})