from django.contrib import admin

from .models import Rol, Usuario, Empleado

admin.site.register(Rol)
admin.site.register(Usuario)
admin.site.register(Empleado)

