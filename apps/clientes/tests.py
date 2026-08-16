from django.test import TestCase
from .models import Cliente
from apps.rutas.models import Ruta

class ClientesTestCase(TestCase):
    def setUp(self):
        self.ruta = Ruta.objects.create(nombre='Ruta Norte', descripcion='Zona norte')

    def test_cliente_creation(self):
        cliente = Cliente.objects.create(
            numero_documento=123456789,
            nombre='Cliente Prueba',
            telefono='0991234567',
            direccion='Av. Principal 123',
            ruta=self.ruta,
            tipo_documento='CEDULA'
        )
        self.assertEqual(str(cliente), 'Cliente Prueba (123456789)')
        self.assertEqual(cliente.ruta.nombre, 'Ruta Norte')
