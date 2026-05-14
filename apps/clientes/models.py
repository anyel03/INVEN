from django.db import models

# Create your models here.
class Cliente(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.TextField(blank=True)
    ruta = models.ForeignKey('rutas.Ruta', on_delete=models.PROTECT, db_column='ruta_id')
    class Meta: db_table = 'clientes'
    def __str__(self): return self.nombre