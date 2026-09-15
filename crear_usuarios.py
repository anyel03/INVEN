import hashlib
import os
import psycopg2

def encrypt(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'sistemainven_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding('UTF8')
    cursor = conn.cursor()

    # 1. Crear roles
    cursor.execute("""
        INSERT INTO roles (nombre) 
        VALUES ('ADMIN'), ('EMPLEADO') 
        ON CONFLICT (nombre) DO NOTHING;
    """)

    # 2. Obtener IDs
    cursor.execute("SELECT id FROM roles WHERE nombre = 'ADMIN';")
    admin_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM roles WHERE nombre = 'EMPLEADO';")
    emp_id = cursor.fetchone()[0]

    # 3. Insertar Usuario ADMIN
    cursor.execute("""
        INSERT INTO usuarios (nombre, email, password, rol_id, activo) 
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING;
    """, ('Administrador', 'admin@empresa.com', encrypt('admin123'), admin_id, True))

    # 4. Insertar Usuario EMPLEADO
    cursor.execute("""
        INSERT INTO usuarios (nombre, email, password, rol_id, activo) 
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING;
    """, ('Juan Perez', 'juan@empresa.com', encrypt('empleado123'), emp_id, True))

    conn.commit()
    cursor.close()
    conn.close()

    print("Proceso finalizado correctamente!")

except Exception as e:
    # Evita el fallo de decodificación al imprimir el error en la terminal
    error_msg = str(e).encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
    if not error_msg.strip():
        error_msg = repr(e)
    print("Error detectado:", error_msg)