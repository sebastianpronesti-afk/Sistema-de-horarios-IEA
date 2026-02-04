from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from openpyxl import load_workbook
import io
import re

from app.database import engine, get_db, Base
from app.models.models import Sede, Cuatrimestre, Catedra, Docente, Alumno, Curso, Asignacion, Inscripcion

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema Horarios IEA", version="2.0")

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
        ("Avellaneda", "bg-blue-500"),
        ("Caballito", "bg-emerald-500"),
        ("Vicente López", "bg-amber-500"),
        ("Liniers", "bg-pink-500"),
        ("Monte Grande", "bg-cyan-500"),
        ("La Plata", "bg-indigo-500"),
        ("Pilar", "bg-rose-500"),
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
    return {"status": "ok", "sistema": "IEA Horarios v2.0"}

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
                docente = {
                    "id": a.docente.id,
                    "nombre": f"{a.docente.nombre} {a.docente.apellido}",
                    "sede": a.docente.sede.nombre if a.docente.sede else None
                }
            asig_list.append({
                "id": a.id,
                "modalidad": a.modalidad,
                "docente": docente,
                "dia": a.dia,
                "hora": a.hora,
                "cuatrimestre_id": a.cuatrimestre_id
            })
        
        result.append({
            "id": c.id,
            "codigo": c.codigo,
            "nombre": c.nombre,
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

# ==================== ASIGNACIONES ====================

@app.post("/api/asignaciones")
def crear_asignacion(data: dict, db: Session = Depends(get_db)):
    asignacion = Asignacion(
        catedra_id=data["catedra_id"],
        cuatrimestre_id=data["cuatrimestre_id"],
        modalidad=data["modalidad"],
        docente_id=data.get("docente_id"),
        dia=data.get("dia"),
        hora=data.get("hora")
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
    
    if "docente_id" in data:
        asig.docente_id = data["docente_id"]
    if "dia" in data:
        asig.dia = data["dia"]
    if "hora" in data:
        asig.hora = data["hora"]
    if "modalidad" in data:
        asig.modalidad = data["modalidad"]
    
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

@app.get("/api/docentes")
def get_docentes(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    docentes = db.query(Docente).all()
    result = []
    for d in docentes:
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
                "hora": a.hora
            })
        
        result.append({
            "id": d.id,
            "nombre": d.nombre,
            "apellido": d.apellido,
            "dni": d.dni,
            "email": d.email,
            "sede": d.sede.nombre if d.sede else None,
            "sede_color": d.sede.color if d.sede else None,
            "asignaciones": asig_list,
            "horas": len(asig_list) * 2,
            "alumnos": total_alumnos
        })
    return result

@app.post("/api/docentes")
def crear_docente(data: dict, db: Session = Depends(get_db)):
    sede = db.query(Sede).filter(Sede.nombre == data.get("sede")).first() if data.get("sede") else None
    docente = Docente(
        nombre=data["nombre"],
        apellido=data["apellido"],
        dni=data["dni"],
        email=data.get("email"),
        sede_id=sede.id if sede else None
    )
    db.add(docente)
    db.commit()
    return {"id": docente.id, "message": "Docente creado"}

# ==================== IMPORTACIÓN (usando openpyxl) ====================

def detectar_sede(texto):
    if not texto:
        return None
    texto = texto.lower()
    sedes_map = {
        "avellaneda": "Avellaneda",
        "caballito": "Caballito",
        "vicente": "Vicente López",
        "liniers": "Liniers",
        "monte grande": "Monte Grande",
        "la plata": "La Plata",
        "pilar": "Pilar",
        "online": "Online - Interior",
        "interior": "Online - Interior",
    }
    for key, value in sedes_map.items():
        if key in texto:
            return value
    return None

@app.post("/api/importar/catedras")
async def importar_catedras(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    wb = load_workbook(filename=io.BytesIO(content), read_only=True)
    ws = wb.active
    
    creadas = 0
    actualizadas = 0
    
    for row in ws.iter_rows(min_row=2, values_only=True):
        codigo = None
        nombre = None
        
        for cell in row:
            if cell:
                val = str(cell).strip()
                if re.match(r'^c\.\d+', val.lower()):
                    codigo = val
                elif len(val) > 5 and not re.match(r'^c\.\d+', val.lower()):
                    nombre = val
        
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
    return {"creadas": creadas, "actualizadas": actualizadas}

@app.post("/api/importar/cursos")
async def importar_cursos(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    wb = load_workbook(filename=io.BytesIO(content), read_only=True)
    ws = wb.active
    
    creados = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        nombre = None
        for cell in row:
            if cell:
                val = str(cell).strip()
                if len(val) > 10:
                    nombre = val
                    break
        
        if nombre and "no disponible" not in nombre.lower() and "baja" not in nombre.lower():
            existente = db.query(Curso).filter(Curso.nombre == nombre).first()
            if not existente:
                sede_nombre = detectar_sede(nombre)
                sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
                curso = Curso(nombre=nombre, sede_id=sede.id if sede else None)
                db.add(curso)
                creados += 1
    
    db.commit()
    wb.close()
    return {"creados": creados}

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
def get_horarios(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    asignaciones = db.query(Asignacion).filter(
        Asignacion.dia != None,
        Asignacion.hora != None,
        Asignacion.docente_id != None
    )
    if cuatrimestre_id:
        asignaciones = asignaciones.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    
    result = []
    for a in asignaciones.all():
        catedra = db.query(Catedra).filter(Catedra.id == a.catedra_id).first()
        docente = db.query(Docente).filter(Docente.id == a.docente_id).first()
        result.append({
            "id": a.id,
            "catedra_codigo": catedra.codigo if catedra else None,
            "catedra_nombre": catedra.nombre if catedra else None,
            "docente_nombre": f"{docente.nombre} {docente.apellido}" if docente else None,
            "docente_sede": docente.sede.nombre if docente and docente.sede else None,
            "modalidad": a.modalidad,
            "dia": a.dia,
            "hora": a.hora
        })
    return result

@app.get("/api/horarios/solapamientos")
def get_solapamientos(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    asignaciones = db.query(Asignacion).filter(
        Asignacion.dia != None,
        Asignacion.hora != None,
        Asignacion.docente_id != None
    )
    if cuatrimestre_id:
        asignaciones = asignaciones.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    
    asigs = asignaciones.all()
    solapamientos = []
    
    for i, a1 in enumerate(asigs):
        for a2 in asigs[i+1:]:
            if a1.docente_id == a2.docente_id and a1.dia == a2.dia and a1.hora == a2.hora:
                docente = db.query(Docente).filter(Docente.id == a1.docente_id).first()
                cat1 = db.query(Catedra).filter(Catedra.id == a1.catedra_id).first()
                cat2 = db.query(Catedra).filter(Catedra.id == a2.catedra_id).first()
                solapamientos.append({
                    "docente": f"{docente.nombre} {docente.apellido}" if docente else None,
                    "dia": a1.dia,
                    "hora": a1.hora,
                    "catedra1": cat1.codigo if cat1 else None,
                    "catedra2": cat2.codigo if cat2 else None
                })
    
    return solapamientos

@app.get("/api/exportar/horarios")
def exportar_horarios(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    return get_horarios(cuatrimestre_id, db)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
