# crear_usuarios.py
import sqlite3
import hashlib
import os

def encrypt(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# Nombre de tu archivo de base de datos
db_name = 'db.sqlite3'

if not os.path.exists(db_name):
    print(f" No existe {db_name}. Primero corre: python manage.py migrate")
else:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # Crear rol ADMIN
    try:
        cursor.execute("INSERT INTO roles (nombre) VALUES ('ADMIN')")
        print(" Rol ADMIN creado")
    except:
        pass
    
    # Crear rol EMPLEADO
    try:
        cursor.execute("INSERT INTO roles (nombre) VALUES ('EMPLEADO')")
        print(" Rol EMPLEADO creado")  
    except:
        pass
    
    # Obtener IDs de roles
    cursor.execute("SELECT id FROM roles WHERE nombre='ADMIN'")
    admin_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM roles WHERE nombre='EMPLEADO'")
    emp_id = cursor.fetchone()[0]
    
    # Crear ADMIN
    try:
        cursor.execute("""
            INSERT INTO usuarios (nombre, email, password, rol_id, activo) 
            VALUES (?, ?, ?, ?, ?)
        """, ('Administrador', 'admin@empresa.com', encrypt('admin123'), admin_id, 1))
        print(" ADMIN: admin@empresa.com / admin123")
    except:
        print(" Admin ya existe")
    
    # Crear EMPLEADO
    try:
        cursor.execute("""
            INSERT INTO usuarios (nombre, email, password, rol_id, activo) 
            VALUES (?, ?, ?, ?, ?)
        """, ('Juan Pérez', 'juan@empresa.com', encrypt('empleado123'), emp_id, 1))
        print(" EMPLEADO: juan@empresa.com / empleado123")
    except:
        print(" Empleado ya existe")
    
    conn.commit()
    conn.close()
    
    print("\n Usuarios creados correctamente!")