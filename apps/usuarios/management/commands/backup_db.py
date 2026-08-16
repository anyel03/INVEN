import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Crea una copia de seguridad timestamped de la base de datos SQLite'

    def handle(self, *args, **options):
        db_path = settings.DATABASES['default']['NAME']
        
        if not os.path.exists(db_path):
            self.stderr.write(self.style.ERROR(f"No se encontró el archivo de base de datos en {db_path}"))
            return

        backups_dir = settings.BASE_DIR / 'backups'
        os.makedirs(backups_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"db_backup_{timestamp}.sqlite3"
        backup_path = backups_dir / backup_filename

        shutil.copy2(db_path, backup_path)
        self.stdout.write(self.style.SUCCESS(f" Respaldo de base de datos creado exitosamente: {backup_path}"))

        # Mantener sólo las últimas 30 copias
        backups = sorted(
            [os.path.join(backups_dir, f) for f in os.listdir(backups_dir) if f.startswith('db_backup_')],
            key=os.path.getmtime
        )

        if len(backups) > 30:
            for old_backup in backups[:-30]:
                os.remove(old_backup)
                self.stdout.write(self.style.WARNING(f" Copia antigua eliminada: {old_backup}"))
