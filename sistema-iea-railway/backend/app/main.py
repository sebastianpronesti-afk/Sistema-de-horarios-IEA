from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from openpyxl import load_workbook
from typing import List, Optional
import io
import re

from app.database import engine, get_db, Base
from app.models.models import (
    Sede, Cuatrimestre, Catedra, Docente, DocenteSede,
    Alumno, Curso, Asignacion, Inscripcion
)

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema Horarios IEA", version="3.0")

# CORS - permitir frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== INICIALIZACIÓN ====================

@app.on_event("startup")
async def startup():
    db = next(get_db())
    # Crear sedes por defecto
    sedes_default = [
        ("Online - Interior", "bg-purple-500"),
        ("Online - Exterior", "bg-violet-500"),
        ("Online - Cursos", "bg-fuchsia-500"),
        ("Online", "bg-purple-400"),
        ("Avellaneda", "bg-blue-500"),
        ("Caballito", "bg-emerald-500"),
        ("Vicente Lopez", "bg-amber-500"),
        ("Liniers", "bg-pink-500"),
        ("Monte Grande", "bg-cyan-500"),
        ("La Plata", "bg-indigo-500"),
        ("Pilar", "bg-rose-500"),
        ("BCE", "bg-lime-500"),
        ("BEA", "bg-teal-500"),
        ("Remoto", "bg-gray-500"),
    ]
    for nombre, color in sedes_default:
        if not db.query(Sede).filter(Sede.nombre == nombre).first():
            db.add(Sede(nombre=nombre, color=color))
    
    # Crear cuatrimestres por defecto
    if not db.query(Cuatrimestre).first():
        db.add(Cuatrimestre(nombre="1er Cuatrimestre 2026", anio=2026, numero=1, activo=True))
        db.add(Cuatrimestre(nombre="2do Cuatrimestre 2026", anio=2026, numero=2, activo=False))
    
    db.commit()
    db.close()

# ==================== ENDPOINTS BÁSICOS ====================

@app.get("/")
def root():
    return {"status": "ok", "sistema": "IEA Horarios v3.1"}

# ==================== AUTENTICACIÓN SIMPLE ====================

CLAVE_ACCESO = "IEA2026"  # Cambiar esta contraseña por la que quieras

@app.post("/api/login")
def login(data: dict):
    """Login con contraseña única compartida"""
    clave = data.get("clave", "")
    if clave == CLAVE_ACCESO:
        return {"ok": True, "mensaje": "Acceso autorizado"}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

@app.get("/api/sedes")
def get_sedes(db: Session = Depends(get_db)):
    return db.query(Sede).all()

@app.get("/api/cuatrimestres")
def get_cuatrimestres(db: Session = Depends(get_db)):
    return db.query(Cuatrimestre).all()

# ==================== CÁTEDRAS ====================

