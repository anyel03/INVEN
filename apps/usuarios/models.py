from django.db import models

# Create your models here.
class Rol(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    class Meta: db_table = 'roles'
    def __str__(self): return self.nombre

class Usuario(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column='rol_id')
    activo = models.BooleanField(default=True)
    class Meta: db_table = 'usuarios'
    def __str__(self): return self.nombre

class Empleado(models.Model):
    id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, db_column='usuario_id')
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.TextField(blank=True)
    ruta = models.ForeignKey('rutas.Ruta', on_delete=models.SET_NULL, null=True, blank=True, db_column='ruta_id')
    class Meta: db_table = 'empleados'

    