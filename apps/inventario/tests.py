from django.test import TestCase
from .models import Producto, InventarioRuta
from apps.rutas.models import Ruta

class InventarioTestCase(TestCase):
    def setUp(self):
        self.ruta = Ruta.objects.create(nombre='Ruta Sur')
        self.producto = Producto.objects.create(
            nombre='Producto A',
            precio_compra=10.00,
            precio_venta=15.00,
            stock_principal=100
        )

    def test_producto_and_inventario_ruta(self):
        self.assertEqual(str(self.producto), 'Producto A')
        inv_ruta = InventarioRuta.objects.create(
            ruta=self.ruta,
            producto=self.producto,
            cantidad=25
        )
        self.assertEqual(inv_ruta.cantidad, 25)
        self.assertEqual(inv_ruta.ruta.nombre, 'Ruta Sur')
