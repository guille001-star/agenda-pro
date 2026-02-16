import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception("❌ DATABASE_URL no configurada")
    
    # Parsear la URL de PostgreSQL (Railway usa formato postgres://...)
    result = urlparse(database_url)
    username = result.username
    password = result.password
    database = result.path[1:]  # Eliminar la primera barra
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
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Crear tabla de turnos
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
    
    # Crear tabla de horarios
    cur.execute('''
        CREATE TABLE IF NOT EXISTS config_horarios (
            dia_semana INTEGER PRIMARY KEY,
            hora_inicio TIME DEFAULT '09:00:00',
            hora_fin TIME DEFAULT '18:00:00',
            intervalo INTEGER DEFAULT 30,
            activo BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Inicializar días de la semana (Lunes=1, Domingo=7)
    for dia in range(1, 8):
        cur.execute('''
            INSERT INTO config_horarios (dia_semana, hora_inicio, hora_fin, intervalo, activo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (dia_semana) DO NOTHING
        ''', (
            dia,
            '09:00:00' if dia <= 5 else '10:00:00',
            '18:00:00' if dia <= 5 else '14:00:00',
            30,
            True if dia <= 5 else False
        ))
    
    conn.commit()
    cur.close()
    conn.close()