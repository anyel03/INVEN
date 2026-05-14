from django.db import models

# Create your models here.
class Venta(models.Model):
    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, db_column='cliente_id')
    empleado = models.ForeignKey('usuarios.Empleado', on_delete=models.PROTECT, db_column='empleado_id')
    ruta = models.ForeignKey('rutas.Ruta', on_delete=models.PROTECT, db_column='ruta_id')
    fecha = models.DateTimeField(auto_now_add=True)
    tipo_pago = models.CharField(max_length=10, db_column='tipo_pago')
    total = models.DecimalField(max_digits=12, decimal_places=2)
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fecha_limite = models.DateField(null=True, blank=True, db_column='fecha_limite')
    class Meta: db_table = 'ventas'
    def __str__(self): return f"Venta #{self.id}"

class DetalleVenta(models.Model):
    id = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, db_column='venta_id')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT, db_column='producto_id')
    cantidad = models.IntegerField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    class Meta: db_table = 'detalle_ventas'