@app.get("/api/catedras")
def get_catedras(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    catedras = db.query(Catedra).all()
    result = []
    for c in catedras:
        inscriptos = db.query(Inscripcion).filter(Inscripcion.catedra_id == c.id)
        if cuatrimestre_id:
            inscriptos = inscriptos.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
        inscriptos_count = inscriptos.count()
        
        asignaciones = db.query(Asignacion).filter(Asignacion.catedra_id == c.id)
        if cuatrimestre_id:
            asignaciones = asignaciones.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
        
        asig_list = []
        for a in asignaciones.all():
            docente = None
            if a.docente:
                # Obtener sedes del docente
                sedes_docente = [ds.sede.nombre for ds in a.docente.sedes]
                docente = {
                    "id": a.docente.id,
                    "nombre": f"{a.docente.nombre} {a.docente.apellido}",
                    "sedes": sedes_docente,
                    "tipo_modalidad": calcular_tipo_modalidad(a.docente, db)
                }
            asig_list.append({
                "id": a.id,
                "modalidad": a.modalidad,
                "docente": docente,
                "dia": a.dia,
                "hora_inicio": a.hora_inicio,
                "hora_fin": a.hora_fin,
                "sede_id": a.sede_id,
                "sede_nombre": a.sede.nombre if a.sede else None,
                "recibe_alumnos_presenciales": a.recibe_alumnos_presenciales,
                "cuatrimestre_id": a.cuatrimestre_id
            })
        
        result.append({
            "id": c.id,
            "codigo": c.codigo,
            "nombre": c.nombre,
            "link_meet": c.link_meet,
            "inscriptos": inscriptos_count,
            "asignaciones": asig_list
        })
    return result

@app.get("/api/catedras/stats")
def get_catedras_stats(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    total = db.query(Catedra).count()
    
    asignaciones = db.query(Asignacion)
    if cuatrimestre_id:
        asignaciones = asignaciones.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    
    asincronicas = asignaciones.filter(Asignacion.modalidad == "asincronica").count()
    con_docente = asignaciones.filter(Asignacion.docente_id != None, Asignacion.modalidad != "asincronica").count()
    sin_docente = asignaciones.filter(Asignacion.docente_id == None, Asignacion.modalidad != "asincronica").count()
    
    inscriptos = db.query(Inscripcion)
    if cuatrimestre_id:
        inscriptos = inscriptos.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
    total_inscriptos = inscriptos.count()
    
    return {
        "total": total,
        "asignaciones": asignaciones.count(),
        "asincronicas": asincronicas,
        "con_docente": con_docente,
        "sin_docente": sin_docente,
        "inscriptos": total_inscriptos
    }

@app.put("/api/catedras/{catedra_id}")
def actualizar_catedra(catedra_id: int, data: dict, db: Session = Depends(get_db)):
    catedra = db.query(Catedra).filter(Catedra.id == catedra_id).first()
    if not catedra:
        raise HTTPException(status_code=404, detail="Cátedra no encontrada")
    
    if "link_meet" in data:
        catedra.link_meet = data["link_meet"]
    if "nombre" in data:
        catedra.nombre = data["nombre"]
    
    db.commit()
    return {"message": "Cátedra actualizada"}

# ==================== ASIGNACIONES ====================

@app.post("/api/asignaciones")
def crear_asignacion(data: dict, db: Session = Depends(get_db)):
    # Verificar solapamiento antes de crear
    if data.get("dia") and data.get("hora_inicio"):
        solapamiento = verificar_solapamiento_catedra(
            db=db,
            catedra_id=data["catedra_id"],
            dia=data["dia"],
            hora_inicio=data["hora_inicio"],
            hora_fin=data.get("hora_fin"),
            cuatrimestre_id=data["cuatrimestre_id"],
            excluir_asignacion_id=None
        )
        if solapamiento:
            raise HTTPException(
                status_code=400, 
                detail=f"SOLAPAMIENTO: La cátedra ya tiene una clase programada el {data['dia']} a las {data['hora_inicio']}. "
                       f"Como comparten el link de Meet, no pueden darse al mismo tiempo."
            )
    
    asignacion = Asignacion(
        catedra_id=data["catedra_id"],
        cuatrimestre_id=data["cuatrimestre_id"],
        modalidad=data["modalidad"],
        docente_id=data.get("docente_id"),
        dia=data.get("dia"),
        hora_inicio=data.get("hora_inicio"),
        hora_fin=data.get("hora_fin"),
        sede_id=data.get("sede_id"),
        recibe_alumnos_presenciales=data.get("recibe_alumnos_presenciales", False)
    )
    db.add(asignacion)
    db.commit()
    db.refresh(asignacion)
    return {"id": asignacion.id, "message": "Asignación creada"}

@app.put("/api/asignaciones/{asignacion_id}")
def actualizar_asignacion(asignacion_id: int, data: dict, db: Session = Depends(get_db)):
    asig = db.query(Asignacion).filter(Asignacion.id == asignacion_id).first()
    if not asig:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    
    # Verificar solapamiento si se cambia día/hora
    nuevo_dia = data.get("dia", asig.dia)
    nueva_hora = data.get("hora_inicio", asig.hora_inicio)
    
    if nuevo_dia and nueva_hora:
        solapamiento = verificar_solapamiento_catedra(
            db=db,
            catedra_id=asig.catedra_id,
            dia=nuevo_dia,
            hora_inicio=nueva_hora,
            hora_fin=data.get("hora_fin", asig.hora_fin),
            cuatrimestre_id=asig.cuatrimestre_id,
            excluir_asignacion_id=asignacion_id
        )
        if solapamiento:
            raise HTTPException(
                status_code=400,
                detail=f"SOLAPAMIENTO: La cátedra ya tiene otra clase el {nuevo_dia} a las {nueva_hora}."
            )
    
    if "docente_id" in data:
        asig.docente_id = data["docente_id"]
    if "dia" in data:
        asig.dia = data["dia"]
    if "hora_inicio" in data:
        asig.hora_inicio = data["hora_inicio"]
    if "hora_fin" in data:
        asig.hora_fin = data["hora_fin"]
    if "modalidad" in data:
        asig.modalidad = data["modalidad"]
    if "sede_id" in data:
        asig.sede_id = data["sede_id"]
    if "recibe_alumnos_presenciales" in data:
        asig.recibe_alumnos_presenciales = data["recibe_alumnos_presenciales"]
    
    asig.modificada = True
    db.commit()
    return {"message": "Asignación actualizada"}

@app.delete("/api/asignaciones/{asignacion_id}")
def eliminar_asignacion(asignacion_id: int, db: Session = Depends(get_db)):
    asig = db.query(Asignacion).filter(Asignacion.id == asignacion_id).first()
    if not asig:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    db.delete(asig)
    db.commit()
    return {"message": "Asignación eliminada"}

# ==================== DOCENTES ====================

def calcular_tipo_modalidad(docente: Docente, db: Session) -> str:
    """
    Deduce el tipo de modalidad del docente basándose en sus asignaciones:
    - PRESENCIAL_VIRTUAL: tiene asignaciones con recibe_alumnos_presenciales=True
    - SEDE_VIRTUAL: tiene asignaciones con sede pero ninguna recibe alumnos presenciales
    - REMOTO: todas sus asignaciones son sin sede física
    - SIN_ASIGNACIONES: no tiene asignaciones aún
    """
    asignaciones = db.query(Asignacion).filter(
        Asignacion.docente_id == docente.id,
        Asignacion.modalidad != "asincronica"
    ).all()
    
    if not asignaciones:
        return "SIN_ASIGNACIONES"
    
    tiene_presencial = any(a.recibe_alumnos_presenciales for a in asignaciones)
    tiene_sede = any(a.sede_id is not None for a in asignaciones)
    
    if tiene_presencial:
        return "PRESENCIAL_VIRTUAL"
    elif tiene_sede:
        return "SEDE_VIRTUAL"
    else:
        return "REMOTO"

@app.get("/api/docentes")
def get_docentes(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    docentes = db.query(Docente).all()
    result = []
    for d in docentes:
        # Obtener sedes del docente
        sedes = [{"id": ds.sede.id, "nombre": ds.sede.nombre, "color": ds.sede.color} for ds in d.sedes]
        
        asignaciones = db.query(Asignacion).filter(Asignacion.docente_id == d.id)
        if cuatrimestre_id:
            asignaciones = asignaciones.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
        
        asig_list = []
        total_alumnos = 0
        for a in asignaciones.all():
            catedra = db.query(Catedra).filter(Catedra.id == a.catedra_id).first()
            inscriptos = db.query(Inscripcion).filter(
                Inscripcion.catedra_id == a.catedra_id,
                Inscripcion.cuatrimestre_id == a.cuatrimestre_id
            ).count() if cuatrimestre_id else 0
            total_alumnos += inscriptos
            
            asig_list.append({
                "id": a.id,
                "catedra_codigo": catedra.codigo if catedra else None,
                "catedra_nombre": catedra.nombre if catedra else None,
                "modalidad": a.modalidad,
                "dia": a.dia,
                "hora_inicio": a.hora_inicio,
                "hora_fin": a.hora_fin,
                "sede_id": a.sede_id,
                "sede_nombre": a.sede.nombre if a.sede else "Remoto",
                "recibe_alumnos_presenciales": a.recibe_alumnos_presenciales
            })
        
        result.append({
            "id": d.id,
            "nombre": d.nombre,
            "apellido": d.apellido,
            "dni": d.dni,
            "email": d.email,
            "sedes": sedes,  # Ahora es una lista de sedes
            "tipo_modalidad": calcular_tipo_modalidad(d, db),
            "asignaciones": asig_list,
            "total_horas": len(asig_list) * 2,
            "total_alumnos": total_alumnos
        })
    return result

@app.post("/api/docentes")
def crear_docente(data: dict, db: Session = Depends(get_db)):
    # Verificar DNI único
    existente = db.query(Docente).filter(Docente.dni == data["dni"]).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe un docente con ese DNI")
    
    docente = Docente(
        dni=data["dni"],
        nombre=data["nombre"],
        apellido=data["apellido"],
        email=data.get("email")
    )
    db.add(docente)
    db.commit()
    db.refresh(docente)
    
    return {"id": docente.id, "message": "Docente creado"}

@app.put("/api/docentes/{docente_id}")
def actualizar_docente(docente_id: int, data: dict, db: Session = Depends(get_db)):
    docente = db.query(Docente).filter(Docente.id == docente_id).first()
    if not docente:
        raise HTTPException(status_code=404, detail="Docente no encontrado")
    
    if "nombre" in data:
        docente.nombre = data["nombre"]
    if "apellido" in data:
        docente.apellido = data["apellido"]
    if "email" in data:
        docente.email = data["email"]
    
    db.commit()
    return {"message": "Docente actualizado"}

@app.delete("/api/docentes/{docente_id}")
def eliminar_docente(docente_id: int, db: Session = Depends(get_db)):
    docente = db.query(Docente).filter(Docente.id == docente_id).first()
    if not docente:
        raise HTTPException(status_code=404, detail="Docente no encontrado")
    db.delete(docente)
    db.commit()
    return {"message": "Docente eliminado"}

# ==================== DOCENTE - SEDES ====================

@app.post("/api/docentes/{docente_id}/sedes")
def agregar_sede_docente(docente_id: int, data: dict, db: Session = Depends(get_db)):
    """Agregar una sede a un docente"""
    docente = db.query(Docente).filter(Docente.id == docente_id).first()
    if not docente:
        raise HTTPException(status_code=404, detail="Docente no encontrado")
    
    sede = db.query(Sede).filter(Sede.id == data["sede_id"]).first()
    if not sede:
        raise HTTPException(status_code=404, detail="Sede no encontrada")
    
    # Verificar si ya tiene esa sede
    existe = db.query(DocenteSede).filter(
        DocenteSede.docente_id == docente_id,
        DocenteSede.sede_id == data["sede_id"]
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail="El docente ya tiene asignada esa sede")
    
    docente_sede = DocenteSede(docente_id=docente_id, sede_id=data["sede_id"])
    db.add(docente_sede)
    db.commit()
    
    return {"message": f"Sede {sede.nombre} agregada al docente"}

@app.delete("/api/docentes/{docente_id}/sedes/{sede_id}")
def quitar_sede_docente(docente_id: int, sede_id: int, db: Session = Depends(get_db)):
    """Quitar una sede de un docente"""
    docente_sede = db.query(DocenteSede).filter(
        DocenteSede.docente_id == docente_id,
        DocenteSede.sede_id == sede_id
    ).first()
    
    if not docente_sede:
        raise HTTPException(status_code=404, detail="El docente no tiene asignada esa sede")
    
    db.delete(docente_sede)
    db.commit()
    
    return {"message": "Sede removida del docente"}

@app.put("/api/docentes/{docente_id}/sedes")
def actualizar_sedes_docente(docente_id: int, data: dict, db: Session = Depends(get_db)):
    """Reemplazar todas las sedes de un docente"""
    docente = db.query(Docente).filter(Docente.id == docente_id).first()
    if not docente:
        raise HTTPException(status_code=404, detail="Docente no encontrado")
    
    # Eliminar sedes actuales
    db.query(DocenteSede).filter(DocenteSede.docente_id == docente_id).delete()
    
    # Agregar nuevas sedes
    for sede_id in data.get("sede_ids", []):
        docente_sede = DocenteSede(docente_id=docente_id, sede_id=sede_id)
        db.add(docente_sede)
    
    db.commit()
    return {"message": "Sedes actualizadas"}

# ==================== IMPORTAR ====================

@app.post("/api/importar/docentes")
async def importar_docentes(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Importar docentes desde Excel.
    Detecta automáticamente las columnas por nombre de header.
    Headers aceptados: DNI/Documento, Nombre/Nombres, Apellido/Apellidos, Email/Mail/Correo
    NO se asigna sede por defecto.
    """
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        
        # Detectar headers de forma flexible
        headers_raw = []
        for cell in ws[1]:
            headers_raw.append(str(cell.value).lower().strip() if cell.value else "")
        
        # Mapear columnas
        col_map = {"dni": -1, "nombre": -1, "apellido": -1, "email": -1}
        for i, h in enumerate(headers_raw):
            if any(x in h for x in ["dni", "documento", "doc.", "nro doc"]):
                col_map["dni"] = i
            elif h in ["nombre", "nombres", "name"] or h == "nombre/s":
                col_map["nombre"] = i
            elif any(x in h for x in ["apellido", "apellidos", "surname"]):
                col_map["apellido"] = i
            elif any(x in h for x in ["mail", "email", "correo", "e-mail"]):
                col_map["email"] = i
        
        # Si no detectó columnas por header, intentar por posición estándar
        if col_map["dni"] == -1:
            col_map = {"dni": 0, "nombre": 1, "apellido": 2, "email": 3}
        
        creados = 0
        actualizados = 0
        errores = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            
            def get_val(key):
                idx = col_map.get(key, -1)
                return vals[idx] if 0 <= idx < len(vals) and vals[idx] else None
            
            dni = get_val("dni")
            nombre = get_val("nombre")
            apellido = get_val("apellido")
            email = get_val("email")
            
            # Limpiar DNI
            if dni:
                dni = dni.replace(".", "").replace("-", "").replace(" ", "")
                # Si es un número con decimales (Excel), quitar el .0
                if dni.endswith(".0"):
                    dni = dni[:-2]
            
            if not dni or len(dni) < 7:
                continue
            
            existente = db.query(Docente).filter(Docente.dni == dni).first()
            if existente:
                if nombre and nombre != existente.nombre:
                    existente.nombre = nombre
                if apellido and apellido != existente.apellido:
                    existente.apellido = apellido
                if email and email != existente.email:
                    existente.email = email
                actualizados += 1
            else:
                if not nombre:
                    errores.append(f"Fila {row_num}: DNI {dni} sin nombre")
                    continue
                
                docente = Docente(
                    dni=dni,
                    nombre=nombre,
                    apellido=apellido or "",
                    email=email
                )
                db.add(docente)
                creados += 1
        
        db.commit()
        wb.close()
        return {
            "creados": creados,
            "actualizados": actualizados,
            "total_procesados": creados + actualizados,
            "errores": errores[:10]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando archivo: {str(e)}")

def detectar_sede(texto: str) -> str | None:
    texto = texto.lower()
    sedes_map = {
        "avellaneda": "Avellaneda",
        "caballito": "Caballito",
        "vicente lopez": "Vicente Lopez",
        "vicente lópez": "Vicente Lopez",
        "vte lopez": "Vicente Lopez",
        "vte lópez": "Vicente Lopez",
        "liniers": "Liniers",
        "monte grande": "Monte Grande",
        "la plata": "La Plata",
        "pilar": "Pilar",
        "online - interior": "Online - Interior",
        "online - exterior": "Online - Exterior",
        "online - cursos": "Online - Cursos",
        "interior": "Online - Interior",
        "exterior": "Online - Exterior",
        "bce": "BCE",
        "bea": "BEA",
        "online": "Online",
    }
    for key, value in sedes_map.items():
        if key in texto:
            return value
    return None

@app.post("/api/importar/catedras")
async def importar_catedras(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Importar cátedras desde Excel.
    Acepta estos formatos:
    - Columna A: número, Columna B: "c.XX NombreDeLaCatedra"
    - Columna A: "c.XX", Columna B: nombre
    - Columna A: "c.XX NombreDeLaCatedra" (todo junto)
    """
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        
        # Buscar la hoja correcta (priorizar "cátedras" o la primera)
        ws = None
        for name in wb.sheetnames:
            if "catedr" in name.lower() or "cátedr" in name.lower():
                ws = wb[name]
                break
        if ws is None:
            ws = wb[wb.sheetnames[0]]
        
        creadas = 0
        actualizadas = 0
        errores = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            codigo = None
            nombre = None
            
            # Obtener valores de las celdas
            vals = [str(c).strip() if c is not None else "" for c in row]
            
            # Formato 1: col_A=número, col_B="c.XX Nombre"
            if len(vals) >= 2 and vals[1]:
                text = vals[1].strip()
                match = re.match(r'^(c\.\d+)\s+(.+)', text, re.IGNORECASE)
                if match:
                    codigo = match.group(1)
                    nombre = match.group(2).strip()
                else:
                    # Formato 2: col_A="c.XX", col_B="Nombre"
                    if re.match(r'^c\.\d+$', vals[0], re.IGNORECASE):
                        codigo = vals[0]
                        nombre = vals[1]
                    elif re.match(r'^c\.\d+$', text, re.IGNORECASE):
                        codigo = text
                        nombre = vals[0] if vals[0] and not vals[0].replace('.','').isdigit() else f"Cátedra {text}"
            
            # Formato 3: col_A es un número que usamos como c.XX
            if not codigo and len(vals) >= 2:
                try:
                    num = int(float(vals[0]))
                    if num > 0 and vals[1]:
                        text = vals[1].strip()
                        match = re.match(r'^(c\.\d+)\s+(.+)', text, re.IGNORECASE)
                        if match:
                            codigo = match.group(1)
                            nombre = match.group(2).strip()
                        else:
                            codigo = f"c.{num}"
                            nombre = text
                except (ValueError, TypeError):
                    pass
            
            if codigo:
                existente = db.query(Catedra).filter(Catedra.codigo == codigo).first()
                if existente:
                    if nombre and nombre != existente.nombre:
                        existente.nombre = nombre
                        actualizadas += 1
                else:
                    nueva = Catedra(codigo=codigo, nombre=nombre or f"Cátedra {codigo}")
                    db.add(nueva)
                    creadas += 1
        
        db.commit()
        wb.close()
        return {"creadas": creadas, "actualizadas": actualizadas, "errores": errores[:5]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando archivo: {str(e)}")

@app.post("/api/importar/cursos")
async def importar_cursos(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Importar cursos desde Excel.
    Formato esperado: Columna A = Sede, Columna B = Nombre del curso
    Filtra automáticamente los cursos marcados como NO DISPONIBLE o BAJAS.
    """
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        
        creados = 0
        omitidos = 0
        errores = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            
            sede_texto = vals[0] if len(vals) > 0 else ""
            nombre = vals[1] if len(vals) > 1 else vals[0] if len(vals) > 0 else ""
            
            if not nombre or len(nombre) < 3:
                continue
            
            # Filtrar cursos no disponibles
            nombre_lower = nombre.lower()
            if any(x in nombre_lower for x in ["no disponible", "baja", "//bajas//", "test ", "prueba"]):
                omitidos += 1
                continue
            
            # Buscar sede
            sede = None
            if sede_texto:
                sede = db.query(Sede).filter(Sede.nombre == sede_texto).first()
                if not sede:
                    # Intentar con detectar_sede
                    sede_nombre = detectar_sede(sede_texto)
                    if sede_nombre:
                        sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first()
                    
                    # Si no existe, crear la sede
                    if not sede and len(sede_texto) > 2:
                        sede = Sede(nombre=sede_texto, color="bg-gray-500")
                        db.add(sede)
                        db.flush()
            
            existente = db.query(Curso).filter(Curso.nombre == nombre).first()
            if not existente:
                curso = Curso(nombre=nombre, sede_id=sede.id if sede else None)
                db.add(curso)
                creados += 1
        
        db.commit()
        wb.close()
        return {"creados": creados, "omitidos": omitidos, "errores": errores[:5]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando archivo: {str(e)}")

@app.post("/api/importar/inscripciones")
async def importar_inscripciones(
    file: UploadFile = File(...),
    cuatrimestre_id: int = 1,
    catedra_codigo: str = None,
    db: Session = Depends(get_db)
):
    content = await file.read()
    wb = load_workbook(filename=io.BytesIO(content), read_only=True)
    ws = wb.active
    
    catedra = None
    if catedra_codigo:
        catedra = db.query(Catedra).filter(Catedra.codigo == catedra_codigo).first()
    
    headers = []
    for cell in ws[1]:
        headers.append(str(cell.value).lower() if cell.value else "")
    
    alumnos_creados = 0
    inscripciones_creadas = 0
    
    for row in ws.iter_rows(min_row=2, values_only=True):
        dni = None
        nombre = None
        apellido = None
        email = None
        curso_nombre = None
        
        for i, cell in enumerate(row):
            if i < len(headers) and cell:
                val = str(cell).strip()
                col = headers[i]
                
                if "dni" in col or "documento" in col:
                    dni = val.replace(".", "")
                elif "nombre" in col and "apellido" not in col:
                    nombre = val
                elif "apellido" in col:
                    apellido = val
                elif "mail" in col or "email" in col:
                    email = val
                elif "carrera" in col or "curso" in col:
                    curso_nombre = val
        
        if dni and len(dni) >= 7:
            alumno = db.query(Alumno).filter(Alumno.dni == dni).first()
            if not alumno:
                alumno = Alumno(dni=dni, nombre=nombre, apellido=apellido, email=email)
                db.add(alumno)
                db.flush()
                alumnos_creados += 1
            
            catedra_inscripcion = catedra
            if not catedra_inscripcion and curso_nombre:
                match = re.search(r'c\.(\d+)', curso_nombre.lower())
                if match:
                    cod = f"c.{match.group(1)}"
                    catedra_inscripcion = db.query(Catedra).filter(Catedra.codigo == cod).first()
            
            if catedra_inscripcion:
                existe = db.query(Inscripcion).filter(
                    Inscripcion.alumno_id == alumno.id,
                    Inscripcion.catedra_id == catedra_inscripcion.id,
                    Inscripcion.cuatrimestre_id == cuatrimestre_id
                ).first()
                
                if not existe:
                    curso = db.query(Curso).filter(Curso.nombre == curso_nombre).first() if curso_nombre else None
                    inscripcion = Inscripcion(
                        alumno_id=alumno.id,
                        catedra_id=catedra_inscripcion.id,
                        cuatrimestre_id=cuatrimestre_id,
                        curso_id=curso.id if curso else None
                    )
                    db.add(inscripcion)
                    inscripciones_creadas += 1
    
    db.commit()
    wb.close()
    return {
        "alumnos_creados": alumnos_creados,
        "inscripciones_creadas": inscripciones_creadas
    }

# ==================== HORARIOS ====================

@app.get("/api/horarios")
def get_horarios(cuatrimestre_id: int = None, sede_id: int = None, db: Session = Depends(get_db)):
    asignaciones = db.query(Asignacion).filter(
        Asignacion.dia != None,
        Asignacion.hora_inicio != None,
        Asignacion.docente_id != None
    )
    if cuatrimestre_id:
        asignaciones = asignaciones.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    if sede_id:
        asignaciones = asignaciones.filter(Asignacion.sede_id == sede_id)
    
    result = []
    for a in asignaciones.all():
        catedra = db.query(Catedra).filter(Catedra.id == a.catedra_id).first()
        docente = db.query(Docente).filter(Docente.id == a.docente_id).first()
        result.append({
            "id": a.id,
            "catedra_codigo": catedra.codigo if catedra else None,
            "catedra_nombre": catedra.nombre if catedra else None,
            "docente_nombre": f"{docente.nombre} {docente.apellido}" if docente else None,
            "docente_tipo": calcular_tipo_modalidad(docente, db) if docente else None,
            "sede_nombre": a.sede.nombre if a.sede else "Remoto",
            "modalidad": a.modalidad,
            "dia": a.dia,
            "hora_inicio": a.hora_inicio,
            "hora_fin": a.hora_fin,
            "recibe_alumnos_presenciales": a.recibe_alumnos_presenciales
        })
    return result

# ==================== SOLAPAMIENTOS ====================

def verificar_solapamiento_catedra(
    db: Session,
    catedra_id: int,
    dia: str,
    hora_inicio: str,
    hora_fin: str,
    cuatrimestre_id: int,
    excluir_asignacion_id: int = None
) -> bool:
    """
    Verifica si hay solapamiento para una cátedra.
    REGLA: La misma cátedra NO puede tener dos clases en el mismo día y hora,
    sin importar la sede (porque comparten el link de Meet).
    """
    query = db.query(Asignacion).filter(
        Asignacion.catedra_id == catedra_id,
        Asignacion.cuatrimestre_id == cuatrimestre_id,
        Asignacion.dia == dia,
        Asignacion.hora_inicio == hora_inicio
    )
    
    if excluir_asignacion_id:
        query = query.filter(Asignacion.id != excluir_asignacion_id)
    
    return query.first() is not None

@app.get("/api/horarios/solapamientos")
def get_solapamientos(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    """
    Detecta dos tipos de solapamientos:
    1. SOLAPAMIENTO DE CÁTEDRA: misma cátedra en mismo día/hora (crítico - comparten Meet)
    2. SOLAPAMIENTO DE DOCENTE: mismo docente en mismo día/hora
    """
    asignaciones = db.query(Asignacion).filter(
        Asignacion.dia != None,
        Asignacion.hora_inicio != None
    )
    if cuatrimestre_id:
        asignaciones = asignaciones.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    
    asigs = asignaciones.all()
    solapamientos = []
    
    for i, a1 in enumerate(asigs):
        for a2 in asigs[i+1:]:
            # SOLAPAMIENTO DE CÁTEDRA (crítico)
            if (a1.catedra_id == a2.catedra_id and 
                a1.dia == a2.dia and 
                a1.hora_inicio == a2.hora_inicio):
                
                cat = db.query(Catedra).filter(Catedra.id == a1.catedra_id).first()
                doc1 = db.query(Docente).filter(Docente.id == a1.docente_id).first() if a1.docente_id else None
                doc2 = db.query(Docente).filter(Docente.id == a2.docente_id).first() if a2.docente_id else None
                
                solapamientos.append({
                    "tipo": "CATEDRA",
                    "severidad": "CRITICO",
                    "mensaje": f"La cátedra {cat.codigo} tiene dos clases el mismo día/hora. Comparten link de Meet.",
                    "catedra": cat.codigo if cat else None,
                    "dia": a1.dia,
                    "hora": a1.hora_inicio,
                    "asignacion1": {
                        "id": a1.id,
                        "docente": f"{doc1.nombre} {doc1.apellido}" if doc1 else "Sin docente",
                        "sede": a1.sede.nombre if a1.sede else "Remoto",
                        "modalidad": a1.modalidad
                    },
                    "asignacion2": {
                        "id": a2.id,
                        "docente": f"{doc2.nombre} {doc2.apellido}" if doc2 else "Sin docente",
                        "sede": a2.sede.nombre if a2.sede else "Remoto",
                        "modalidad": a2.modalidad
                    }
                })
            
            # SOLAPAMIENTO DE DOCENTE
            elif (a1.docente_id and a1.docente_id == a2.docente_id and 
                  a1.dia == a2.dia and 
                  a1.hora_inicio == a2.hora_inicio):
                
                docente = db.query(Docente).filter(Docente.id == a1.docente_id).first()
                cat1 = db.query(Catedra).filter(Catedra.id == a1.catedra_id).first()
                cat2 = db.query(Catedra).filter(Catedra.id == a2.catedra_id).first()
                
                solapamientos.append({
                    "tipo": "DOCENTE",
                    "severidad": "ALTO",
                    "mensaje": f"{docente.nombre} {docente.apellido} tiene dos clases el mismo día/hora",
                    "docente": f"{docente.nombre} {docente.apellido}" if docente else None,
                    "dia": a1.dia,
                    "hora": a1.hora_inicio,
                    "catedra1": cat1.codigo if cat1 else None,
                    "catedra2": cat2.codigo if cat2 else None
                })
    
    return solapamientos

@app.get("/api/exportar/horarios")
def exportar_horarios(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    return get_horarios(cuatrimestre_id, db=db)

# ==================== ESTADÍSTICAS DOCENTES ====================

@app.get("/api/docentes/estadisticas")
def get_estadisticas_docentes(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    """Estadísticas de docentes por tipo de modalidad"""
    docentes = db.query(Docente).all()
    
    stats = {
        "total": len(docentes),
        "presencial_virtual": 0,
        "sede_virtual": 0,
        "remoto": 0,
        "sin_asignaciones": 0
    }
    
    for d in docentes:
        tipo = calcular_tipo_modalidad(d, db)
        if tipo == "PRESENCIAL_VIRTUAL":
            stats["presencial_virtual"] += 1
        elif tipo == "SEDE_VIRTUAL":
            stats["sede_virtual"] += 1
        elif tipo == "REMOTO":
            stats["remoto"] += 1
        else:
            stats["sin_asignaciones"] += 1
    
    return stats

# ==================== IMPORTACIÓN MASIVA POR JSON ====================

@app.post("/api/importar/masivo")
async def importar_masivo(data: dict, db: Session = Depends(get_db)):
    """Importar sedes, cátedras y cursos en un solo request JSON"""
    resultado = {"sedes": 0, "catedras": 0, "cursos": 0, "errores": []}
    
    # Importar sedes
    for sede_nombre in data.get("sedes", []):
        if not db.query(Sede).filter(Sede.nombre == sede_nombre).first():
            db.add(Sede(nombre=sede_nombre, color="bg-gray-500"))
            resultado["sedes"] += 1
    db.commit()
    
    # Importar cátedras
    for cat in data.get("catedras", []):
        codigo = cat.get("codigo", "").strip()
        nombre = cat.get("nombre", "").strip()
        if not codigo:
            continue
        existente = db.query(Catedra).filter(Catedra.codigo == codigo).first()
        if existente:
            if nombre and nombre != existente.nombre:
                existente.nombre = nombre
        else:
            db.add(Catedra(codigo=codigo, nombre=nombre or f"Cátedra {codigo}"))
            resultado["catedras"] += 1
    db.commit()
    
    # Importar cursos
    for cur in data.get("cursos", []):
        nombre = cur.get("nombre", "").strip()
        sede_nombre = cur.get("sede", "").strip()
        if not nombre:
            continue
        existente = db.query(Curso).filter(Curso.nombre == nombre).first()
        if not existente:
            sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
            db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None))
            resultado["cursos"] += 1
    db.commit()
    
    return resultado


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
