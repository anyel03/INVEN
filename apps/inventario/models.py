from django.db import models

# Create your models here.
class Producto(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    stock_principal = models.IntegerField(default=0)
    class Meta: db_table = 'productos'
    def __str__(self): return self.nombre

class InventarioRuta(models.Model):
    id = models.AutoField(primary_key=True)
    ruta = models.ForeignKey('rutas.Ruta', on_delete=models.CASCADE, db_column='ruta_id')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, db_column='producto_id')
    cantidad = models.IntegerField()
    class Meta:
        db_table = 'inventario_ruta'
        unique_together = ['ruta', 'producto']

class TransferenciaInventario(models.Model):  
    id = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    ruta = models.ForeignKey('rutas.Ruta', on_delete=models.PROTECT, db_column='ruta_id')
    class Meta: db_table = 'transferenciaInventario'  # ⭐ NUEVO NOMBRE
    def __str__(self): return f"Transferencia #{self.id}"

class DetalleTransferencia(models.Model):
    id = models.AutoField(primary_key=True)
    transferencia = models.ForeignKey(TransferenciaInventario, on_delete=models.CASCADE, db_column='transferencia_id')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='producto_id')
    cantidad = models.IntegerField()
    class Meta: db_table = 'detalle_transferencias'