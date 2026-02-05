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
    Alumno, Curso, CatedraCurso, Asignacion, Inscripcion
)

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema Horarios IEA", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== STARTUP: MIGRACIÓN + SEED ====================

@app.on_event("startup")
async def startup():
    db = next(get_db())
    
    # --- Migrar estructura de BD (agregar columnas/tablas faltantes) ---
    from sqlalchemy import text, inspect
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'catedras' in tables:
            cols = [c['name'] for c in inspector.get_columns('catedras')]
            if 'link_meet' not in cols:
                db.execute(text("ALTER TABLE catedras ADD COLUMN link_meet VARCHAR"))
                db.commit()
        
        if 'asignaciones' in tables:
            cols = [c['name'] for c in inspector.get_columns('asignaciones')]
            for col, tipo in [('recibe_alumnos_presenciales', 'BOOLEAN DEFAULT FALSE'),
                              ('hora_inicio', 'VARCHAR'), ('hora_fin', 'VARCHAR'),
                              ('modificada', 'BOOLEAN DEFAULT FALSE')]:
                if col not in cols:
                    db.execute(text(f"ALTER TABLE asignaciones ADD COLUMN {col} {tipo}"))
                    db.commit()
        
        # Crear tablas nuevas si no existen
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"⚠️ Migración: {e}")
    
    # --- Cargar datos iniciales desde seed_data ---
    try:
        from app.seed_data import SEDES, CATEDRAS, CURSOS, DOCENTES
        
        for nombre, color in SEDES:
            if not db.query(Sede).filter(Sede.nombre == nombre).first():
                db.add(Sede(nombre=nombre, color=color))
        db.commit()
        
        if not db.query(Cuatrimestre).first():
            db.add(Cuatrimestre(nombre="1er Cuatrimestre 2026", anio=2026, numero=1, activo=True))
            db.add(Cuatrimestre(nombre="2do Cuatrimestre 2026", anio=2026, numero=2, activo=False))
            db.commit()
        
        if db.query(Catedra).count() == 0:
            for codigo, nombre in CATEDRAS:
                db.add(Catedra(codigo=codigo, nombre=nombre))
            db.commit()
            print(f"✅ {len(CATEDRAS)} cátedras cargadas")
        
        if db.query(Curso).count() == 0:
            for sede_nombre, nombre in CURSOS:
                sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first()
                db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None))
            db.commit()
            print(f"✅ {len(CURSOS)} cursos cargados")
        
        if db.query(Docente).count() == 0:
            for dni, nombre, apellido in DOCENTES:
                db.add(Docente(dni=dni, nombre=nombre, apellido=apellido))
            db.commit()
            print(f"✅ {len(DOCENTES)} docentes cargados")
    except ImportError:
        print("⚠️ seed_data.py no encontrado")
    except Exception as e:
        print(f"⚠️ Seed error: {e}")
    
    db.close()
    print("🚀 IEA Horarios v3.1 iniciado")

# ==================== AUTH ====================

CLAVE_ACCESO = "IEA2026"

@app.get("/")
def root():
    return {"status": "ok", "sistema": "IEA Horarios v3.1"}

