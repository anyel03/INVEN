from django.db import models

# Create your models here.
class Cobro(models.Model):
    id = models.AutoField(primary_key=True)
    venta = models.ForeignKey('ventas.Venta', on_delete=models.CASCADE, db_column='venta_id')
    fecha = models.DateTimeField(auto_now_add=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    class Meta: db_table = 'cobros'
    def __str__(self): return f"Cobro #{self.id}"