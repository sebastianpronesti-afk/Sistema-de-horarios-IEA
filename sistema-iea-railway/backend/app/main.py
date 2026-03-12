from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema Horarios IEA", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== HELPERS ====================

def sort_key_codigo(codigo):
    m = re.match(r'c\.(\d+)', codigo or '', re.IGNORECASE)
    return int(m.group(1)) if m else 9999

SEDES_NORMALIZADAS = {
    'avellaneda': 'Avellaneda',
    'caballito': 'Caballito',
    'vicente lopez': 'Vicente López',
    'vicente lópez': 'Vicente López',
    'online interior': 'Online - Interior',
    'online - interior': 'Online - Interior',
    'online- interior': 'Online - Interior',
    'online': 'Online - Interior',
    'liniers': 'Liniers',
}

def normalizar_sede(texto):
    if not texto:
        return None
    t = texto.strip().lower()
    return SEDES_NORMALIZADAS.get(t, texto.strip())

def clasificar_alumno_curso(curso_texto):
    """
    Clasifica un alumno según su CURSO:
    - es_cied: True si dice CIED o es Online/Interior
    - sede_referencia: sede normalizada extraída del paréntesis
    - modalidad_alumno: 'virtual' si CIED/Online, 'presencial' si no
    """
    if not curso_texto:
        return 'virtual', None, True
    curso = curso_texto.strip()
    es_cied = 'CIED' in curso.upper()
    # Extraer sede del paréntesis
    m_sede = re.search(r'\(([^)]+)\)', curso)
    sede_raw = m_sede.group(1).strip() if m_sede else None
    sede = normalizar_sede(sede_raw) if sede_raw else None
    # Online-Interior siempre es virtual (igual que CIED)
    es_online = sede in ['Online - Interior'] if sede else False
    if es_cied or es_online:
        modalidad = 'virtual'
    else:
        modalidad = 'presencial'
    return modalidad, sede, es_cied

def extraer_turno_materia(materia_texto):
    """Extrae el turno de la columna MATERIA: Mañana, Noche, Virtual"""
    if not materia_texto:
        return None
    m = re.search(r'-\s*(Mañana|Noche|Virtual|Tarde)', materia_texto, re.IGNORECASE)
    return m.group(1).capitalize() if m else None


# ==================== MIGRACIÓN ====================

