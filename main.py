import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import database

# === CONFIGURACIÓN ===
app = FastAPI(title="AgendaPro")
templates = Jinja2Templates(directory="templates")

# Inicializar base de datos al iniciar
database.init_db()

# === MODELOS ===
class TurnoCreate(BaseModel):
    nombre: str
    email: str
    telefono: Optional[str] = None
    fecha: str  # formato YYYY-MM-DD
    hora: str   # formato HH:MM
    motivo: Optional[str] = None

# === RUTAS PÚBLICAS ===
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/horarios/{fecha}")
async def get_horarios_disponibles(fecha: str):
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d')
        dia_semana = fecha_obj.weekday() + 1  # Lunes = 1
        
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT * FROM config_horarios WHERE dia_semana = %s', (dia_semana,))
        config = cur.fetchone()
        
        if not config or not config['activo']:
            cur.close()
            conn.close()
            return {"horarios": []}
        
        # Obtener horarios ocupados
        cur.execute('SELECT hora FROM turnos WHERE fecha = %s AND estado != %s', (fecha, 'cancelado'))
        ocupados = {row['hora'].strftime('%H:%M') for row in cur.fetchall()}
        
        # Generar horarios disponibles
        inicio = datetime.strptime(config['hora_inicio'].strftime('%H:%M'), '%H:%M')
        fin = datetime.strptime(config['hora_fin'].strftime('%H:%M'), '%H:%M')
        intervalo = config['intervalo']
        
        horarios = []
        current = inicio
        while current < fin:
            h_str = current.strftime('%H:%M')
            if h_str not in ocupados:
                horarios.append(h_str)
            current += timedelta(minutes=intervalo)
        
        cur.close()
        conn.close()
        return {"horarios": horarios}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")

@app.post("/api/turnos")
async def crear_turno(turno: TurnoCreate):
    try:
        # Validar fecha futura
        fecha_turno = datetime.strptime(turno.fecha, '%Y-%m-%d').date()
        hoy = datetime.now().date()
        if fecha_turno < hoy:
            return JSONResponse({"success": False, "error": "No se aceptan fechas pasadas"})
        
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        # Verificar disponibilidad
        cur.execute('SELECT 1 FROM turnos WHERE fecha = %s AND hora = %s AND estado != %s', 
                   (turno.fecha, turno.hora, 'cancelado'))
        if cur.fetchone():
            return JSONResponse({"success": False, "error": "Horario ya reservado"})
        
        # Insertar turno
        cur.execute('''
            INSERT INTO turnos (nombre, email, telefono, fecha, hora, motivo)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (turno.nombre, turno.email, turno.telefono, turno.fecha, turno.hora, turno.motivo))
        
        conn.commit()
        cur.close()
        conn.close()
        return JSONResponse({"success": True})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": "Error al agendar"})

# === RUTAS ADMIN ===
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    return templates.TemplateResponse("admin_panel.html", {"request": request})

@app.get("/api/admin/estadisticas")
async def get_estadisticas():
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM turnos')
    total = cur.fetchone()['count']
    
    cur.execute('SELECT COUNT(*) FROM turnos WHERE estado = %s', ('pendiente',))
    confirmados = cur.fetchone()['count']
    
    hoy = datetime.now().strftime('%Y-%m-%d')
    cur.execute('SELECT COUNT(*) FROM turnos WHERE fecha = %s AND estado != %s', (hoy, 'cancelado'))
    hoy_count = cur.fetchone()['count']
    
    cur.execute('SELECT COUNT(*) FROM turnos WHERE estado = %s', ('cancelado',))
    cancelados = cur.fetchone()['count']
    
    cur.close()
    conn.close()
    return {
        "total": total,
        "confirmados": confirmados,
        "hoy": hoy_count,
        "cancelados": cancelados
    }

@app.get("/api/admin/turnos")
async def get_turnos():
    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM turnos ORDER BY created_at DESC')
    turnos = cur.fetchall()
    cur.close()
    conn.close()
    return {"turnos": [dict(t) for t in turnos]}

@app.get("/api/admin/horarios")
async def get_horarios_admin():
    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM config_horarios ORDER BY dia_semana')
    horarios = cur.fetchall()
    cur.close()
    conn.close()
    return {"horarios": [dict(h) for h in horarios]}

@app.put("/api/admin/horarios/{dia}")
async def update_horario(dia: int, request: Request):
    if not (1 <= dia <= 7):
        raise HTTPException(status_code=400, detail="Día inválido")
    
    body = await request.json()
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        INSERT INTO config_horarios (dia_semana, hora_inicio, hora_fin, intervalo, activo)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (dia_semana) 
        DO UPDATE SET 
            hora_inicio = EXCLUDED.hora_inicio,
            hora_fin = EXCLUDED.hora_fin,
            intervalo = EXCLUDED.intervalo,
            activo = EXCLUDED.activo
    ''', (
        dia,
        body.get("hora_inicio", "09:00:00"),
        body.get("hora_fin", "18:00:00"),
        int(body.get("intervalo", 30)),
        bool(body.get("activo", False))
    ))
    
    conn.commit()
    cur.close()
    conn.close()
    return JSONResponse({"success": True})

@app.post("/api/admin/turnos/{id}/cancelar")
async def cancelar_turno(id: int):
    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE turnos SET estado = %s WHERE id = %s', ('cancelado', id))
    conn.commit()
    cur.close()
    conn.close()
    return {"success": True}

# === SERVIDOR ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)