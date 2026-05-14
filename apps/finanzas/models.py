from django.db import models

# Create your models here.
class Compra(models.Model):
    id = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    proveedor = models.CharField(max_length=200)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    class Meta: db_table = 'compras'
    def __str__(self): return f"Compra #{self.id}"

class DetalleCompra(models.Model):
    id = models.AutoField(primary_key=True)
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, db_column='compra_id')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT, db_column='producto_id')
    cantidad = models.IntegerField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    class Meta: db_table = 'detalle_compras'

class CajaRuta(models.Model):
    id = models.AutoField(primary_key=True)
    ruta = models.ForeignKey('rutas.Ruta', on_delete=models.PROTECT, db_column='ruta_id')
    fecha = models.DateField()
    total_ventas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cobros = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_entregado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    class Meta:
        db_table = 'caja_ruta'
        unique_together = ['ruta', 'fecha']

class Ingreso(models.Model):
    id = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    descripcion = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    class Meta: db_table = 'ingresos'