def run_migration(db):
    from sqlalchemy import text, inspect
    resultado = []
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        resultado.append(f"Tablas: {tables}")
        Base.metadata.create_all(bind=engine)
        resultado.append("✅ create_all")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        # --- Migrar catedras ---
        if 'catedras' in tables:
            cols = [c['name'] for c in inspector.get_columns('catedras')]
            if 'link_meet' not in cols:
                db.execute(text("ALTER TABLE catedras ADD COLUMN link_meet VARCHAR"))
                db.commit()
                resultado.append("✅ catedras.link_meet")
        # --- Migrar asignaciones ---
        if 'asignaciones' in tables:
            cols = [c['name'] for c in inspector.get_columns('asignaciones')]
            if 'hora' in cols and 'hora_inicio' not in cols:
                try:
                    db.execute(text("ALTER TABLE asignaciones RENAME COLUMN hora TO hora_inicio"))
                    db.commit()
                except Exception as e:
                    db.rollback()
            cols = [c['name'] for c in inspector.get_columns('asignaciones')]
            for col, tipo in [
                ('hora_inicio', 'VARCHAR'), ('hora_fin', 'VARCHAR'),
                ('modalidad', "VARCHAR DEFAULT 'virtual_tm'"),
                ('sede_id', 'INTEGER REFERENCES sedes(id)'),
                ('recibe_alumnos_presenciales', 'BOOLEAN DEFAULT FALSE'),
                ('modificada', 'BOOLEAN DEFAULT FALSE'),
            ]:
                if col not in cols:
                    try:
                        db.execute(text(f"ALTER TABLE asignaciones ADD COLUMN {col} {tipo}"))
                        db.commit()
                        resultado.append(f"✅ asignaciones.{col}")
                    except Exception as e:
                        db.rollback()
        # --- Migrar inscripciones (v5.0) ---
        if 'inscripciones' in tables:
            cols = [c['name'] for c in inspector.get_columns('inscripciones')]
            for col, tipo in [
                ('turno', 'VARCHAR'),
                ('modalidad_alumno', 'VARCHAR'),
                ('sede_referencia', 'VARCHAR'),
                ('curso_nombre', 'VARCHAR'),
            ]:
                if col not in cols:
                    try:
                        db.execute(text(f"ALTER TABLE inscripciones ADD COLUMN {col} {tipo}"))
                        db.commit()
                        resultado.append(f"✅ inscripciones.{col}")
                    except Exception as e:
                        db.rollback()
        # --- Migrar docentes (v5.0: horas) ---
        if 'docentes' in tables:
            cols = [c['name'] for c in inspector.get_columns('docentes')]
            if 'horas_asignadas' not in cols:
                try:
                    db.execute(text("ALTER TABLE docentes ADD COLUMN horas_asignadas INTEGER DEFAULT 0"))
                    db.commit()
                    resultado.append("✅ docentes.horas_asignadas")
                except Exception as e:
                    db.rollback()
        # --- Crear tabla docente_disponibilidad (v5.0) ---
        if 'docente_disponibilidad' not in tables:
            try:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS docente_disponibilidad (
                        id SERIAL PRIMARY KEY,
                        docente_id INTEGER REFERENCES docentes(id) ON DELETE CASCADE,
                        dia VARCHAR NOT NULL,
                        hora VARCHAR NOT NULL,
                        disponible BOOLEAN DEFAULT TRUE
                    )
                """))
                db.commit()
                resultado.append("✅ Tabla docente_disponibilidad creada")
            except Exception as e:
                db.rollback()
        # --- Crear tablas auxiliares ---
        for tbl, ddl in [
            ('docente_sede', """CREATE TABLE IF NOT EXISTS docente_sede (
                id SERIAL PRIMARY KEY, docente_id INTEGER REFERENCES docentes(id) ON DELETE CASCADE,
                sede_id INTEGER REFERENCES sedes(id) ON DELETE CASCADE)"""),
            ('catedra_curso', """CREATE TABLE IF NOT EXISTS catedra_curso (
                id SERIAL PRIMARY KEY, catedra_id INTEGER REFERENCES catedras(id) ON DELETE CASCADE,
                curso_id INTEGER REFERENCES cursos(id) ON DELETE CASCADE, turno VARCHAR,
                sede_id INTEGER REFERENCES sedes(id))"""),
        ]:
            if tbl not in tables:
                try:
                    db.execute(text(ddl))
                    db.commit()
                    resultado.append(f"✅ Tabla {tbl}")
                except Exception as e:
                    db.rollback()
        # --- Limpiar sedes duplicadas ---
        try:
            sede_sin = db.query(Sede).filter(Sede.nombre == "Vicente Lopez").first()
            sede_con = db.query(Sede).filter(Sede.nombre == "Vicente López").first()
            if sede_sin and sede_con:
                for tbl in ['cursos', 'asignaciones']:
                    db.execute(text(f"UPDATE {tbl} SET sede_id = {sede_con.id} WHERE sede_id = {sede_sin.id}"))
                db.execute(text(f"DELETE FROM docente_sede WHERE sede_id = {sede_sin.id} AND docente_id IN (SELECT docente_id FROM docente_sede WHERE sede_id = {sede_con.id})"))
                db.execute(text(f"UPDATE docente_sede SET sede_id = {sede_con.id} WHERE sede_id = {sede_sin.id}"))
                if 'catedra_curso' in tables:
                    db.execute(text(f"UPDATE catedra_curso SET sede_id = {sede_con.id} WHERE sede_id = {sede_sin.id}"))
                db.execute(text(f"DELETE FROM sedes WHERE id = {sede_sin.id}"))
                db.commit()
            elif sede_sin and not sede_con:
                sede_sin.nombre = "Vicente López"
                db.commit()
        except Exception as e:
            db.rollback()
    except Exception as e:
        resultado.append(f"❌ {e}")
    return resultado


@app.on_event("startup")
async def startup():
    db = next(get_db())
    migr = run_migration(db)
    for m in migr:
        print(f"  [MIG] {m}")
    try:
        from app.seed_data import SEDES, CATEDRAS, CURSOS, DOCENTES
        for nombre, color in SEDES:
            if not db.query(Sede).filter(Sede.nombre == nombre).first():
                db.add(Sede(nombre=nombre, color=color))
        db.commit()
        if not db.query(Cuatrimestre).first():
            for anio in range(2026, 2031):
                db.add(Cuatrimestre(nombre=f"1er Cuatrimestre {anio}", anio=anio, numero=1, activo=(anio == 2026)))
                db.add(Cuatrimestre(nombre=f"2do Cuatrimestre {anio}", anio=anio, numero=2, activo=False))
            db.commit()
        else:
            for anio in range(2026, 2031):
                for num in [1, 2]:
                    nombre_c = f"{'1er' if num == 1 else '2do'} Cuatrimestre {anio}"
                    if not db.query(Cuatrimestre).filter(Cuatrimestre.anio == anio, Cuatrimestre.numero == num).first():
                        db.add(Cuatrimestre(nombre=nombre_c, anio=anio, numero=num, activo=False))
            db.commit()
        if db.query(Catedra).count() == 0:
            for codigo, nombre in CATEDRAS:
                db.add(Catedra(codigo=codigo, nombre=nombre))
            db.commit()
        if db.query(Curso).count() == 0:
            for sede_nombre, nombre in CURSOS:
                sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first()
                db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None))
            db.commit()
        if db.query(Docente).count() == 0:
            for dni, nombre, apellido in DOCENTES:
                db.add(Docente(dni=dni, nombre=nombre, apellido=apellido))
            db.commit()
    except ImportError:
        pass
    except Exception as e:
        print(f"  ⚠️ Seed: {e}")
    db.close()
    print("🚀 IEA Horarios v5.0 iniciado")

CLAVE_ACCESO = "IEA2026"

@app.get("/")
def root():
    return {"status": "ok", "sistema": "IEA Horarios v5.0"}

@app.get("/api/reparar")
def reparar_bd(db: Session = Depends(get_db)):
    resultado = run_migration(db)
    try:
        from app.seed_data import SEDES, CATEDRAS, CURSOS, DOCENTES
        for nombre, color in SEDES:
            if not db.query(Sede).filter(Sede.nombre == nombre).first():
                db.add(Sede(nombre=nombre, color=color))
        db.commit()
        for anio in range(2026, 2031):
            for num in [1, 2]:
                nombre_c = f"{'1er' if num == 1 else '2do'} Cuatrimestre {anio}"
                if not db.query(Cuatrimestre).filter(Cuatrimestre.anio == anio, Cuatrimestre.numero == num).first():
                    db.add(Cuatrimestre(nombre=nombre_c, anio=anio, numero=num, activo=False))
        db.commit()
    except Exception as e:
        resultado.append(f"⚠️ {e}")
    return {"resultado": resultado}

@app.get("/api/diagnostico")
def diagnostico_bd(db: Session = Depends(get_db)):
    from sqlalchemy import text, inspect
    info = {}
    try:
        inspector = inspect(engine)
        for t in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns(t)]
            count = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            info[t] = {"columnas": cols, "registros": count}
    except Exception as e:
        info["error"] = str(e)
    return info

@app.post("/api/login")
def login(data: dict):
    if data.get("clave", "") == CLAVE_ACCESO:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")

@app.get("/api/sedes")
def get_sedes(db: Session = Depends(get_db)):
    return [{"id": s.id, "nombre": s.nombre, "color": s.color} for s in db.query(Sede).all()]

@app.get("/api/cuatrimestres")
def get_cuatrimestres(db: Session = Depends(get_db)):
    return [{"id": c.id, "nombre": c.nombre, "anio": c.anio, "numero": c.numero, "activo": c.activo}
            for c in db.query(Cuatrimestre).order_by(Cuatrimestre.anio, Cuatrimestre.numero).all()]


# ==================== CÁTEDRAS ====================

@app.get("/api/catedras")
def get_catedras(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    from sqlalchemy import text
    catedras = db.query(Catedra).all()
    catedras_sorted = sorted(catedras, key=lambda c: sort_key_codigo(c.codigo))
    # Pre-cargar desglose de inscriptos por cátedra
    desglose_query = """
        SELECT catedra_id,
            COALESCE(modalidad_alumno, 'sin_dato') as mod,
            COALESCE(turno, 'Sin turno') as turno,
            COALESCE(sede_referencia, 'Sin sede') as sede,
            COUNT(*) as cnt
        FROM inscripciones
    """
    if cuatrimestre_id:
        desglose_query += f" WHERE cuatrimestre_id = {cuatrimestre_id}"
    desglose_query += " GROUP BY catedra_id, modalidad_alumno, turno, sede_referencia"
    try:
        desglose_rows = db.execute(text(desglose_query)).fetchall()
    except Exception:
        desglose_rows = []
    # Organizar desglose por cátedra
    desglose_map = {}
    for row in desglose_rows:
        cat_id = row[0]
        if cat_id not in desglose_map:
            desglose_map[cat_id] = {'total': 0, 'virtual': 0, 'presencial': 0, 'por_turno': {}, 'por_sede': {}}
        d = desglose_map[cat_id]
        cnt = row[4]
        d['total'] += cnt
        mod = row[1]
        if mod == 'virtual':
            d['virtual'] += cnt
        elif mod == 'presencial':
            d['presencial'] += cnt
        turno = row[2]
        d['por_turno'][turno] = d['por_turno'].get(turno, 0) + cnt
        sede = row[3]
        d['por_sede'][sede] = d['por_sede'].get(sede, 0) + cnt
    result = []
    for cat in catedras_sorted:
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
            desg = desglose_map.get(cat.id, {'total': 0, 'virtual': 0, 'presencial': 0, 'por_turno': {}, 'por_sede': {}})
            inscriptos = desg['total']
            docentes_sugeridos = max(1, -(-inscriptos // 100)) if inscriptos > 0 else 0
            cursos_vinc = []
            try:
                for cc in (cat.cursos or []):
                    cursos_vinc.append({"id": cc.id, "curso_id": cc.curso_id, "curso_nombre": cc.curso.nombre if cc.curso else None, "turno": cc.turno, "sede_nombre": cc.sede.nombre if cc.sede else None})
            except Exception:
                pass
            result.append({
                "id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "link_meet": getattr(cat, 'link_meet', None),
                "inscriptos": inscriptos,
                "inscriptos_virtual": desg['virtual'],
                "inscriptos_presencial": desg['presencial'],
                "inscriptos_por_turno": desg['por_turno'],
                "inscriptos_por_sede": desg['por_sede'],
                "docentes_sugeridos": docentes_sugeridos,
                "cursos_vinculados": cursos_vinc,
                "asignaciones": asigs,
            })
        except Exception:
            result.append({"id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "link_meet": None, "inscriptos": 0, "inscriptos_virtual": 0, "inscriptos_presencial": 0,
                "inscriptos_por_turno": {}, "inscriptos_por_sede": {},
                "docentes_sugeridos": 0, "cursos_vinculados": [], "asignaciones": []})
    return result

@app.get("/api/catedras/stats")
def get_catedras_stats(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    from sqlalchemy import text
    total = db.query(Catedra).count()
    q = db.query(Asignacion)
    if cuatrimestre_id:
        q = q.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    asigs = q.all()
    q_insc = db.query(Inscripcion)
    if cuatrimestre_id:
        q_insc = q_insc.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
    total_inscripciones = q_insc.count()
    alumnos_unicos = db.query(func.count(func.distinct(Inscripcion.alumno_id)))
    if cuatrimestre_id:
        alumnos_unicos = alumnos_unicos.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
    alumnos_unicos = alumnos_unicos.scalar() or 0
    materias_con_inscriptos = db.query(func.count(func.distinct(Inscripcion.catedra_id)))
    if cuatrimestre_id:
        materias_con_inscriptos = materias_con_inscriptos.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
    materias_con_inscriptos = materias_con_inscriptos.scalar() or 0
    # Desglose virtual/presencial
    try:
        virt_q = "SELECT COUNT(*) FROM inscripciones WHERE modalidad_alumno = 'virtual'"
        pres_q = "SELECT COUNT(*) FROM inscripciones WHERE modalidad_alumno = 'presencial'"
        if cuatrimestre_id:
            virt_q += f" AND cuatrimestre_id = {cuatrimestre_id}"
            pres_q += f" AND cuatrimestre_id = {cuatrimestre_id}"
        virtuales = db.execute(text(virt_q)).scalar() or 0
        presenciales = db.execute(text(pres_q)).scalar() or 0
    except Exception:
        virtuales = 0
        presenciales = 0
    return {
        "total_catedras": total,
        "catedras_abiertas": len(set(a.catedra_id for a in asigs)),
        "total_asignaciones": len(asigs),
        "con_docente": len([a for a in asigs if a.docente_id and a.modalidad != 'asincronica']),
        "sin_docente": len([a for a in asigs if not a.docente_id and a.modalidad != 'asincronica']),
        "total_inscripciones": total_inscripciones,
        "alumnos_unicos": alumnos_unicos,
        "materias_con_inscriptos": materias_con_inscriptos,
        "inscriptos_virtuales": virtuales,
        "inscriptos_presenciales": presenciales,
    }

@app.put("/api/catedras/{catedra_id}")
def actualizar_catedra(catedra_id: int, data: dict, db: Session = Depends(get_db)):
    cat = db.query(Catedra).filter(Catedra.id == catedra_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="No encontrada")
    if "nombre" in data: cat.nombre = data["nombre"]
    if "link_meet" in data: cat.link_meet = data["link_meet"]
    db.commit()
    return {"ok": True}

@app.get("/api/catedras/necesitan-docente")
def get_catedras_necesitan_docente(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Inscripcion.catedra_id, func.count(Inscripcion.id).label('cnt'))
    if cuatrimestre_id:
        q = q.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
    q = q.group_by(Inscripcion.catedra_id).having(func.count(Inscripcion.id) > 5)
    inscriptos_por_cat = {row.catedra_id: row.cnt for row in q.all()}
    result = []
    for cat_id, cant in inscriptos_por_cat.items():
        cat = db.query(Catedra).filter(Catedra.id == cat_id).first()
        if not cat: continue
        asigs = db.query(Asignacion).filter(Asignacion.catedra_id == cat_id)
        if cuatrimestre_id:
            asigs = asigs.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
        asigs = asigs.all()
        docentes_asignados = [a for a in asigs if a.docente_id]
        docentes_sugeridos = max(1, -(-cant // 100))
        necesita = docentes_sugeridos - len(docentes_asignados)
        if necesita > 0 or len(docentes_asignados) == 0:
            result.append({
                "catedra_id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "inscriptos": cant, "docentes_sugeridos": docentes_sugeridos,
                "docentes_asignados": len(docentes_asignados),
                "docentes_faltantes": max(0, necesita),
                "docentes_nombres": [f"{a.docente.nombre} {a.docente.apellido}" for a in docentes_asignados if a.docente],
            })
    result.sort(key=lambda x: sort_key_codigo(x['codigo']))
    return result


# ==================== ASIGNACIONES ====================

@app.post("/api/asignaciones")
def crear_asignacion(data: dict, db: Session = Depends(get_db)):
    try:
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
            docente_id=data.get("docente_id") if data.get("docente_id") else None,
            modalidad=modalidad,
            dia=dia if dia else None, hora_inicio=hora if hora else None,
            hora_fin=data.get("hora_fin") if data.get("hora_fin") else None,
            sede_id=sede_id if sede_id else None,
            recibe_alumnos_presenciales=data.get("recibe_alumnos_presenciales", False),
        )
        db.add(asig); db.commit()
        return {"id": asig.id, "ok": True}
    except HTTPException: raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.put("/api/asignaciones/{asignacion_id}")
def actualizar_asignacion(asignacion_id: int, data: dict, db: Session = Depends(get_db)):
    try:
        asig = db.query(Asignacion).filter(Asignacion.id == asignacion_id).first()
        if not asig: raise HTTPException(status_code=404, detail="No encontrada")
        dia = data.get("dia", asig.dia)
        hora = data.get("hora_inicio", asig.hora_inicio)
        if dia and hora and data.get("modalidad", asig.modalidad) != 'asincronica':
            conflict = verificar_solapamiento_catedra(asig.catedra_id, dia, hora, asig.cuatrimestre_id, asig.id, db)
            if conflict: raise HTTPException(status_code=400, detail=conflict)
        for field in ["docente_id", "modalidad", "dia", "hora_inicio", "hora_fin", "sede_id", "recibe_alumnos_presenciales"]:
            if field in data:
                val = data[field]
                if field in ["docente_id", "sede_id"] and (val == "" or val == "null" or not val):
                    val = None
                setattr(asig, field, val if val else None)
        asig.modificada = True
        db.commit()
        return {"ok": True}
    except HTTPException: raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.delete("/api/asignaciones/{asignacion_id}")
def eliminar_asignacion(asignacion_id: int, db: Session = Depends(get_db)):
    asig = db.query(Asignacion).filter(Asignacion.id == asignacion_id).first()
    if not asig: raise HTTPException(status_code=404, detail="No encontrada")
    db.delete(asig); db.commit()
    return {"ok": True}


# ==================== DOCENTES ====================

def calcular_tipo_modalidad(docente, db):
    asigs = db.query(Asignacion).filter(Asignacion.docente_id == docente.id).all()
    if not asigs: return "SIN_ASIGNACIONES"
    if any(a.recibe_alumnos_presenciales for a in asigs): return "PRESENCIAL_VIRTUAL"
    if any(a.sede_id for a in asigs): return "SEDE_VIRTUAL"
    return "REMOTO"

@app.get("/api/docentes")
def get_docentes(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    docentes = db.query(Docente).order_by(Docente.apellido).all()
    result = []
    for d in docentes:
        try:
            asigs_data = []
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
            sedes_data = [{"id": ds.sede.id, "nombre": ds.sede.nombre} for ds in (d.sedes or []) if ds.sede]
            tipo = calcular_tipo_modalidad(d, db)
            horas = getattr(d, 'horas_asignadas', 0) or 0
            result.append({
                "id": d.id, "dni": d.dni, "nombre": d.nombre, "apellido": d.apellido,
                "email": d.email, "tipo_modalidad": tipo,
                "horas_asignadas": horas,
                "sedes": sedes_data, "asignaciones": asigs_data,
            })
        except Exception:
            result.append({"id": d.id, "dni": d.dni, "nombre": d.nombre, "apellido": d.apellido,
                "email": d.email, "tipo_modalidad": "SIN_ASIGNACIONES",
                "horas_asignadas": 0, "sedes": [], "asignaciones": []})
    return result

@app.post("/api/docentes")
def crear_docente(data: dict, db: Session = Depends(get_db)):
    dni = data.get("dni", "").strip()
    if not dni or len(dni) < 7: raise HTTPException(status_code=400, detail="DNI inválido")
    if db.query(Docente).filter(Docente.dni == dni).first():
        raise HTTPException(status_code=400, detail="DNI ya existe")
    d = Docente(dni=dni, nombre=data.get("nombre", ""), apellido=data.get("apellido", ""), email=data.get("email"))
    db.add(d); db.commit()
    return {"id": d.id, "ok": True}

@app.put("/api/docentes/{docente_id}")
def actualizar_docente(docente_id: int, data: dict, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == docente_id).first()
    if not d: raise HTTPException(status_code=404, detail="No encontrado")
    for field in ["nombre", "apellido", "email", "dni"]:
        if field in data and data[field]:
            setattr(d, field, data[field])
    # v5.0: horas asignadas
    if "horas_asignadas" in data:
        try:
            from sqlalchemy import text
            db.execute(text(f"UPDATE docentes SET horas_asignadas = {int(data['horas_asignadas'])} WHERE id = {docente_id}"))
        except Exception:
            pass
    db.commit()
    return {"ok": True}

@app.delete("/api/docentes/{docente_id}")
def eliminar_docente(docente_id: int, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == docente_id).first()
    if not d: raise HTTPException(status_code=404, detail="No encontrado")
    db.query(Asignacion).filter(Asignacion.docente_id == docente_id).update({"docente_id": None})
    db.query(DocenteSede).filter(DocenteSede.docente_id == docente_id).delete()
    from sqlalchemy import text
    try: db.execute(text(f"DELETE FROM docente_disponibilidad WHERE docente_id = {docente_id}"))
    except: pass
    db.delete(d); db.commit()
    return {"ok": True}

@app.put("/api/docentes/{docente_id}/sedes")
def actualizar_sedes_docente(docente_id: int, data: dict, db: Session = Depends(get_db)):
    d = db.query(Docente).filter(Docente.id == docente_id).first()
    if not d: raise HTTPException(status_code=404, detail="No encontrado")
    db.query(DocenteSede).filter(DocenteSede.docente_id == docente_id).delete()
    for sid in data.get("sede_ids", []):
        db.add(DocenteSede(docente_id=docente_id, sede_id=sid))
    db.commit()
    return {"ok": True}

# ===== v5.0: Disponibilidad horaria =====
@app.get("/api/docentes/{docente_id}/disponibilidad")
def get_disponibilidad(docente_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        rows = db.execute(text(f"SELECT dia, hora, disponible FROM docente_disponibilidad WHERE docente_id = {docente_id}")).fetchall()
        return [{"dia": r[0], "hora": r[1], "disponible": r[2]} for r in rows]
    except Exception:
        return []

@app.put("/api/docentes/{docente_id}/disponibilidad")
def set_disponibilidad(docente_id: int, data: dict, db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        db.execute(text(f"DELETE FROM docente_disponibilidad WHERE docente_id = {docente_id}"))
        for item in data.get("disponibilidad", []):
            dia = item.get("dia")
            hora = item.get("hora")
            disponible = item.get("disponible", True)
            if dia and hora:
                db.execute(text(
                    f"INSERT INTO docente_disponibilidad (docente_id, dia, hora, disponible) VALUES ({docente_id}, '{dia}', '{hora}', {disponible})"
                ))
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CURSOS ====================

@app.get("/api/cursos")
def get_cursos(sede_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Curso)
    if sede_id: q = q.filter(Curso.sede_id == sede_id)
    result = []
    for c in q.order_by(Curso.nombre).all():
        catedras_vinc = []
        try:
            for cc in (c.catedras or []):
                catedras_vinc.append({"id": cc.id, "catedra_id": cc.catedra_id, "catedra_codigo": cc.catedra.codigo if cc.catedra else None, "catedra_nombre": cc.catedra.nombre if cc.catedra else None, "turno": cc.turno})
        except Exception: pass
        result.append({"id": c.id, "nombre": c.nombre, "sede_id": c.sede_id, "sede_nombre": c.sede.nombre if c.sede else None, "cant_catedras": len(catedras_vinc), "catedras": catedras_vinc})
    return result


# ==================== IMPORTACIONES ====================

@app.post("/api/importar/catedras")
async def importar_catedras(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = None
        for name in wb.sheetnames:
            if "catedr" in name.lower() or "cátedr" in name.lower(): ws = wb[name]; break
        if ws is None: ws = wb[wb.sheetnames[0]]
        creadas = actualizadas = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            vals = [str(c).strip() if c is not None else "" for c in row]
            codigo = nombre = None
            if len(vals) >= 2 and vals[1]:
                m = re.match(r'^(c\.\d+)\s+(.+)', vals[1], re.IGNORECASE)
                if m: codigo, nombre = m.group(1), m.group(2).strip()
            if not codigo and len(vals) >= 2:
                try:
                    num = int(float(vals[0]))
                    if num > 0 and vals[1]:
                        m = re.match(r'^(c\.\d+)\s+(.+)', vals[1], re.IGNORECASE)
                        if m: codigo, nombre = m.group(1), m.group(2).strip()
                        else: codigo, nombre = f"c.{num}", vals[1]
                except: pass
            if codigo:
                ex = db.query(Catedra).filter(Catedra.codigo == codigo).first()
                if ex:
                    if nombre and nombre != ex.nombre: ex.nombre = nombre; actualizadas += 1
                else:
                    db.add(Catedra(codigo=codigo, nombre=nombre or f"Cátedra {codigo}")); creadas += 1
        db.commit(); wb.close()
        return {"creadas": creadas, "actualizadas": actualizadas}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.post("/api/importar/apertura-catedras")
async def importar_apertura_catedras(file: UploadFile = File(...), cuatrimestre_id: int = 1, db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        abiertas = ya_existentes = 0
        errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if not any(vals): continue
            codigo = None
            nombre = None
            for v in vals:
                m = re.match(r'^(c\.\d+)\s*(.*)', v, re.IGNORECASE)
                if m: codigo = m.group(1); nombre = m.group(2).strip() if m.group(2) else None; break
            if not codigo and vals[0]:
                try:
                    num = int(float(vals[0]))
                    if num > 0: codigo = f"c.{num}"; nombre = vals[1] if len(vals) > 1 else None
                except: pass
            if not codigo: continue
            catedra = db.query(Catedra).filter(Catedra.codigo == codigo).first()
            if not catedra:
                if nombre: catedra = Catedra(codigo=codigo, nombre=nombre); db.add(catedra); db.flush()
                else: continue
            if db.query(Asignacion).filter(Asignacion.catedra_id == catedra.id, Asignacion.cuatrimestre_id == cuatrimestre_id).first():
                ya_existentes += 1; continue
            db.add(Asignacion(catedra_id=catedra.id, cuatrimestre_id=cuatrimestre_id, modalidad='virtual_tm'))
            abiertas += 1
        db.commit(); wb.close()
        return {"abiertas": abiertas, "ya_existentes": ya_existentes, "errores": errores[:20]}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.post("/api/importar/cursos")
async def importar_cursos(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        creados = omitidos = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            vals = [str(c).strip() if c is not None else "" for c in row]
            sede_texto = vals[0] if len(vals) > 0 else ""
            nombre = vals[1] if len(vals) > 1 else ""
            if not nombre or len(nombre) < 3: continue
            if any(x in nombre.lower() for x in ['no disponible', '//bajas//', 'test ']): omitidos += 1; continue
            sede = db.query(Sede).filter(Sede.nombre == sede_texto).first() if sede_texto else None
            if not sede and sede_texto and len(sede_texto) > 2:
                sede = Sede(nombre=sede_texto, color="bg-gray-500"); db.add(sede); db.flush()
            if not db.query(Curso).filter(Curso.nombre == nombre).first():
                db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None)); creados += 1
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
            if any(x in h for x in ["dni", "documento"]): col_map["dni"] = i
            elif h in ["nombre", "nombres"]: col_map["nombre"] = i
            elif "apellido" in h: col_map["apellido"] = i
            elif any(x in h for x in ["mail", "email", "correo"]): col_map["email"] = i
        es_combinado = any("apellido y nombre" in h or "apellido, nombre" in h for h in headers)
        creados = actualizados = 0; errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if es_combinado:
                dni = vals[0].replace(".", "").replace("-", "").replace(" ", "") if vals else ""
                if dni.endswith(".0"): dni = dni[:-2]
                parts = (vals[1] if len(vals) > 1 else "").split(",", 1)
                apellido = parts[0].strip().title()
                nombre = parts[1].strip().title() if len(parts) > 1 else ""
                email = vals[2] if len(vals) > 2 else None
            else:
                def gv(k):
                    idx = col_map.get(k, -1)
                    return vals[idx] if 0 <= idx < len(vals) and vals[idx] else None
                dni = (gv("dni") or (vals[0] if vals else "")).replace(".", "").replace("-", "").replace(" ", "")
                if dni.endswith(".0"): dni = dni[:-2]
                nombre = gv("nombre") or ""; apellido = gv("apellido") or ""; email = gv("email")
            if not dni or len(dni) < 7: continue
            ex = db.query(Docente).filter(Docente.dni == dni).first()
            if ex:
                if nombre: ex.nombre = nombre
                if apellido: ex.apellido = apellido
                if email: ex.email = email
                actualizados += 1
            else:
                if not nombre and not apellido: continue
                db.add(Docente(dni=dni, nombre=nombre, apellido=apellido, email=email)); creados += 1
        db.commit(); wb.close()
        return {"creados": creados, "actualizados": actualizados, "errores": errores[:10]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.post("/api/importar/catedra-cursos")
async def importar_catedra_cursos(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        creados = 0; errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if len(vals) < 3: continue
            materia_texto = vals[1]; curso_nombre = vals[2]; sede_nombre = vals[3] if len(vals) > 3 else ""
            m = re.match(r'^(c\.\d+)\s+(.+?)(?:\s*-\s*(Mañana|Noche|Virtual|Tarde))?\s*$', materia_texto, re.IGNORECASE)
            codigo = m.group(1) if m else (f"c.{vals[0]}" if vals[0] else None)
            turno = m.group(3) if m else None
            if not codigo or not curso_nombre: continue
            catedra = db.query(Catedra).filter(Catedra.codigo == codigo).first()
            if not catedra: continue
            curso = db.query(Curso).filter(Curso.nombre == curso_nombre).first()
            if not curso:
                sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
                curso = Curso(nombre=curso_nombre, sede_id=sede.id if sede else None); db.add(curso); db.flush()
            sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
            if not db.query(CatedraCurso).filter(CatedraCurso.catedra_id == catedra.id, CatedraCurso.curso_id == curso.id, CatedraCurso.turno == turno).first():
                db.add(CatedraCurso(catedra_id=catedra.id, curso_id=curso.id, turno=turno, sede_id=sede.id if sede else None)); creados += 1
        db.commit(); wb.close()
        return {"creados": creados, "errores": errores[:20]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.post("/api/importar/links-meet")
async def importar_links_meet(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        actualizados = 0; errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if len(vals) < 2: continue
            codigo = link = None
            for v in vals:
                if re.match(r'^c\.\d+', v, re.IGNORECASE): codigo = v
                elif 'meet.google.com' in v or 'http' in v: link = v
            if not codigo or not link: continue
            cat = db.query(Catedra).filter(Catedra.codigo == codigo).first()
            if cat: cat.link_meet = link; actualizados += 1
        db.commit(); wb.close()
        return {"actualizados": actualizados, "errores": errores[:10]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

# ===== v5.0: Importar alumnos con clasificación sede/turno/modalidad =====
@app.post("/api/importar/alumnos")
async def importar_alumnos(file: UploadFile = File(...), cuatrimestre_id: int = 1, db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        creados = 0; inscripciones = 0; errores = []
        stats = {'virtual': 0, 'presencial': 0, 'turnos': {}, 'sedes': {}}
        for ws in wb:
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                vals = [str(c).strip() if c is not None else "" for c in row]
                if len(vals) < 4: continue
                alumno_texto = vals[1]
                dni_raw = str(vals[2]).strip() if vals[2] else ""
                materia_texto = vals[3]
                curso_texto = vals[4] if len(vals) > 4 else ""
                dni = re.sub(r'[.\-\s]', '', dni_raw)
                if '.' in dni:
                    try: dni = str(int(float(dni)))
                    except: pass
                if not dni or len(dni) < 6: continue
                m_nombre = re.match(r'^(.+?)\s*\(\d+\)', alumno_texto)
                nombre_completo = m_nombre.group(1).strip() if m_nombre else alumno_texto
                partes = nombre_completo.strip().split(' ')
                nombre = ' '.join(partes[:-1]) if len(partes) >= 2 else nombre_completo
                apellido = partes[-1] if len(partes) >= 2 else ""
                m_cod = re.match(r'^(c\.\d+)', materia_texto, re.IGNORECASE)
                if not m_cod: continue
                codigo = m_cod.group(1)
                catedra = db.query(Catedra).filter(Catedra.codigo == codigo).first()
                if not catedra: continue
                # v5.0: Clasificar por curso
                modalidad_alumno, sede_ref, es_cied = clasificar_alumno_curso(curso_texto)
                turno = extraer_turno_materia(materia_texto)
                alumno = db.query(Alumno).filter(Alumno.dni == dni).first()
                if not alumno:
                    alumno = Alumno(dni=dni, nombre=nombre, apellido=apellido)
                    db.add(alumno); db.flush(); creados += 1
                existe = db.query(Inscripcion).filter(
                    Inscripcion.alumno_id == alumno.id,
                    Inscripcion.catedra_id == catedra.id,
                    Inscripcion.cuatrimestre_id == cuatrimestre_id
                ).first()
                if not existe:
                    insc = Inscripcion(alumno_id=alumno.id, catedra_id=catedra.id, cuatrimestre_id=cuatrimestre_id)
                    db.add(insc); db.flush()
                    # Guardar datos extendidos via SQL directo
                    try:
                        db.execute(text(
                            f"UPDATE inscripciones SET turno = :turno, modalidad_alumno = :mod, sede_referencia = :sede, curso_nombre = :curso WHERE id = :id"
                        ), {"turno": turno, "mod": modalidad_alumno, "sede": sede_ref, "curso": curso_texto[:200] if curso_texto else None, "id": insc.id})
                    except Exception:
                        pass
                    inscripciones += 1
                    stats[modalidad_alumno] = stats.get(modalidad_alumno, 0) + 1
                    if turno: stats['turnos'][turno] = stats['turnos'].get(turno, 0) + 1
                    if sede_ref: stats['sedes'][sede_ref] = stats['sedes'].get(sede_ref, 0) + 1
                else:
                    # Actualizar datos extendidos si ya existía pero no tenía clasificación
                    try:
                        db.execute(text(
                            f"UPDATE inscripciones SET turno = COALESCE(turno, :turno), modalidad_alumno = COALESCE(modalidad_alumno, :mod), sede_referencia = COALESCE(sede_referencia, :sede), curso_nombre = COALESCE(curso_nombre, :curso) WHERE id = :id"
                        ), {"turno": turno, "mod": modalidad_alumno, "sede": sede_ref, "curso": curso_texto[:200] if curso_texto else None, "id": existe.id})
                    except Exception:
                        pass
        db.commit(); wb.close()
        return {
            "alumnos_nuevos": creados, "inscripciones_cargadas": inscripciones,
            "virtuales": stats.get('virtual', 0), "presenciales": stats.get('presencial', 0),
            "por_turno": stats['turnos'], "por_sede": stats['sedes'],
            "errores": errores[:20]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


# ==================== SOLAPAMIENTOS ====================

def verificar_solapamiento_catedra(catedra_id, dia, hora_inicio, cuatrimestre_id, excluir_id, db):
    q = db.query(Asignacion).filter(Asignacion.catedra_id == catedra_id, Asignacion.dia == dia, Asignacion.hora_inicio == hora_inicio, Asignacion.cuatrimestre_id == cuatrimestre_id, Asignacion.modalidad != 'asincronica')
    if excluir_id: q = q.filter(Asignacion.id != excluir_id)
    if q.first(): return f"⛔ La cátedra ya tiene clase el {dia} a las {hora_inicio}."
    return None

@app.get("/api/horarios/solapamientos")
def get_solapamientos(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    try:
        q = db.query(Asignacion).filter(Asignacion.dia.isnot(None), Asignacion.hora_inicio.isnot(None), Asignacion.modalidad != 'asincronica')
        if cuatrimestre_id: q = q.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
        asigs = q.all()
        solapamientos = []; checked = set()
        for i, a1 in enumerate(asigs):
            for a2 in asigs[i+1:]:
                if a1.dia != a2.dia or a1.hora_inicio != a2.hora_inicio: continue
                pair = tuple(sorted([a1.id, a2.id]))
                if pair in checked: continue
                checked.add(pair)
                cat1 = a1.catedra; cat2 = a2.catedra
                if a1.catedra_id == a2.catedra_id:
                    solapamientos.append({"tipo": "CATEDRA", "severidad": "CRITICO", "mensaje": f"Cátedra {cat1.codigo if cat1 else '?'} tiene dos clases {a1.dia} {a1.hora_inicio}.", "dia": a1.dia, "hora": a1.hora_inicio})
                elif a1.docente_id and a1.docente_id == a2.docente_id:
                    doc = a1.docente
                    solapamientos.append({"tipo": "DOCENTE", "severidad": "ALTO", "mensaje": f"{doc.nombre} {doc.apellido} tiene {cat1.codigo} y {cat2.codigo} el {a1.dia} {a1.hora_inicio}.", "dia": a1.dia, "hora": a1.hora_inicio})
        return solapamientos
    except Exception: return []

@app.get("/api/docentes/estadisticas")
def get_estadisticas_docentes(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    stats = {"presencial_virtual": 0, "sede_virtual": 0, "remoto": 0, "sin_asignaciones": 0}
    for d in db.query(Docente).all():
        tipo = calcular_tipo_modalidad(d, db)
        if tipo == "PRESENCIAL_VIRTUAL": stats["presencial_virtual"] += 1
        elif tipo == "SEDE_VIRTUAL": stats["sede_virtual"] += 1
        elif tipo == "REMOTO": stats["remoto"] += 1
        else: stats["sin_asignaciones"] += 1
    return stats

@app.post("/api/cuatrimestres/replicar")
def replicar_cuatrimestre(data: dict, db: Session = Depends(get_db)):
    origen_id = data.get("origen_id"); destino_id = data.get("destino_id")
    if not origen_id or not destino_id: raise HTTPException(status_code=400, detail="Faltan datos")
    asigs = db.query(Asignacion).filter(Asignacion.cuatrimestre_id == origen_id).all()
    if not asigs: raise HTTPException(status_code=400, detail="Origen sin asignaciones")
    replicadas = ya_existentes = 0
    for a in asigs:
        if db.query(Asignacion).filter(Asignacion.catedra_id == a.catedra_id, Asignacion.cuatrimestre_id == destino_id, Asignacion.modalidad == a.modalidad).first():
            ya_existentes += 1; continue
        db.add(Asignacion(catedra_id=a.catedra_id, cuatrimestre_id=destino_id, modalidad=a.modalidad, dia=a.dia, hora_inicio=a.hora_inicio, hora_fin=a.hora_fin, sede_id=a.sede_id, recibe_alumnos_presenciales=a.recibe_alumnos_presenciales))
        replicadas += 1
    db.commit()
    return {"replicadas": replicadas, "ya_existentes": ya_existentes}

# ===== v5.0: Exportar con desglose sede/turno/modalidad =====
@app.get("/api/exportar/horarios")
def exportar_horarios(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment
    from sqlalchemy import text
    wb = Workbook()
    q = db.query(Asignacion)
    if cuatrimestre_id: q = q.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    asigs = sorted(q.all(), key=lambda a: sort_key_codigo(a.catedra.codigo if a.catedra else 'c.9999'))
    # Inscriptos desglosados
    insc_q = "SELECT catedra_id, COUNT(*) as total, SUM(CASE WHEN modalidad_alumno='virtual' THEN 1 ELSE 0 END) as virt, SUM(CASE WHEN modalidad_alumno='presencial' THEN 1 ELSE 0 END) as pres FROM inscripciones"
    if cuatrimestre_id: insc_q += f" WHERE cuatrimestre_id = {cuatrimestre_id}"
    insc_q += " GROUP BY catedra_id"
    try: insc_rows = {r[0]: (r[1], r[2], r[3]) for r in db.execute(text(insc_q)).fetchall()}
    except: insc_rows = {}
    SEDE_FILL = {'Avellaneda': '3B82F6', 'Caballito': '10B981', 'Vicente López': 'F59E0B', 'Online - Interior': '8B5CF6'}
    headers = ["#", "Código", "Cátedra", "Inscriptos Total", "Virtuales", "Presenciales", "Docente", "Modalidad", "Día", "Hora", "Sede", "Recibe Presenciales"]
    def write_sheet(ws, title, asigs_list, color='1D6F42'):
        ws.title = title[:31]
        ws.append(headers)
        hf = Font(bold=True, color="FFFFFF", size=11); hfill = PatternFill("solid", fgColor=color)
        for cell in ws[1]: cell.font = hf; cell.fill = hfill; cell.alignment = Alignment(horizontal="center")
        for i, a in enumerate(asigs_list, 1):
            insc = insc_rows.get(a.catedra_id, (0, 0, 0))
            ws.append([i, a.catedra.codigo if a.catedra else "", a.catedra.nombre if a.catedra else "",
                insc[0], insc[1], insc[2],
                f"{a.docente.nombre} {a.docente.apellido}" if a.docente else "Sin asignar",
                a.modalidad or "", a.dia or "Pendiente", a.hora_inicio or "Pendiente",
                a.sede.nombre if a.sede else "Remoto", "Sí" if a.recibe_alumnos_presenciales else "No"])
        for col, w in [('A',5),('B',10),('C',32),('D',12),('E',10),('F',12),('G',30),('H',15),('I',12),('J',10),('K',20),('L',18)]:
            ws.column_dimensions[col].width = w
    ws1 = wb.active; write_sheet(ws1, "Todas las sedes", asigs)
    for sede in db.query(Sede).all():
        asigs_sede = [a for a in asigs if a.sede_id == sede.id]
        if asigs_sede:
            write_sheet(wb.create_sheet(), sede.nombre, asigs_sede, SEDE_FILL.get(sede.nombre, '6B7280'))
    asigs_remotos = [a for a in asigs if not a.sede_id]
    if asigs_remotos: write_sheet(wb.create_sheet(), "Remotos", asigs_remotos, '6B7280')
    output = io.BytesIO(); wb.save(output); output.seek(0)
    nombre = f"IEA_Horarios{'_Cuat' + str(cuatrimestre_id) if cuatrimestre_id else ''}.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename={nombre}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
