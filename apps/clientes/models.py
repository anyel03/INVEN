from django.db import models

class Cliente(models.Model):
    numero_documento = models.BigIntegerField( primary_key=True)
    
    nombre = models.CharField(max_length=200)
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.TextField(blank=True)
    ruta = models.ForeignKey(
        'rutas.Ruta', 
        on_delete=models.PROTECT, 
        db_column='ruta_id', 
        null=True, 
        blank=True
    )
    
    # Documento de identidad
    tipo_documento = models.CharField(max_length=20, choices=[
        ('CEDULA', 'Cédula'),
        ('RUC', 'RUC'),
        ('PASAPORTE', 'Pasaporte'),
    ], default='CEDULA')
    foto_documento = models.ImageField(
        upload_to='clientes/documentos/', 
        blank=True, 
        null=True
    )
    
    
    class Meta:
        db_table = 'clientes'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.numero_documento})"