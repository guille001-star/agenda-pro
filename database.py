import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

def get_db_connection():
    """
    Establece conexión con PostgreSQL usando DATABASE_URL de Railway.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception("❌ DATABASE_URL no configurada. Asegúrate de tener PostgreSQL conectado en Railway.")
    
    # Parsear la URL de conexión (ej: postgres://user:pass@host:port/dbname)
    result = urlparse(database_url)
    username = result.username
    password = result.password
    database = result.path[1:]  # Elimina la barra inicial del path
    hostname = result.hostname
    port = result.port or 5432

    conn = psycopg2.connect(
        host=hostname,
        database=database,
        user=username,
        password=password,
        port=port,
        cursor_factory=RealDictCursor
    )
    return conn

def init_db():
    """
    Crea las tablas si no existen e inicializa los horarios por defecto.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Tabla de turnos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS turnos (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL,
            telefono TEXT,
            fecha DATE NOT NULL,
            hora TIME NOT NULL,
            motivo TEXT,
            estado TEXT DEFAULT 'pendiente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de configuración de horarios
    cur.execute('''
        CREATE TABLE IF NOT EXISTS config_horarios (
            dia_semana INTEGER PRIMARY KEY,
            hora_inicio TIME DEFAULT '09:00:00',
            hora_fin TIME DEFAULT '18:00:00',
            intervalo INTEGER DEFAULT 30,
            activo BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Inicializar horarios por día (Lunes=1, Domingo=7)
    for dia in range(1, 8):
        hora_inicio = '09:00:00' if dia <= 5 else '10:00:00'
        hora_fin = '18:00:00' if dia <= 5 else '14:00:00'
        activo = True if dia <= 5 else False
        
        cur.execute('''
            INSERT INTO config_horarios (dia_semana, hora_inicio, hora_fin, intervalo, activo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (dia_semana) DO NOTHING
        ''', (dia, hora_inicio, hora_fin, 30, activo))
    
    conn.commit()
    cur.close()
    conn.close()