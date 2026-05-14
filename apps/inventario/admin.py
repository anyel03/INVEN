from django.contrib import admin
from .models import Producto, InventarioRuta, TransferenciaInventario, DetalleTransferencia
# Register your models here.
admin.site.register(Producto)
admin.site.register(InventarioRuta)
admin.site.register(TransferenciaInventario)
admin.site.register(DetalleTransferencia)