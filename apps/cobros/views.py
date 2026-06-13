# apps/cobros/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db import models
from decimal import Decimal

from .models import Cobro
from apps.ventas.models import Venta


# ==================== HELPERS ====================

def requiere_login(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


# ==================== COBROS ====================

@requiere_login
def cobro_list(request):
    """Lista de cobros"""
    search = request.GET.get('search', '')
    
    cobros = Cobro.objects.select_related('venta__cliente').order_by('-created_at')
    
    if search:
        cobros = cobros.filter(
            venta__cliente__nombre__icontains=search
        )
    
    total_cobrado = sum(c.monto for c in cobros)
    
    return render(request, 'cobros/lista.html', {
        'cobros': cobros,
        'total_cobrado': total_cobrado,
        'search': search
    })


@requiere_login
def cobro_create(request):
    """Registrar nuevo cobro"""
    if request.method == 'POST':
        venta_id = request.POST.get('venta_id')
        monto = Decimal(request.POST.get('monto', '0'))
        metodo = request.POST.get('metodo', 'EFECTIVO')
        observacion = request.POST.get('observacion', '').strip()
        
        if not venta_id:
            messages.error(request, 'Selecciona una venta')
            return redirect('cobro_create')
        
        if monto <= 0:
            messages.error(request, 'El monto debe ser mayor a 0')
            return redirect('cobro_create')
        
        venta = Venta.objects.get(pk=venta_id)
        
        # Calcular lo que falta por pagar
        total_venta = venta.total
        cobros_anteriores = Cobro.objects.filter(venta=venta).aggregate(total=models.Sum('monto'))['total'] or Decimal('0')
        pendiente = total_venta - cobros_anteriores
        
        if monto > pendiente:
            messages.error(request, f'El monto excede lo pendiente (${pendiente})')
            return redirect('cobro_create')
        
        with transaction.atomic():
            # Crear cobro
            Cobro.objects.create(
                venta_id=venta_id,
                monto=monto,
                metodo=metodo,
                observacion=observacion
            )
            
            # Verificar si se pagó completo
            nuevo_cobrado = cobros_anteriores + monto
            if nuevo_cobrado >= total_venta:
                venta.estado = 'PAGADA'
                venta.save()
        
        messages.success(request, 'Cobro registrado correctamente')
        return redirect('cobro_list')
    
    # Ventas pendientes de crédito
    ventas_pendientes = Venta.objects.filter(
        tipo='CREDITO',
        estado='PENDIENTE'
    ).select_related('cliente')
    
    # Calcular pendientes
    ventas_con_saldo = []
    for v in ventas_pendientes:
        total_cobrado = Cobro.objects.filter(venta=v).aggregate(t=models.Sum('monto'))['t'] or Decimal('0')
        pendiente = v.total - total_cobrado
        if pendiente > 0:
            ventas_con_saldo.append({
                'venta': v,
                'pendiente': pendiente
            })
    
    return render(request, 'cobros/form.html', {
        'ventas': ventas_con_saldo
    })