@app.get("/api/reparar")
def reparar_bd(db: Session = Depends(get_db)):
    """Visitar esta URL para reparar la BD y cargar datos"""
    from sqlalchemy import text, inspect
    resultado = []
    
    try:
        inspector = inspect(engine)
        
        # 1. Agregar columnas faltantes
        if 'catedras' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('catedras')]
            if 'link_meet' not in cols:
                db.execute(text("ALTER TABLE catedras ADD COLUMN link_meet VARCHAR"))
                db.commit()
                resultado.append("✅ Columna link_meet agregada a catedras")
            else:
                resultado.append("OK link_meet ya existe")
        
        if 'asignaciones' in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns('asignaciones')]
            for col, tipo in [('recibe_alumnos_presenciales', 'BOOLEAN DEFAULT FALSE'),
                              ('hora_inicio', 'VARCHAR'), ('hora_fin', 'VARCHAR'),
                              ('modificada', 'BOOLEAN DEFAULT FALSE')]:
                if col not in cols:
                    db.execute(text(f"ALTER TABLE asignaciones ADD COLUMN {col} {tipo}"))
                    db.commit()
                    resultado.append(f"✅ Columna {col} agregada")
        
        # 2. Crear tablas que falten
        Base.metadata.create_all(bind=engine)
        resultado.append("OK tablas verificadas")
        
        # 3. Cargar datos
        try:
            from app.seed_data import SEDES, CATEDRAS, CURSOS, DOCENTES
            
            # Sedes
            nuevas_sedes = 0
            for nombre, color in SEDES:
                if not db.query(Sede).filter(Sede.nombre == nombre).first():
                    db.add(Sede(nombre=nombre, color=color))
                    nuevas_sedes += 1
            if nuevas_sedes > 0:
                db.commit()
                resultado.append(f"✅ {nuevas_sedes} sedes nuevas")
            
            # Cátedras
            total_cat = db.query(Catedra).count()
            if total_cat < 10:
                for codigo, nombre in CATEDRAS:
                    if not db.query(Catedra).filter(Catedra.codigo == codigo).first():
                        db.add(Catedra(codigo=codigo, nombre=nombre))
                db.commit()
                nuevo_total = db.query(Catedra).count()
                resultado.append(f"✅ Cátedras: {total_cat} → {nuevo_total}")
            else:
                resultado.append(f"OK {total_cat} cátedras ya existen")
            
            # Cursos
            total_cur = db.query(Curso).count()
            if total_cur < 10:
                for sede_nombre, nombre in CURSOS:
                    if not db.query(Curso).filter(Curso.nombre == nombre).first():
                        sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first()
                        db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None))
                db.commit()
                nuevo_total = db.query(Curso).count()
                resultado.append(f"✅ Cursos: {total_cur} → {nuevo_total}")
            else:
                resultado.append(f"OK {total_cur} cursos ya existen")
            
            # Docentes
            total_doc = db.query(Docente).count()
            if total_doc < 5:
                for dni, nombre, apellido in DOCENTES:
                    if not db.query(Docente).filter(Docente.dni == dni).first():
                        db.add(Docente(dni=dni, nombre=nombre, apellido=apellido))
                db.commit()
                nuevo_total = db.query(Docente).count()
                resultado.append(f"✅ Docentes: {total_doc} → {nuevo_total}")
            else:
                resultado.append(f"OK {total_doc} docentes ya existen")
            
            # Cuatrimestres
            if not db.query(Cuatrimestre).first():
                db.add(Cuatrimestre(nombre="1er Cuatrimestre 2026", anio=2026, numero=1, activo=True))
                db.add(Cuatrimestre(nombre="2do Cuatrimestre 2026", anio=2026, numero=2, activo=False))
                db.commit()
                resultado.append("✅ Cuatrimestres creados")
        
        except ImportError:
            resultado.append("⚠️ seed_data.py no encontrado")
    
    except Exception as e:
        resultado.append(f"❌ Error: {str(e)}")
    
    return {"resultado": resultado}

@app.post("/api/login")
def login(data: dict):
    if data.get("clave", "") == CLAVE_ACCESO:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

# ==================== SEDES Y CUATRIMESTRES ====================

@app.get("/api/sedes")
def get_sedes(db: Session = Depends(get_db)):
    return [{"id": s.id, "nombre": s.nombre, "color": s.color} for s in db.query(Sede).all()]

@app.get("/api/cuatrimestres")
def get_cuatrimestres(db: Session = Depends(get_db)):
    return [{"id": c.id, "nombre": c.nombre, "anio": c.anio, "numero": c.numero, "activo": c.activo}
            for c in db.query(Cuatrimestre).all()]

# ==================== CÁTEDRAS ====================

