import hashlib
from django.test import TestCase, Client
from django.urls import reverse
from .models import Rol, Usuario, Empleado
from apps.rutas.models import Ruta

class UsuariosModelsTestCase(TestCase):
    def setUp(self):
        self.rol_admin = Rol.objects.create(nombre='ADMIN')
        self.rol_emp = Rol.objects.create(nombre='EMPLEADO')
        self.password_hash = hashlib.sha256('secret123'.encode()).hexdigest()
        
        self.usuario = Usuario.objects.create(
            nombre='Admin Test',
            email='admin@test.com',
            password=self.password_hash,
            rol=self.rol_admin,
            activo=True
        )

    def test_usuario_creation(self):
        self.assertEqual(str(self.usuario), 'Admin Test')
        self.assertTrue(self.usuario.activo)
        self.assertEqual(self.usuario.rol.nombre, 'ADMIN')

    def test_login_flow(self):
        client = Client()
        response = client.post(reverse('login'), {
            'email': 'admin@test.com',
            'password': 'secret123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session.get('user_id'), self.usuario.id)
