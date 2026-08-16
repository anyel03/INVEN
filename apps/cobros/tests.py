from django.test import TestCase, Client
from django.urls import reverse
from .models import Cobro
from apps.ventas.models import Venta
from apps.ventas.utils_pdf import generar_pdf_cobro
from apps.clientes.models import Cliente
from apps.rutas.models import Ruta
from apps.usuarios.models import Rol, Usuario

class CobrosTestCase(TestCase):
    def setUp(self):
        self.ruta = Ruta.objects.create(nombre='Ruta Oeste')
        self.cliente = Cliente.objects.create(
            numero_documento=1122334455,
            nombre='Cliente Cobro',
            ruta=self.ruta
        )
        self.rol = Rol.objects.create(nombre='EMPLEADO')
        self.usuario = Usuario.objects.create(
            nombre='Cobrador',
            email='cobrador@test.com',
            password='hash',
            rol=self.rol
        )
        self.venta = Venta.objects.create(
            cliente=self.cliente,
            usuario=self.usuario,
            ruta=self.ruta,
            tipo='CREDITO',
            subtotal=50.00,
            total=50.00,
            saldo=50.00,
            estado='PENDIENTE'
        )
        self.cobro = Cobro.objects.create(
            venta=self.venta,
            monto=20.00,
            metodo='EFECTIVO',
            observacion='Abono inicial'
        )

    def test_cobro_creation(self):
        self.assertEqual(self.cobro.monto, 20.00)
        self.assertIn(f"Venta #{self.venta.id}", str(self.cobro))

    def test_generar_pdf_cobro(self):
        pdf_buffer = generar_pdf_cobro(self.cobro)
        self.assertTrue(len(pdf_buffer.getvalue()) > 0)

    def test_cobro_pdf_view(self):
        client = Client()
        session = client.session
        session['user_id'] = self.usuario.id
        session['rol_nombre'] = 'EMPLEADO'
        session.save()
        response = client.get(reverse('cobro_pdf', kwargs={'pk': self.cobro.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
