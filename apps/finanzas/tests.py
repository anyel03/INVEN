import datetime
from django.test import TestCase
from .models import Compra, DetalleCompra, CajaRuta, Ingreso
from apps.inventario.models import Producto
from apps.rutas.models import Ruta

class FinanzasTestCase(TestCase):
    def setUp(self):
        self.ruta = Ruta.objects.create(nombre='Ruta Finanzas')
        self.producto = Producto.objects.create(
            nombre='Insumo A',
            precio_compra=8.00,
            precio_venta=12.00,
            stock_principal=0
        )

    def test_compra_and_ingreso(self):
        compra = Compra.objects.create(
            proveedor='Proveedor Central',
            total=80.00
        )
        detalle = DetalleCompra.objects.create(
            compra=compra,
            producto=self.producto,
            cantidad=10,
            precio=8.00
        )
        ingreso = Ingreso.objects.create(
            descripcion='Aporte inicial',
            monto=500.00
        )
        caja = CajaRuta.objects.create(
            ruta=self.ruta,
            fecha=datetime.date.today(),
            total_ventas=100.00,
            total_cobros=80.00,
            total_entregado=80.00
        )
        self.assertEqual(str(compra), f"Compra #{compra.id}")
        self.assertEqual(detalle.cantidad, 10)
        self.assertEqual(ingreso.monto, 500.00)
        self.assertEqual(caja.total_entregado, 80.00)
