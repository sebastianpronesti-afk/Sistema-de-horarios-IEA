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

app = FastAPI(title="Sistema Horarios IEA", version="8.0")

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
            for col_s in ['sociedad_cfpea', 'sociedad_isftea']:
                if col_s not in cols:
                    try:
                        db.execute(text(f"ALTER TABLE docentes ADD COLUMN {col_s} BOOLEAN DEFAULT FALSE"))
                        db.commit()
                        resultado.append(f"✅ docentes.{col_s}")
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
    print("🚀 IEA Horarios v8.0 iniciado")

CLAVE_ACCESO = "IEA2026"

@app.get("/")
def root():
    return {"status": "ok", "sistema": "IEA Horarios v6.0"}

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
    # Pre-cargar desglose: turno × (sede presencial o CIED)
    # IMPORTANTE: solo contar inscripciones que YA fueron clasificadas (tienen turno y modalidad_alumno)
    desglose_query = """
        SELECT catedra_id,
            turno,
            modalidad_alumno,
            sede_referencia,
            COUNT(*) as cnt
        FROM inscripciones
        WHERE modalidad_alumno IS NOT NULL
    """
    if cuatrimestre_id:
        desglose_query += f" AND cuatrimestre_id = {cuatrimestre_id}"
    desglose_query += " GROUP BY catedra_id, turno, modalidad_alumno, sede_referencia"
    # Contar sin clasificar aparte
    sin_clasif_query = "SELECT catedra_id, COUNT(*) FROM inscripciones WHERE modalidad_alumno IS NULL"
    if cuatrimestre_id:
        sin_clasif_query += f" AND cuatrimestre_id = {cuatrimestre_id}"
    sin_clasif_query += " GROUP BY catedra_id"
    try:
        desglose_rows = db.execute(text(desglose_query)).fetchall()
    except Exception:
        desglose_rows = []
    sin_clasif_map = {}
    try:
        for r in db.execute(text(sin_clasif_query)).fetchall():
            sin_clasif_map[r[0]] = r[1]
    except Exception:
        pass
    # Organizar: por cátedra → {turno → {sede → count}}
    desglose_map = {}
    for row in desglose_rows:
        cat_id, turno, mod_alumno, sede, cnt = row[0], row[1], row[2], row[3], row[4]
        if cat_id not in desglose_map:
            desglose_map[cat_id] = {
                'total': 0,
                'tm_av': 0, 'tm_cab': 0, 'tm_vl': 0, 'tm_cied': 0,
                'tn_av': 0, 'tn_cab': 0, 'tn_vl': 0, 'tn_cied': 0,
                'virt_cied': 0, 'sin_clasificar': 0,
            }
        d = desglose_map[cat_id]
        d['total'] += cnt
        es_cied = (mod_alumno == 'virtual')
        sede_norm = (sede or '').strip()
        sede_key = None
        if not es_cied:
            if 'avellaneda' in sede_norm.lower(): sede_key = 'av'
            elif 'caballito' in sede_norm.lower(): sede_key = 'cab'
            elif 'vicente' in sede_norm.lower(): sede_key = 'vl'
        if turno == 'Mañana':
            if es_cied or not sede_key:
                d['tm_cied'] += cnt
            else:
                d[f'tm_{sede_key}'] += cnt
        elif turno == 'Noche':
            if es_cied or not sede_key:
                d['tn_cied'] += cnt
            else:
                d[f'tn_{sede_key}'] += cnt
        else:
            d['virt_cied'] += cnt
    # Agregar sin clasificar
    for cat_id, cnt in sin_clasif_map.items():
        if cat_id not in desglose_map:
            desglose_map[cat_id] = {
                'total': 0, 'tm_av': 0, 'tm_cab': 0, 'tm_vl': 0, 'tm_cied': 0,
                'tn_av': 0, 'tn_cab': 0, 'tn_vl': 0, 'tn_cied': 0,
                'virt_cied': 0, 'sin_clasificar': 0,
            }
        desglose_map[cat_id]['sin_clasificar'] = cnt
        desglose_map[cat_id]['total'] += cnt
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
            desg = desglose_map.get(cat.id, {
                'total': 0, 'tm_av': 0, 'tm_cab': 0, 'tm_vl': 0, 'tm_cied': 0,
                'tn_av': 0, 'tn_cab': 0, 'tn_vl': 0, 'tn_cied': 0, 'virt_cied': 0, 'sin_clasificar': 0,
            })
            inscriptos = desg['total']
            tm_total = desg['tm_av'] + desg['tm_cab'] + desg['tm_vl'] + desg['tm_cied']
            tn_total = desg['tn_av'] + desg['tn_cab'] + desg['tn_vl'] + desg['tn_cied']
            clasificados = tm_total + tn_total + desg['virt_cied']
            # v7.0: Sede totals
            sede_av = desg['tm_av'] + desg['tn_av']
            sede_cab = desg['tm_cab'] + desg['tn_cab']
            sede_vl = desg['tm_vl'] + desg['tn_vl']
            sede_cied = desg['tm_cied'] + desg['tn_cied'] + desg['virt_cied']
            docentes_sugeridos = (1 if inscriptos <= 50 else (1 + -(-max(0, inscriptos - 50) // 50))) if inscriptos >= 10 else 0
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
                "tm_av": desg['tm_av'], "tm_cab": desg['tm_cab'], "tm_vl": desg['tm_vl'], "tm_cied": desg['tm_cied'], "tm_total": tm_total,
                "tn_av": desg['tn_av'], "tn_cab": desg['tn_cab'], "tn_vl": desg['tn_vl'], "tn_cied": desg['tn_cied'], "tn_total": tn_total,
                "virt_cied": desg['virt_cied'],
                "sede_av": sede_av, "sede_cab": sede_cab, "sede_vl": sede_vl, "sede_cied": sede_cied,
                "sin_clasificar": desg['sin_clasificar'],
                "docentes_sugeridos": docentes_sugeridos,
                "cursos_vinculados": cursos_vinc,
                "asignaciones": asigs,
            })
        except Exception:
            result.append({"id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "link_meet": None, "inscriptos": 0,
                "tm_av": 0, "tm_cab": 0, "tm_vl": 0, "tm_cied": 0, "tm_total": 0,
                "tn_av": 0, "tn_cab": 0, "tn_vl": 0, "tn_cied": 0, "tn_total": 0,
                "virt_cied": 0, "sede_av": 0, "sede_cab": 0, "sede_vl": 0, "sede_cied": 0,
                "sin_clasificar": 0, "docentes_sugeridos": 0,
                "cursos_vinculados": [], "asignaciones": []})
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
    from sqlalchemy import text
    q_txt = """SELECT catedra_id, COALESCE(turno,'Virtual') as turno, COALESCE(modalidad_alumno,'virtual') as mod,
        COALESCE(sede_referencia,'') as sede, COUNT(*) as cnt
        FROM inscripciones WHERE modalidad_alumno IS NOT NULL"""
    if cuatrimestre_id: q_txt += f" AND cuatrimestre_id = {cuatrimestre_id}"
    q_txt += " GROUP BY catedra_id, turno, modalidad_alumno, sede_referencia"
    try: rows = db.execute(text(q_txt)).fetchall()
    except: return []
    cat_desg = {}
    for r in rows:
        cat_id, turno, mod, sede, cnt = r
        if cat_id not in cat_desg: cat_desg[cat_id] = []
        es_cied = (mod == 'virtual')
        if es_cied: sede_tipo = 'CIED'
        else:
            sn = (sede or '').lower()
            if 'avellaneda' in sn: sede_tipo = 'Avellaneda'
            elif 'caballito' in sn: sede_tipo = 'Caballito'
            elif 'vicente' in sn: sede_tipo = 'Vicente López'
            else: sede_tipo = 'CIED'
        cat_desg[cat_id].append({'turno': turno, 'sede_tipo': sede_tipo, 'cant': cnt})
    result = []
    for cat_id, items in cat_desg.items():
        cat = db.query(Catedra).filter(Catedra.id == cat_id).first()
        if not cat: continue
        agrupado = {}
        for it in items:
            key = f"{it['turno']}|{it['sede_tipo']}"
            agrupado[key] = agrupado.get(key, 0) + it['cant']
        asigs = db.query(Asignacion).filter(Asignacion.catedra_id == cat_id)
        if cuatrimestre_id: asigs = asigs.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
        asigs_list = asigs.all()
        total_insc = sum(agrupado.values())
        aperturas = []
        for key, cnt in agrupado.items():
            if cnt < 10: continue
            turno, sede_tipo = key.split('|')
            aperturas.append({'turno': turno, 'sede': sede_tipo, 'inscriptos': cnt, 'tiene_docente': False})
        if not aperturas: continue
        # Verificar docentes existentes
        docs_asig = [a for a in asigs_list if a.docente_id]
        for ap in aperturas:
            for a in docs_asig:
                m = a.modalidad or ''
                s = a.sede.nombre if a.sede else ''
                if ap['turno'] == 'Mañana' and 'tm' in m: ap['tiene_docente'] = True
                elif ap['turno'] == 'Noche' and ('tn' in m or m == 'presencial'): ap['tiene_docente'] = True
                elif ap['turno'] == 'Virtual' and 'virtual' in m: ap['tiene_docente'] = True
        sin_doc = [a for a in aperturas if not a['tiene_docente']]
        if not sin_doc and not any(a['tiene_docente'] for a in aperturas): continue
        result.append({
            "catedra_id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
            "inscriptos_total": total_insc, "docentes_asignados": len(docs_asig),
            "docentes_nombres": [f"{a.docente.nombre} {a.docente.apellido}" for a in docs_asig if a.docente],
            "aperturas_necesarias": aperturas,  # ALL aperturas, both covered and uncovered
            "tiene_sin_cubrir": len(sin_doc) > 0,
        })
    result.sort(key=lambda x: sort_key_codigo(x['codigo']))
    return result

# ===== v8.0: Criterio de apertura simplificado =====
@app.get("/api/catedras/criterio-apertura")
def get_criterio_apertura(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    """
    >=10 total → ABRIR. 1 doc hasta 50, luego +1 cada 50 adicionales.
    1-9 total → ASINCRÓNICA
    0 → SIN ALUMNOS
    """
    from sqlalchemy import text
    total_q = "SELECT catedra_id, COUNT(*) FROM inscripciones"
    if cuatrimestre_id: total_q += f" WHERE cuatrimestre_id = {cuatrimestre_id}"
    total_q += " GROUP BY catedra_id"
    total_map = {}
    try:
        for r in db.execute(text(total_q)).fetchall(): total_map[r[0]] = r[1]
    except: pass
    all_cats = sorted(db.query(Catedra).all(), key=lambda c: sort_key_codigo(c.codigo))
    abrir = []; asincronica = []; sin_alumnos = []
    for cat in all_cats:
        total = total_map.get(cat.id, 0)
        if total == 0:
            sin_alumnos.append({"codigo": cat.codigo, "nombre": cat.nombre, "total": 0})
        elif total < 10:
            asincronica.append({"codigo": cat.codigo, "nombre": cat.nombre, "total": total})
        else:
            docs = 1 if total <= 50 else (1 + -(-max(0, total - 50) // 50))
            # Check if already has asignacion
            tiene = db.query(Asignacion).filter(Asignacion.catedra_id == cat.id)
            if cuatrimestre_id: tiene = tiene.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
            tiene_asig = tiene.count() > 0
            docs_actuales = tiene.filter(Asignacion.docente_id.isnot(None)).count() if tiene_asig else 0
            abrir.append({"codigo": cat.codigo, "nombre": cat.nombre, "total": total,
                "docentes_sugeridos": docs, "docentes_actuales": docs_actuales,
                "faltan": max(0, docs - docs_actuales), "tiene_asignacion": tiene_asig})
    return {"abrir": abrir, "asincronica": asincronica, "sin_alumnos": sin_alumnos,
        "stats": {"total_abrir": len(abrir), "total_asincronica": len(asincronica),
            "total_sin_alumnos": len(sin_alumnos),
            "total_docentes_sugeridos": sum(a["docentes_sugeridos"] for a in abrir)}}


@app.get("/api/inscriptos/por-curso")
def get_inscriptos_por_curso(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    from sqlalchemy import text
    q = """SELECT curso_nombre, 
        COUNT(*) as total_inscripciones,
        COUNT(DISTINCT alumno_id) as alumnos_unicos
        FROM inscripciones WHERE curso_nombre IS NOT NULL AND curso_nombre != ''"""
    if cuatrimestre_id:
        q += f" AND cuatrimestre_id = {cuatrimestre_id}"
    q += " GROUP BY curso_nombre ORDER BY total_inscripciones DESC"
    try:
        rows = db.execute(text(q)).fetchall()
        result = []
        for r in rows:
            curso_raw = r[0]; total_insc = r[1]; alumnos = r[2]
            nombre_limpio = re.split(r'\s*[-–]\s*(?:CIED|Cursada)', curso_raw, maxsplit=1)[0].strip()
            nombre_limpio = re.split(r'\s*\(', nombre_limpio, maxsplit=1)[0].strip()
            es_cied = 'CIED' in curso_raw.upper()
            m_sede = re.search(r'\(([^)]+)\)', curso_raw)
            sede_raw = m_sede.group(1).strip() if m_sede else ''
            sede = normalizar_sede(sede_raw) if sede_raw else 'Sin sede'
            es_online = sede in ['Online - Interior']
            modalidad = 'CIED' if (es_cied or es_online) else 'Presencial'
            es_bce = 'BCE' in curso_raw.upper() or 'SECUNDARIO' in curso_raw.upper()
            es_bea = 'BEA' in curso_raw.upper()
            tipo_curso = 'BCE' if es_bce else ('BEA' if es_bea else 'Superior')
            result.append({
                "curso_completo": curso_raw, "curso_nombre": nombre_limpio,
                "sede": sede, "modalidad": modalidad, "tipo_curso": tipo_curso,
                "inscripciones": total_insc, "alumnos_unicos": alumnos,
            })
        return result
    except Exception as e:
        return []


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
            cfpea = getattr(d, 'sociedad_cfpea', False) or False
            isftea = getattr(d, 'sociedad_isftea', False) or False
            result.append({
                "id": d.id, "dni": d.dni, "nombre": d.nombre, "apellido": d.apellido,
                "email": d.email, "tipo_modalidad": tipo,
                "horas_asignadas": horas,
                "sociedad_cfpea": cfpea, "sociedad_isftea": isftea,
                "sedes": sedes_data, "asignaciones": asigs_data,
            })
        except Exception:
            result.append({"id": d.id, "dni": d.dni, "nombre": d.nombre, "apellido": d.apellido,
                "email": d.email, "tipo_modalidad": "SIN_ASIGNACIONES",
                "horas_asignadas": 0, "sociedad_cfpea": False, "sociedad_isftea": False,
                "sedes": [], "asignaciones": []})
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
    # v6.0: horas and sociedad
    if "horas_asignadas" in data:
        try:
            db.execute(text(f"UPDATE docentes SET horas_asignadas = {int(data['horas_asignadas'])} WHERE id = {docente_id}"))
        except Exception: pass
    if "sociedad_cfpea" in data:
        try:
            val = 'TRUE' if data['sociedad_cfpea'] else 'FALSE'
            db.execute(text(f"UPDATE docentes SET sociedad_cfpea = {val} WHERE id = {docente_id}"))
        except Exception: pass
    if "sociedad_isftea" in data:
        try:
            val = 'TRUE' if data['sociedad_isftea'] else 'FALSE'
            db.execute(text(f"UPDATE docentes SET sociedad_isftea = {val} WHERE id = {docente_id}"))
        except Exception: pass
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
        creados = 0; inscripciones = 0; actualizados = 0; errores = []
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
                    try:
                        db.execute(text(
                            "UPDATE inscripciones SET turno = :turno, modalidad_alumno = :mod, sede_referencia = :sede, curso_nombre = :curso WHERE id = :id"
                        ), {"turno": turno, "mod": modalidad_alumno, "sede": sede_ref, "curso": curso_texto[:200] if curso_texto else None, "id": insc.id})
                    except Exception:
                        pass
                    inscripciones += 1
                else:
                    # SIEMPRE sobreescribir clasificación (no COALESCE)
                    try:
                        db.execute(text(
                            "UPDATE inscripciones SET turno = :turno, modalidad_alumno = :mod, sede_referencia = :sede, curso_nombre = :curso WHERE id = :id"
                        ), {"turno": turno, "mod": modalidad_alumno, "sede": sede_ref, "curso": curso_texto[:200] if curso_texto else None, "id": existe.id})
                        actualizados += 1
                    except Exception:
                        pass
                # Contar stats siempre
                stats[modalidad_alumno] = stats.get(modalidad_alumno, 0) + 1
                if turno: stats['turnos'][turno] = stats['turnos'].get(turno, 0) + 1
                if sede_ref: stats['sedes'][sede_ref] = stats['sedes'].get(sede_ref, 0) + 1
        db.commit(); wb.close()
        return {
            "alumnos_nuevos": creados, "inscripciones_nuevas": inscripciones,
            "inscripciones_actualizadas": actualizados,
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



# ===== v7.0: Exportar COMPLETO =====
@app.get("/api/exportar/horarios")
def exportar_horarios(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment
    from sqlalchemy import text
    wb = Workbook()
    q = db.query(Asignacion)
    if cuatrimestre_id: q = q.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    asigs = sorted(q.all(), key=lambda a: sort_key_codigo(a.catedra.codigo if a.catedra else 'c.9999'))
    # -- Inscriptos desglosados --
    insc_q = """SELECT catedra_id, turno, modalidad_alumno, sede_referencia, COUNT(*) FROM inscripciones WHERE modalidad_alumno IS NOT NULL"""
    if cuatrimestre_id: insc_q += f" AND cuatrimestre_id = {cuatrimestre_id}"
    insc_q += " GROUP BY catedra_id, turno, modalidad_alumno, sede_referencia"
    insc_desg = {}
    try:
        for r in db.execute(text(insc_q)).fetchall():
            cid, turno, mod, sede, cnt = r
            if cid not in insc_desg:
                insc_desg[cid] = {'total':0,'tm_av':0,'tm_cab':0,'tm_vl':0,'tm_cied':0,'tn_av':0,'tn_cab':0,'tn_vl':0,'tn_cied':0,'virt':0}
            d = insc_desg[cid]; d['total'] += cnt
            es_cied = (mod == 'virtual')
            sk = None
            if not es_cied:
                sl = (sede or '').lower()
                if 'avellaneda' in sl: sk = 'av'
                elif 'caballito' in sl: sk = 'cab'
                elif 'vicente' in sl: sk = 'vl'
            if turno == 'Mañana': d[f'tm_{sk}' if sk else 'tm_cied'] += cnt
            elif turno == 'Noche': d[f'tn_{sk}' if sk else 'tn_cied'] += cnt
            else: d['virt'] += cnt
    except: pass
    total_insc_q = "SELECT catedra_id, COUNT(*) FROM inscripciones"
    if cuatrimestre_id: total_insc_q += f" WHERE cuatrimestre_id = {cuatrimestre_id}"
    total_insc_q += " GROUP BY catedra_id"
    total_insc_map = {}
    try:
        for r in db.execute(text(total_insc_q)).fetchall(): total_insc_map[r[0]] = r[1]
    except: pass
    hf = Font(bold=True, color="FFFFFF", size=10)
    YELLOW = PatternFill("solid", fgColor="FFFFCC")
    def make_hdr(ws, headers, color='1D6F42'):
        ws.append(headers)
        for cell in ws[1]:
            cell.font = hf; cell.fill = PatternFill("solid", fgColor=color); cell.alignment = Alignment(horizontal="center")
    all_cats = sorted(db.query(Catedra).all(), key=lambda c: sort_key_codigo(c.codigo))

    # ========== HOJA 1 (PRINCIPAL): Inscriptos de todas las cátedras unificadas ==========
    ws0 = wb.active; ws0.title = "Inscriptos unificados"
    make_hdr(ws0, ["#","Código","Cátedra","TM Avellaneda","TM Caballito","TM Vicente López","TM CIED","Total TM","TN Avellaneda","TN Caballito","TN Vicente López","TN CIED","Total TN","CIED Virtual","Sede Avellaneda","Sede Caballito","Sede V.López","Sede CIED","TOTAL"], '0F766E')
    for i, cat in enumerate(all_cats, 1):
        d = insc_desg.get(cat.id, {})
        tm_t = d.get('tm_av',0)+d.get('tm_cab',0)+d.get('tm_vl',0)+d.get('tm_cied',0)
        tn_t = d.get('tn_av',0)+d.get('tn_cab',0)+d.get('tn_vl',0)+d.get('tn_cied',0)
        s_av = d.get('tm_av',0)+d.get('tn_av',0)
        s_cab = d.get('tm_cab',0)+d.get('tn_cab',0)
        s_vl = d.get('tm_vl',0)+d.get('tn_vl',0)
        s_cied = d.get('tm_cied',0)+d.get('tn_cied',0)+d.get('virt',0)
        tot = total_insc_map.get(cat.id, 0)
        if tot == 0 and d.get('total',0) == 0: continue
        ws0.append([i, cat.codigo, cat.nombre,
            d.get('tm_av',0) or '', d.get('tm_cab',0) or '', d.get('tm_vl',0) or '', d.get('tm_cied',0) or '', tm_t or '',
            d.get('tn_av',0) or '', d.get('tn_cab',0) or '', d.get('tn_vl',0) or '', d.get('tn_cied',0) or '', tn_t or '',
            d.get('virt',0) or '', s_av or '', s_cab or '', s_vl or '', s_cied or '', tot or ''])
        if tot >= 10:
            tiene = any(1 for a in asigs if a.catedra_id == cat.id)
            if not tiene:
                for cell in ws0[ws0.max_row]: cell.fill = YELLOW
    for col, w in [('A',4),('B',8),('C',28),('D',14),('E',13),('F',16),('G',9),('H',9),('I',14),('J',13),('K',16),('L',9),('M',9),('N',11),('O',14),('P',13),('Q',13),('R',10),('S',7)]:
        ws0.column_dimensions[col].width = w

    # ========== HOJA 2: Totalidad General (antes "Todas las sedes") ==========
    ws1 = wb.create_sheet("Totalidad General")
    ws1.append(["#","Código","Cátedra","TM Av","TM Cab","TM VL","TM CIED","Tot TM","TN Av","TN Cab","TN VL","TN CIED","Tot TN","CIED Virt","TOTAL","Docente","Turno Doc.","Modalidad","Día","Hora","Sede"])
    for cell in ws1[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="1D6F42"); cell.alignment = Alignment(horizontal="center")
    for i, a in enumerate(asigs, 1):
        d = insc_desg.get(a.catedra_id, {})
        tm_t = d.get('tm_av',0)+d.get('tm_cab',0)+d.get('tm_vl',0)+d.get('tm_cied',0)
        tn_t = d.get('tn_av',0)+d.get('tn_cab',0)+d.get('tn_vl',0)+d.get('tn_cied',0)
        tot = total_insc_map.get(a.catedra_id, 0)
        mod = a.modalidad or ''
        td = 'Mañana' if 'tm' in mod else ('Noche' if 'tn' in mod else ('Asincrónica' if mod == 'asincronica' else 'Presencial'))
        ws1.append([i, a.catedra.codigo if a.catedra else "", a.catedra.nombre if a.catedra else "",
            d.get('tm_av',0) or '', d.get('tm_cab',0) or '', d.get('tm_vl',0) or '', d.get('tm_cied',0) or '', tm_t or '',
            d.get('tn_av',0) or '', d.get('tn_cab',0) or '', d.get('tn_vl',0) or '', d.get('tn_cied',0) or '', tn_t or '',
            d.get('virt',0) or '', tot or '',
            f"{a.docente.nombre} {a.docente.apellido}" if a.docente else "Sin asignar", td,
            mod, a.dia or "Pend.", a.hora_inicio or "Pend.", a.sede.nombre if a.sede else "Remoto"])
        if tot >= 10 and not a.docente_id:
            for cell in ws1[ws1.max_row]: cell.fill = YELLOW
    for col, w in [('A',4),('B',8),('C',28),('D',7),('E',7),('F',7),('G',7),('H',7),('I',7),('J',7),('K',7),('L',7),('M',7),('N',9),('O',7),('P',26),('Q',10),('R',12),('S',10),('T',7),('U',16)]:
        ws1.column_dimensions[col].width = w

    # ========== HOJAS POR SEDE ==========
    for sede_key, sede_name, color in [('av','Avellaneda','3B82F6'),('cab','Caballito','10B981'),('vl','Vicente López','F59E0B'),('cied','CIED','8B5CF6')]:
        ws = wb.create_sheet(sede_name[:31])
        if sede_key == 'cied':
            ws.append(["#","Código","Cátedra","TM CIED","TN CIED","Virtual","TOTAL","Docente","Turno","Día","Hora"])
            sede_asigs = [a for a in asigs if not a.sede_id or (a.modalidad and ('virtual' in a.modalidad or a.modalidad == 'asincronica'))]
        else:
            ws.append(["#","Código","Cátedra",f"TM {sede_name}",f"TN {sede_name}","TOTAL","Docente","Turno","Día","Hora"])
            sede_db = db.query(Sede).filter(Sede.nombre == sede_name).first()
            sede_asigs = [a for a in asigs if a.sede_id == (sede_db.id if sede_db else -1)]
        for cell in ws[1]:
            cell.font = hf; cell.fill = PatternFill("solid", fgColor=color); cell.alignment = Alignment(horizontal="center")
        for i, a in enumerate(sede_asigs, 1):
            d = insc_desg.get(a.catedra_id, {})
            mod = a.modalidad or ''
            td = 'Mañana' if 'tm' in mod else ('Noche' if 'tn' in mod else 'Otro')
            if sede_key == 'cied':
                tm_v=d.get('tm_cied',0); tn_v=d.get('tn_cied',0); vv=d.get('virt',0)
                ws.append([i, a.catedra.codigo if a.catedra else "", a.catedra.nombre if a.catedra else "",
                    tm_v or '', tn_v or '', vv or '', (tm_v+tn_v+vv) or '',
                    f"{a.docente.nombre} {a.docente.apellido}" if a.docente else "Sin asignar", td, a.dia or "Pend.", a.hora_inicio or "Pend."])
            else:
                tm_v=d.get(f'tm_{sede_key}',0); tn_v=d.get(f'tn_{sede_key}',0)
                ws.append([i, a.catedra.codigo if a.catedra else "", a.catedra.nombre if a.catedra else "",
                    tm_v or '', tn_v or '', (tm_v+tn_v) or '',
                    f"{a.docente.nombre} {a.docente.apellido}" if a.docente else "Sin asignar", td, a.dia or "Pend.", a.hora_inicio or "Pend."])
        for col, w in [('A',4),('B',8),('C',28),('D',14),('E',14),('F',10),('G',7),('H',26),('I',10),('J',10),('K',7)]:
            ws.column_dimensions[col].width = w

    # ========== HOJA: Listado Total Docentes (ordenado por sede) ==========
    docentes_db = db.query(Docente).order_by(Docente.apellido).all()
    ws_ld = wb.create_sheet("Listado Docentes")
    ws_ld.append(["#","Docente","DNI","Email","Horas","CFPEA","ISFTEA","Sedes","Cátedras asignadas","Modalidad","Día","Hora"])
    for cell in ws_ld[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="334155"); cell.alignment = Alignment(horizontal="center")
    idx = 1
    # Ordenar por sede principal
    def sede_sort_key(doc):
        sds = [s.sede.nombre for s in (doc.sedes or []) if s.sede]
        return sds[0] if sds else 'ZZZ'
    for doc in sorted(docentes_db, key=sede_sort_key):
        sds = ', '.join([s.sede.nombre for s in (doc.sedes or []) if s.sede]) or 'Sin sede'
        doc_asigs = [a for a in asigs if a.docente_id == doc.id]
        if doc_asigs:
            for a in doc_asigs:
                ws_ld.append([idx, f"{doc.nombre} {doc.apellido}", doc.dni, doc.email or '',
                    getattr(doc, 'horas_asignadas', 0) or '',
                    "Sí" if getattr(doc, 'sociedad_cfpea', False) else "",
                    "Sí" if getattr(doc, 'sociedad_isftea', False) else "",
                    sds, f"{a.catedra.codigo} {a.catedra.nombre}" if a.catedra else "",
                    a.modalidad or '', a.dia or "Pend.", a.hora_inicio or "Pend."])
                idx += 1
        else:
            ws_ld.append([idx, f"{doc.nombre} {doc.apellido}", doc.dni, doc.email or '',
                getattr(doc, 'horas_asignadas', 0) or '',
                "Sí" if getattr(doc, 'sociedad_cfpea', False) else "",
                "Sí" if getattr(doc, 'sociedad_isftea', False) else "",
                sds, "SIN MATERIA ASIGNADA", '', '', ''])
            idx += 1
    for col, w in [('A',4),('B',28),('C',12),('D',24),('E',7),('F',7),('G',8),('H',20),('I',34),('J',13),('K',10),('L',7)]:
        ws_ld.column_dimensions[col].width = w

    # ========== HOJA: Docentes TM ==========
    ws_dtm = wb.create_sheet("Docentes TM")
    ws_dtm.append(["#","Docente","DNI","Email","Horas","CFPEA","ISFTEA","Cátedra","Sede","Día","Hora"])
    for cell in ws_dtm[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="D97706"); cell.alignment = Alignment(horizontal="center")
    idx = 1
    for doc in docentes_db:
        for a in [a for a in asigs if a.docente_id == doc.id and a.modalidad and 'tm' in a.modalidad]:
            ws_dtm.append([idx, f"{doc.nombre} {doc.apellido}", doc.dni, doc.email or '',
                getattr(doc, 'horas_asignadas', 0) or '',
                "Sí" if getattr(doc, 'sociedad_cfpea', False) else "",
                "Sí" if getattr(doc, 'sociedad_isftea', False) else "",
                f"{a.catedra.codigo} {a.catedra.nombre}" if a.catedra else "", a.sede.nombre if a.sede else "Remoto",
                a.dia or "Pend.", a.hora_inicio or "Pend."])
            idx += 1
    for col, w in [('A',4),('B',28),('C',12),('D',24),('E',7),('F',7),('G',8),('H',32),('I',16),('J',10),('K',7)]:
        ws_dtm.column_dimensions[col].width = w

    # ========== HOJA: Docentes TN ==========
    ws_dtn = wb.create_sheet("Docentes TN")
    ws_dtn.append(["#","Docente","DNI","Email","Horas","CFPEA","ISFTEA","Cátedra","Sede","Día","Hora"])
    for cell in ws_dtn[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="4338CA"); cell.alignment = Alignment(horizontal="center")
    idx = 1
    for doc in docentes_db:
        for a in [a for a in asigs if a.docente_id == doc.id and a.modalidad and ('tn' in a.modalidad or a.modalidad == 'presencial')]:
            ws_dtn.append([idx, f"{doc.nombre} {doc.apellido}", doc.dni, doc.email or '',
                getattr(doc, 'horas_asignadas', 0) or '',
                "Sí" if getattr(doc, 'sociedad_cfpea', False) else "",
                "Sí" if getattr(doc, 'sociedad_isftea', False) else "",
                f"{a.catedra.codigo} {a.catedra.nombre}" if a.catedra else "", a.sede.nombre if a.sede else "Remoto",
                a.dia or "Pend.", a.hora_inicio or "Pend."])
            idx += 1
    for col, w in [('A',4),('B',28),('C',12),('D',24),('E',7),('F',7),('G',8),('H',32),('I',16),('J',10),('K',7)]:
        ws_dtn.column_dimensions[col].width = w

    # ========== HOJA: Inscriptos por Curso ==========
    ws_cur = wb.create_sheet("Inscriptos por Curso")
    ws_cur.append(["#","Curso","Sede","Modalidad","Tipo","Alumnos (DNI)","Inscripciones"])
    for cell in ws_cur[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="6B21A8"); cell.alignment = Alignment(horizontal="center")
    c_q = """SELECT curso_nombre, COUNT(DISTINCT alumno_id), COUNT(*) FROM inscripciones WHERE curso_nombre IS NOT NULL AND curso_nombre != ''"""
    if cuatrimestre_id: c_q += f" AND cuatrimestre_id = {cuatrimestre_id}"
    c_q += " GROUP BY curso_nombre ORDER BY COUNT(*) DESC"
    try:
        for i, r in enumerate(db.execute(text(c_q)).fetchall(), 1):
            curso_raw, unicos, total = r[0], r[1], r[2]
            es_cied = 'CIED' in curso_raw.upper()
            m_s = re.search(r'\(([^)]+)\)', curso_raw)
            sede_r = normalizar_sede(m_s.group(1).strip()) if m_s else 'Sin sede'
            mod = 'CIED' if (es_cied or sede_r in ['Online - Interior']) else 'Presencial'
            es_bce = 'BCE' in curso_raw.upper() or 'SECUNDARIO' in curso_raw.upper()
            tipo = 'BCE' if es_bce else ('BEA' if 'BEA' in curso_raw.upper() else 'Superior')
            ws_cur.append([i, curso_raw, sede_r, mod, tipo, unicos, total])
    except: pass
    for col, w in [('A',4),('B',60),('C',18),('D',12),('E',10),('F',16),('G',14)]:
        ws_cur.column_dimensions[col].width = w

    # ========== HOJA: Necesitan Docente (con sede+turno) ==========
    ws_nd = wb.create_sheet("Necesitan Docente")
    ws_nd.append(["#","Código","Cátedra","Turno","Sede","Inscriptos","Cubierto","Docentes actuales"])
    for cell in ws_nd[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="DC2626"); cell.alignment = Alignment(horizontal="center")
    nd_data = get_catedras_necesitan_docente(cuatrimestre_id, db)
    idx = 1
    for nd in nd_data:
        for ap in nd.get('aperturas_necesarias', []):
            cubierto = "✅ Sí" if ap.get('tiene_docente') else "❌ No"
            ws_nd.append([idx, nd['codigo'], nd['nombre'], ap['turno'], ap['sede'], ap['inscriptos'],
                cubierto, ', '.join(nd['docentes_nombres']) or "Sin docente"])
            if not ap.get('tiene_docente'):
                for cell in ws_nd[ws_nd.max_row]: cell.fill = YELLOW
            idx += 1
    for col, w in [('A',4),('B',8),('C',30),('D',10),('E',16),('F',12),('G',10),('H',36)]:
        ws_nd.column_dimensions[col].width = w

    # ========== v7.0: 3 nuevas solapas de criterio de apertura ==========
    criterio = get_criterio_apertura(cuatrimestre_id, db)

    # --- HOJA: Abrir Cátedra (>=10 inscriptos total) ---
    ws_abrir = wb.create_sheet("Abrir cátedra")
    ws_abrir.append(["#","Código","Cátedra","Total inscriptos","Docentes sugeridos","Docentes actuales","Faltan","Estado"])
    for cell in ws_abrir[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="059669"); cell.alignment = Alignment(horizontal="center")
    for i, item in enumerate(criterio['abrir'], 1):
        estado = "✅ Cubierto" if item['faltan'] == 0 else "⚠️ Faltan docentes"
        ws_abrir.append([i, item['codigo'], item['nombre'], item['total'],
            item['docentes_sugeridos'], item['docentes_actuales'], item['faltan'], estado])
        if item['faltan'] > 0:
            for cell in ws_abrir[ws_abrir.max_row]: cell.fill = YELLOW
    for col, w in [('A',4),('B',8),('C',30),('D',14),('E',16),('F',16),('G',8),('H',18)]:
        ws_abrir.column_dimensions[col].width = w

    # --- HOJA: Cátedra Asincrónica (1-9 inscriptos total) ---
    ws_asinc = wb.create_sheet("Cátedra asincrónica")
    ws_asinc.append(["#","Código","Cátedra","Total inscriptos","Observación"])
    for cell in ws_asinc[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="7C3AED"); cell.alignment = Alignment(horizontal="center")
    for i, item in enumerate(criterio['asincronica'], 1):
        ws_asinc.append([i, item['codigo'], item['nombre'], item['total'], "1 a 9 inscriptos → Se dicta de forma asincrónica (pregrabada)"])
    for col, w in [('A',4),('B',8),('C',30),('D',14),('E',50)]:
        ws_asinc.column_dimensions[col].width = w

    # --- HOJA: Cátedra sin alumnos ---
    ws_sin = wb.create_sheet("Cátedra sin alumnos")
    ws_sin.append(["#","Código","Cátedra","Inscriptos"])
    for cell in ws_sin[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="6B7280"); cell.alignment = Alignment(horizontal="center")
    idx = 1
    for cat in all_cats:
        ic = total_insc_map.get(cat.id, 0)
        if ic == 0:
            ws_sin.append([idx, cat.codigo, cat.nombre, 0])
            idx += 1
    for col, w in [('A',4),('B',8),('C',30),('D',12)]:
        ws_sin.column_dimensions[col].width = w

    # ========== HOJA: Solapamientos ==========
    ws_sol = wb.create_sheet("Solapamientos")
    ws_sol.append(["#","Tipo","Severidad","Mensaje","Día","Hora"])
    for cell in ws_sol[1]:
        cell.font = hf; cell.fill = PatternFill("solid", fgColor="B91C1C"); cell.alignment = Alignment(horizontal="center")
    for i, s in enumerate(get_solapamientos(cuatrimestre_id, db), 1):
        ws_sol.append([i, s.get('tipo',''), s.get('severidad',''), s.get('mensaje',''), s.get('dia',''), s.get('hora','')])
    for col, w in [('A',4),('B',12),('C',12),('D',60),('E',12),('F',7)]:
        ws_sol.column_dimensions[col].width = w

    output = io.BytesIO(); wb.save(output); output.seek(0)
    nombre = f"IEA_Horarios{'_Cuat' + str(cuatrimestre_id) if cuatrimestre_id else ''}.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename={nombre}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
