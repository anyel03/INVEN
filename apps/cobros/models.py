from django.db import models

# Create your models here.
class Cobro(models.Model):
    id = models.AutoField(primary_key=True)
    venta = models.ForeignKey('ventas.Venta', on_delete=models.CASCADE, db_column='venta_id')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=[
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('YAPE', 'Yape'),
        ('PLIN', 'Plin'),
    ], default='EFECTIVO')
    observacion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cobros'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Cobro #{self.id} - Venta #{self.venta_id}"