@app.get("/api/catedras")
def get_catedras(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    catedras = db.query(Catedra).order_by(Catedra.codigo).all()
    result = []
    for cat in catedras:
        try:
            asigs = []
            try:
                all_asigs = cat.asignaciones or []
                if cuatrimestre_id:
                    all_asigs = [a for a in all_asigs if a.cuatrimestre_id == cuatrimestre_id]
                for a in all_asigs:
                    asigs.append({
                        "id": a.id, "modalidad": a.modalidad, "dia": a.dia,
                        "hora_inicio": a.hora_inicio, "hora_fin": a.hora_fin,
                        "sede_id": a.sede_id,
                        "sede_nombre": a.sede.nombre if a.sede else None,
                        "recibe_alumnos_presenciales": getattr(a, 'recibe_alumnos_presenciales', False),
                        "docente": {"id": a.docente.id, "nombre": f"{a.docente.nombre} {a.docente.apellido}"} if a.docente else None,
                    })
            except Exception:
                pass
            
            inscriptos = 0
            try:
                inscrip = cat.inscripciones or []
                if cuatrimestre_id:
                    inscrip = [i for i in inscrip if i.cuatrimestre_id == cuatrimestre_id]
                inscriptos = len(inscrip)
            except Exception:
                pass
            
            cursos_vinc = []
            try:
                for cc in (cat.cursos or []):
                    cursos_vinc.append({
                        "id": cc.id, "curso_id": cc.curso_id,
                        "curso_nombre": cc.curso.nombre if cc.curso else None,
                        "turno": cc.turno,
                        "sede_nombre": cc.sede.nombre if cc.sede else None,
                    })
            except Exception:
                pass
            
            result.append({
                "id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "link_meet": getattr(cat, 'link_meet', None),
                "inscriptos": inscriptos,
                "cursos_vinculados": cursos_vinc,
                "asignaciones": asigs,
            })
        except Exception:
            result.append({
                "id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "link_meet": None, "inscriptos": 0,
                "cursos_vinculados": [], "asignaciones": [],
            })
    return result

@app.get("/api/catedras/stats")
def get_catedras_stats(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    total = db.query(Catedra).count()
    q = db.query(Asignacion)
    if cuatrimestre_id:
        q = q.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    asigs = q.all()
    return {
        "total_catedras": total,
        "total_asignaciones": len(asigs),
        "asincronicas": len([a for a in asigs if a.modalidad == 'asincronica']),
        "con_docente": len([a for a in asigs if a.docente_id and a.modalidad != 'asincronica']),
        "sin_docente": len([a for a in asigs if not a.docente_id and a.modalidad != 'asincronica']),
    }

@app.put("/api/catedras/{catedra_id}")
def actualizar_catedra(catedra_id: int, data: dict, db: Session = Depends(get_db)):
    cat = db.query(Catedra).filter(Catedra.id == catedra_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Cátedra no encontrada")
    if "nombre" in data:
        cat.nombre = data["nombre"]
    if "link_meet" in data:
        cat.link_meet = data["link_meet"]
    db.commit()
    return {"ok": True}

# ==================== ASIGNACIONES ====================

@app.post("/api/asignaciones")
def crear_asignacion(data: dict, db: Session = Depends(get_db)):
    cat_id = data.get("catedra_id")
    cuat_id = data.get("cuatrimestre_id", 1)
    modalidad = data.get("modalidad", "virtual_tm")
    dia = data.get("dia")
    hora = data.get("hora_inicio")
    sede_id = data.get("sede_id")
    
    if dia and hora and modalidad != 'asincronica':
        conflict = verificar_solapamiento_catedra(cat_id, dia, hora, cuat_id, None, db)
        if conflict:
            raise HTTPException(status_code=400, detail=conflict)
    
    asig = Asignacion(
        catedra_id=cat_id, cuatrimestre_id=cuat_id,
        docente_id=data.get("docente_id"), modalidad=modalidad,
        dia=dia, hora_inicio=hora, hora_fin=data.get("hora_fin"),
        sede_id=sede_id if sede_id else None,
        recibe_alumnos_presenciales=data.get("recibe_alumnos_presenciales", False),
    )
    db.add(asig)
    db.commit()
    return {"id": asig.id, "ok": True}

@app.put("/api/asignaciones/{asignacion_id}")
def actualizar_asignacion(asignacion_id: int, data: dict, db: Session = Depends(get_db)):
    asig = db.query(Asignacion).filter(Asignacion.id == asignacion_id).first()
    if not asig:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    
    dia = data.get("dia", asig.dia)
    hora = data.get("hora_inicio", asig.hora_inicio)
    
    if dia and hora and data.get("modalidad", asig.modalidad) != 'asincronica':
        conflict = verificar_solapamiento_catedra(
            asig.catedra_id, dia, hora, asig.cuatrimestre_id, asig.id, db)
        if conflict:
            raise HTTPException(status_code=400, detail=conflict)
    
    for field in ["docente_id", "modalidad", "dia", "hora_inicio", "hora_fin",
                   "sede_id", "recibe_alumnos_presenciales"]:
        if field in data:
            setattr(asig, field, data[field] if data[field] else None)
    asig.modificada = True
    db.commit()
    return {"ok": True}

@app.delete("/api/asignaciones/{asignacion_id}")
def eliminar_asignacion(asignacion_id: int, db: Session = Depends(get_db)):
    asig = db.query(Asignacion).filter(Asignacion.id == asignacion_id).first()
    if not asig:
        raise HTTPException(status_code=404, detail="No encontrada")
    db.delete(asig)
    db.commit()
    return {"ok": True}

# ==================== DOCENTES ====================

def calcular_tipo_modalidad(docente: Docente, db: Session) -> str:
    asigs = db.query(Asignacion).filter(Asignacion.docente_id == docente.id).all()
    if not asigs:
        return "SIN_ASIGNACIONES"
    tiene_presencial = any(a.recibe_alumnos_presenciales for a in asigs)
    tiene_sede = any(a.sede_id for a in asigs)
    if tiene_presencial:
        return "PRESENCIAL_VIRTUAL"
    elif tiene_sede:
        return "SEDE_VIRTUAL"
    else:
        return "REMOTO"

@app.get("/api/docentes")
def get_docentes(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    docentes = db.query(Docente).order_by(Docente.apellido).all()
    result = []
    for d in docentes:
        try:
            asigs_data = []
            sedes_data = []
            tipo = "SIN_ASIGNACIONES"
            
            try:
                all_asigs = d.asignaciones or []
                if cuatrimestre_id:
                    all_asigs = [a for a in all_asigs if a.cuatrimestre_id == cuatrimestre_id]
                for a in all_asigs:
                    asigs_data.append({
                        "id": a.id, "modalidad": a.modalidad, "dia": a.dia,
                        "hora_inicio": a.hora_inicio,
                        "catedra_codigo": a.catedra.codigo if a.catedra else None,
                        "catedra_nombre": a.catedra.nombre if a.catedra else None,
                        "sede_nombre": a.sede.nombre if a.sede else None,
                        "recibe_alumnos_presenciales": getattr(a, 'recibe_alumnos_presenciales', False),
                    })
                tipo = calcular_tipo_modalidad(d, db)
            except Exception:
                pass
            
            try:
                sedes_data = [{"id": ds.sede.id, "nombre": ds.sede.nombre} for ds in (d.sedes or []) if ds.sede]
            except Exception:
                pass
            
            result.append({
                "id": d.id, "dni": d.dni, "nombre": d.nombre, "apellido": d.apellido,
                "email": d.email, "tipo_modalidad": tipo,
                "sedes": sedes_data, "asignaciones": asigs_data,
            })
        except Exception:
            result.append({
                "id": d.id, "dni": d.dni, "nombre": d.nombre, "apellido": d.apellido,
                "email": d.email, "tipo_modalidad": "SIN_ASIGNACIONES",
                "sedes": [], "asignaciones": [],
            })
    return result

@app.post("/api/docentes")
def crear_docente(data: dict, db: Session = Depends(get_db)):
    dni = data.get("dni", "").strip()
    if not dni or len(dni) < 7:
        raise HTTPException(status_code=400, detail="DNI inválido")
    if db.query(Docente).filter(Docente.dni == dni).first():
        raise HTTPException(status_code=400, detail="DNI ya existe")
    d = Docente(dni=dni, nombre=data.get("nombre", ""), apellido=data.get("apellido", ""),
                email=data.get("email"))
    db.add(d)
    db.commit()
    return {"id": d.id, "ok": True}

@app.put("/api/docentes/{docente_id}")
def actualizar_docente(docente_id: int, data: dict, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == docente_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Docente no encontrado")
    for field in ["nombre", "apellido", "email", "dni"]:
        if field in data and data[field]:
            setattr(d, field, data[field])
    db.commit()
    return {"ok": True}

@app.delete("/api/docentes/{docente_id}")
def eliminar_docente(docente_id: int, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == docente_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="No encontrado")
    db.query(Asignacion).filter(Asignacion.docente_id == docente_id).update({"docente_id": None})
    db.delete(d)
    db.commit()
    return {"ok": True}

@app.put("/api/docentes/{docente_id}/sedes")
def actualizar_sedes_docente(docente_id: int, data: dict, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == docente_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="No encontrado")
    db.query(DocenteSede).filter(DocenteSede.docente_id == docente_id).delete()
    for sid in data.get("sede_ids", []):
        db.add(DocenteSede(docente_id=docente_id, sede_id=sid))
    db.commit()
    return {"ok": True}

# ==================== CURSOS ====================

@app.get("/api/cursos")
def get_cursos(sede_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Curso)
    if sede_id:
        q = q.filter(Curso.sede_id == sede_id)
    cursos = q.order_by(Curso.nombre).all()
    return [{
        "id": c.id, "nombre": c.nombre,
        "sede_id": c.sede_id, "sede_nombre": c.sede.nombre if c.sede else None,
        "cant_catedras": len(c.catedras) if c.catedras else 0,
    } for c in cursos]

# ==================== IMPORTADORES ====================

@app.post("/api/importar/catedras")
async def importar_catedras(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = None
        for name in wb.sheetnames:
            if "catedr" in name.lower() or "cátedr" in name.lower():
                ws = wb[name]; break
        if ws is None:
            ws = wb[wb.sheetnames[0]]
        
        creadas = 0
        actualizadas = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            vals = [str(c).strip() if c is not None else "" for c in row]
            codigo = nombre = None
            
            if len(vals) >= 2 and vals[1]:
                m = re.match(r'^(c\.\d+)\s+(.+)', vals[1], re.IGNORECASE)
                if m:
                    codigo, nombre = m.group(1), m.group(2).strip()
            
            if not codigo and len(vals) >= 2:
                try:
                    num = int(float(vals[0]))
                    if num > 0 and vals[1]:
                        m = re.match(r'^(c\.\d+)\s+(.+)', vals[1], re.IGNORECASE)
                        if m:
                            codigo, nombre = m.group(1), m.group(2).strip()
                        else:
                            codigo, nombre = f"c.{num}", vals[1]
                except (ValueError, TypeError):
                    pass
            
            if codigo:
                ex = db.query(Catedra).filter(Catedra.codigo == codigo).first()
                if ex:
                    if nombre and nombre != ex.nombre:
                        ex.nombre = nombre; actualizadas += 1
                else:
                    db.add(Catedra(codigo=codigo, nombre=nombre or f"Cátedra {codigo}"))
                    creadas += 1
        
        db.commit(); wb.close()
        return {"creadas": creadas, "actualizadas": actualizadas}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.post("/api/importar/cursos")
async def importar_cursos(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        creados = 0
        omitidos = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            vals = [str(c).strip() if c is not None else "" for c in row]
            sede_texto = vals[0] if len(vals) > 0 else ""
            nombre = vals[1] if len(vals) > 1 else ""
            if not nombre or len(nombre) < 3: continue
            if any(x in nombre.lower() for x in ['no disponible', '//bajas//', 'test ']): 
                omitidos += 1; continue
            sede = None
            if sede_texto:
                sede = db.query(Sede).filter(Sede.nombre == sede_texto).first()
                if not sede and len(sede_texto) > 2:
                    sede = Sede(nombre=sede_texto, color="bg-gray-500")
                    db.add(sede); db.flush()
            if not db.query(Curso).filter(Curso.nombre == nombre).first():
                db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None))
                creados += 1
        db.commit(); wb.close()
        return {"creados": creados, "omitidos": omitidos}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.post("/api/importar/docentes")
async def importar_docentes(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        
        headers = [str(c.value).lower().strip() if c.value else "" for c in ws[1]]
        col_map = {"dni": -1, "nombre": -1, "apellido": -1, "email": -1}
        for i, h in enumerate(headers):
            if any(x in h for x in ["dni", "documento"]):
                col_map["dni"] = i
            elif h in ["nombre", "nombres"]:
                col_map["nombre"] = i
            elif "apellido" in h:
                col_map["apellido"] = i
            elif any(x in h for x in ["mail", "email", "correo"]):
                col_map["email"] = i
        
        # Formato "APELLIDO y NOMBRE" en una columna
        es_formato_combinado = any("apellido y nombre" in h or "apellido, nombre" in h for h in headers)
        
        creados = 0
        actualizados = 0
        errores = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            
            if es_formato_combinado:
                # DNI en col 0, "APELLIDO, NOMBRE" en col 1
                dni_raw = vals[0] if len(vals) > 0 else ""
                nombre_completo = vals[1] if len(vals) > 1 else ""
                email = vals[2] if len(vals) > 2 else None
                
                dni = dni_raw.replace(".", "").replace("-", "").replace(" ", "")
                if dni.endswith(".0"): dni = dni[:-2]
                
                parts = nombre_completo.split(",", 1)
                apellido = parts[0].strip().title()
                nombre = parts[1].strip().title() if len(parts) > 1 else ""
            else:
                def get_val(key):
                    idx = col_map.get(key, -1)
                    return vals[idx] if 0 <= idx < len(vals) and vals[idx] else None
                dni = get_val("dni") or (vals[0] if vals else "")
                dni = dni.replace(".", "").replace("-", "").replace(" ", "")
                if dni.endswith(".0"): dni = dni[:-2]
                nombre = get_val("nombre") or ""
                apellido = get_val("apellido") or ""
                email = get_val("email")
            
            if not dni or len(dni) < 7: continue
            
            ex = db.query(Docente).filter(Docente.dni == dni).first()
            if ex:
                if nombre: ex.nombre = nombre
                if apellido: ex.apellido = apellido
                if email: ex.email = email
                actualizados += 1
            else:
                if not nombre and not apellido:
                    errores.append(f"Fila {row_num}: DNI {dni} sin nombre"); continue
                db.add(Docente(dni=dni, nombre=nombre, apellido=apellido, email=email))
                creados += 1
        
        db.commit(); wb.close()
        return {"creados": creados, "actualizados": actualizados, "errores": errores[:10]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

# ==================== IMPORTADOR CÁTEDRA-CURSO (FUTURO) ====================

@app.post("/api/importar/catedra-cursos")
async def importar_catedra_cursos(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Importar relaciones cátedra-curso desde Excel.
    Formato esperado: Codigo | Materia (c.XX Nombre - Turno) | Curso | Sede
    """
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        
        creados = 0
        errores = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if len(vals) < 3: continue
            
            # Parsear código de cátedra
            codigo_num = vals[0]
            materia_texto = vals[1]  # "c.1 Administración - Mañana"
            curso_nombre = vals[2]
            sede_nombre = vals[3] if len(vals) > 3 else ""
            
            # Extraer código y turno de la materia
            m = re.match(r'^(c\.\d+)\s+(.+?)(?:\s*-\s*(Mañana|Noche|Virtual|Tarde))?\s*$', materia_texto, re.IGNORECASE)
            if m:
                codigo = m.group(1)
                turno = m.group(3)
            else:
                codigo = f"c.{codigo_num}" if codigo_num else None
                turno = None
            
            if not codigo or not curso_nombre: continue
            
            # Buscar cátedra
            catedra = db.query(Catedra).filter(Catedra.codigo == codigo).first()
            if not catedra:
                errores.append(f"Fila {row_num}: Cátedra {codigo} no existe")
                continue
            
            # Buscar curso (o crear)
            curso = db.query(Curso).filter(Curso.nombre == curso_nombre).first()
            if not curso:
                sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
                curso = Curso(nombre=curso_nombre, sede_id=sede.id if sede else None)
                db.add(curso); db.flush()
            
            # Buscar sede
            sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
            
            # Evitar duplicados
            existe = db.query(CatedraCurso).filter(
                CatedraCurso.catedra_id == catedra.id,
                CatedraCurso.curso_id == curso.id,
                CatedraCurso.turno == turno
            ).first()
            
            if not existe:
                db.add(CatedraCurso(
                    catedra_id=catedra.id, curso_id=curso.id,
                    turno=turno, sede_id=sede.id if sede else None
                ))
                creados += 1
        
        db.commit(); wb.close()
        return {"creados": creados, "errores": errores[:20]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

# ==================== IMPORTADOR LINKS MEET (FUTURO) ====================

@app.post("/api/importar/links-meet")
async def importar_links_meet(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Importar links de Google Meet por cátedra.
    Formato: Código (c.XX) | Link Meet
    """
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        
        actualizados = 0
        errores = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if len(vals) < 2: continue
            
            # Buscar código y link
            codigo = None
            link = None
            for v in vals:
                if re.match(r'^c\.\d+', v, re.IGNORECASE):
                    codigo = v
                elif 'meet.google.com' in v or 'http' in v:
                    link = v
            
            if not codigo or not link: continue
            
            cat = db.query(Catedra).filter(Catedra.codigo == codigo).first()
            if cat:
                cat.link_meet = link
                actualizados += 1
            else:
                errores.append(f"Fila {row_num}: Cátedra {codigo} no existe")
        
        db.commit(); wb.close()
        return {"actualizados": actualizados, "errores": errores[:10]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

# ==================== SOLAPAMIENTOS ====================

def verificar_solapamiento_catedra(catedra_id, dia, hora_inicio, cuatrimestre_id, excluir_id, db):
    q = db.query(Asignacion).filter(
        Asignacion.catedra_id == catedra_id,
        Asignacion.dia == dia,
        Asignacion.hora_inicio == hora_inicio,
        Asignacion.cuatrimestre_id == cuatrimestre_id,
        Asignacion.modalidad != 'asincronica',
    )
    if excluir_id:
        q = q.filter(Asignacion.id != excluir_id)
    conflicto = q.first()
    if conflicto:
        return f"⛔ La cátedra ya tiene clase el {dia} a las {hora_inicio}. Comparten link de Meet."
    return None

@app.get("/api/horarios/solapamientos")
def get_solapamientos(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Asignacion).filter(
        Asignacion.dia.isnot(None), Asignacion.hora_inicio.isnot(None),
        Asignacion.modalidad != 'asincronica'
    )
    if cuatrimestre_id:
        q = q.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    asigs = q.all()
    
    solapamientos = []
    checked = set()
    
    for i, a1 in enumerate(asigs):
        for a2 in asigs[i+1:]:
            if a1.dia != a2.dia or a1.hora_inicio != a2.hora_inicio:
                continue
            pair = tuple(sorted([a1.id, a2.id]))
            if pair in checked:
                continue
            checked.add(pair)
            
            cat1 = a1.catedra
            cat2 = a2.catedra
            
            if a1.catedra_id == a2.catedra_id:
                solapamientos.append({
                    "tipo": "CATEDRA", "severidad": "CRITICO",
                    "mensaje": f"Cátedra {cat1.codigo} tiene dos clases {a1.dia} {a1.hora_inicio}. Comparten link Meet.",
                    "catedra": cat1.codigo, "dia": a1.dia, "hora": a1.hora_inicio,
                })
            elif a1.docente_id and a1.docente_id == a2.docente_id:
                doc = a1.docente
                solapamientos.append({
                    "tipo": "DOCENTE", "severidad": "ALTO",
                    "mensaje": f"{doc.nombre} {doc.apellido} tiene {cat1.codigo} y {cat2.codigo} el {a1.dia} {a1.hora_inicio}.",
                    "docente": f"{doc.nombre} {doc.apellido}", "dia": a1.dia, "hora": a1.hora_inicio,
                })
    
    return solapamientos

# ==================== ESTADÍSTICAS ====================

@app.get("/api/docentes/estadisticas")
def get_estadisticas_docentes(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    docentes = db.query(Docente).all()
    stats = {"presencial_virtual": 0, "sede_virtual": 0, "remoto": 0, "sin_asignaciones": 0}
    for d in docentes:
        tipo = calcular_tipo_modalidad(d, db)
        if tipo == "PRESENCIAL_VIRTUAL": stats["presencial_virtual"] += 1
        elif tipo == "SEDE_VIRTUAL": stats["sede_virtual"] += 1
        elif tipo == "REMOTO": stats["remoto"] += 1
        else: stats["sin_asignaciones"] += 1
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
