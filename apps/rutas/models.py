from django.db import models

# Create your models here.
class Ruta(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    class Meta: db_table = 'rutas'
    def __str__(self): return self.nombre

