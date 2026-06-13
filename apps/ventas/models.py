# apps/ventas/models.py
from django.db import models

class Venta(models.Model):
    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, db_column='cliente_id')
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT, db_column='usuario_id')
    ruta = models.ForeignKey('rutas.Ruta', on_delete=models.PROTECT, db_column='ruta_id', null=True)
    
    tipo = models.CharField(max_length=10, choices=[
        ('CONTADO', 'Contado'),
        ('CREDITO', 'Crédito'),
    ], default='CONTADO')
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    estado = models.CharField(max_length=15, choices=[
        ('PENDIENTE', 'Pendiente'),
        ('PAGADA', 'Pagada'),
        ('CANCELADA', 'Cancelada'),
    ], default='PENDIENTE')
    
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ventas'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Venta #{self.id} - {self.cliente.nombre}"


class DetalleVenta(models.Model):
    id = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, db_column='venta_id')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT, db_column='producto_id')
    cantidad = models.IntegerField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'detalle_ventas'
    
    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"
