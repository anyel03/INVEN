from django.test import TestCase
from .models import Ruta

class RutasTestCase(TestCase):
    def test_ruta_creation(self):
        ruta = Ruta.objects.create(nombre='Ruta Central', descripcion='Zona comercial centro')
        self.assertEqual(str(ruta), 'Ruta Central')
        self.assertEqual(Ruta.objects.count(), 1)
