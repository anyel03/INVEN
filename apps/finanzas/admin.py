from django.contrib import admin
from .models import Ingreso, CajaRuta, DetalleCompra, Compra
# Register your models here.
admin.site.register(Ingreso)
admin.site.register(CajaRuta)
admin.site.register(DetalleCompra)
admin.site.register(Compra)

