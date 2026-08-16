from django.test import TestCase, Client
from django.urls import reverse
from .models import Venta, DetalleVenta
from .utils_pdf import generar_pdf_venta
from apps.clientes.models import Cliente
from apps.rutas.models import Ruta
from apps.inventario.models import Producto
from apps.usuarios.models import Rol, Usuario

class VentasTestCase(TestCase):
    def setUp(self):
        self.ruta = Ruta.objects.create(nombre='Ruta Este')
        self.cliente = Cliente.objects.create(
            numero_documento=987654321,
            nombre='Cliente Venta',
            ruta=self.ruta
        )
        self.producto = Producto.objects.create(
            nombre='Producto X',
            precio_compra=5.00,
            precio_venta=10.00,
            stock_principal=50
        )
        self.rol = Rol.objects.create(nombre='EMPLEADO')
        self.usuario = Usuario.objects.create(
            nombre='Vendedor',
            email='vendedor@test.com',
            password='hash',
            rol=self.rol
        )
        self.venta = Venta.objects.create(
            cliente=self.cliente,
            usuario=self.usuario,
            ruta=self.ruta,
            tipo='CREDITO',
            subtotal=100.00,
            descuento=0.00,
            total=100.00,
            saldo=100.00,
            estado='PENDIENTE'
        )
        self.detalle = DetalleVenta.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=10,
            precio=10.00,
            subtotal=100.00
        )

    def test_venta_creation(self):
        self.assertEqual(self.venta.total, 100.00)
        self.assertEqual(self.detalle.subtotal, 100.00)

    def test_generar_pdf_venta(self):
        pdf_buffer = generar_pdf_venta(self.venta)
        self.assertTrue(len(pdf_buffer.getvalue()) > 0)

    def test_venta_pdf_view(self):
        client = Client()
        session = client.session
        session['user_id'] = self.usuario.id
        session['rol_nombre'] = 'EMPLEADO'
        session.save()
        response = client.get(reverse('venta_pdf', kwargs={'pk': self.venta.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
