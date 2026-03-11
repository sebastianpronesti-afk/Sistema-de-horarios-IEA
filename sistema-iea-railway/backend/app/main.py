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

app = FastAPI(title="Sistema Horarios IEA", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MIGRACIÓN ====================

def run_migration(db):
    from sqlalchemy import text, inspect
    resultado = []
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        resultado.append(f"Tablas existentes: {tables}")
        Base.metadata.create_all(bind=engine)
        resultado.append("✅ create_all ejecutado")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if 'catedras' in tables:
            cols = [c['name'] for c in inspector.get_columns('catedras')]
            if 'link_meet' not in cols:
                db.execute(text("ALTER TABLE catedras ADD COLUMN link_meet VARCHAR"))
                db.commit()
                resultado.append("✅ catedras.link_meet agregado")
        if 'asignaciones' in tables:
            cols = [c['name'] for c in inspector.get_columns('asignaciones')]
            resultado.append(f"Columnas asignaciones: {cols}")
            if 'hora' in cols and 'hora_inicio' not in cols:
                try:
                    db.execute(text("ALTER TABLE asignaciones RENAME COLUMN hora TO hora_inicio"))
                    db.commit()
                    resultado.append("✅ asignaciones.hora → hora_inicio (renombrado)")
                    cols = [c['name'] for c in inspector.get_columns('asignaciones')]
                except Exception as e:
                    resultado.append(f"⚠️ Renombrar hora: {e}")
                    db.rollback()
            columns_needed = [
                ('hora_inicio', 'VARCHAR'),
                ('hora_fin', 'VARCHAR'),
                ('modalidad', "VARCHAR DEFAULT 'virtual_tm'"),
                ('sede_id', 'INTEGER REFERENCES sedes(id)'),
                ('recibe_alumnos_presenciales', 'BOOLEAN DEFAULT FALSE'),
                ('modificada', 'BOOLEAN DEFAULT FALSE'),
            ]
            for col, tipo in columns_needed:
                if col not in cols:
                    try:
                        db.execute(text(f"ALTER TABLE asignaciones ADD COLUMN {col} {tipo}"))
                        db.commit()
                        resultado.append(f"✅ asignaciones.{col} agregado")
                    except Exception as e:
                        resultado.append(f"⚠️ asignaciones.{col}: {e}")
                        db.rollback()
        if 'docente_sede' not in tables:
            try:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS docente_sede (
                        id SERIAL PRIMARY KEY,
                        docente_id INTEGER REFERENCES docentes(id) ON DELETE CASCADE,
                        sede_id INTEGER REFERENCES sedes(id) ON DELETE CASCADE
                    )
                """))
                db.commit()
                resultado.append("✅ Tabla docente_sede creada")
            except Exception as e:
                resultado.append(f"⚠️ docente_sede: {e}")
                db.rollback()
        if 'catedra_curso' not in tables:
            try:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS catedra_curso (
                        id SERIAL PRIMARY KEY,
                        catedra_id INTEGER REFERENCES catedras(id) ON DELETE CASCADE,
                        curso_id INTEGER REFERENCES cursos(id) ON DELETE CASCADE,
                        turno VARCHAR,
                        sede_id INTEGER REFERENCES sedes(id)
                    )
                """))
                db.commit()
                resultado.append("✅ Tabla catedra_curso creada")
            except Exception as e:
                resultado.append(f"⚠️ catedra_curso: {e}")
                db.rollback()
        # Limpiar sedes duplicadas Vicente Lopez / Vicente López
        try:
            sede_sin_tilde = db.query(Sede).filter(Sede.nombre == "Vicente Lopez").first()
            sede_con_tilde = db.query(Sede).filter(Sede.nombre == "Vicente López").first()
            if sede_sin_tilde and sede_con_tilde:
                keeper = sede_con_tilde
                dupe = sede_sin_tilde
                db.execute(text(f"UPDATE cursos SET sede_id = {keeper.id} WHERE sede_id = {dupe.id}"))
                db.execute(text(f"UPDATE asignaciones SET sede_id = {keeper.id} WHERE sede_id = {dupe.id}"))
                db.execute(text(f"DELETE FROM docente_sede WHERE sede_id = {dupe.id} AND docente_id IN (SELECT docente_id FROM docente_sede WHERE sede_id = {keeper.id})"))
                db.execute(text(f"UPDATE docente_sede SET sede_id = {keeper.id} WHERE sede_id = {dupe.id}"))
                if 'catedra_curso' in tables:
                    db.execute(text(f"UPDATE catedra_curso SET sede_id = {keeper.id} WHERE sede_id = {dupe.id}"))
                db.execute(text(f"DELETE FROM sedes WHERE id = {dupe.id}"))
                db.commit()
                resultado.append(f"✅ Sedes fusionadas: Vicente Lopez → Vicente López")
            elif sede_sin_tilde and not sede_con_tilde:
                sede_sin_tilde.nombre = "Vicente López"
                db.commit()
                resultado.append("✅ Sede renombrada a Vicente López")
        except Exception as e:
            resultado.append(f"⚠️ Limpieza sedes: {e}")
            db.rollback()
    except Exception as e:
        resultado.append(f"❌ Error migración: {e}")
    return resultado


# ==================== STARTUP ====================

@app.on_event("startup")
async def startup():
    db = next(get_db())
    migr = run_migration(db)
    for m in migr:
        print(f"  [MIGRACIÓN] {m}")
    try:
        from app.seed_data import SEDES, CATEDRAS, CURSOS, DOCENTES
        for nombre, color in SEDES:
            if not db.query(Sede).filter(Sede.nombre == nombre).first():
                db.add(Sede(nombre=nombre, color=color))
        db.commit()
        # ===== v4.0: Cuatrimestres 2026-2030 =====
        if not db.query(Cuatrimestre).first():
            for anio in range(2026, 2031):
                db.add(Cuatrimestre(nombre=f"1er Cuatrimestre {anio}", anio=anio, numero=1, activo=(anio == 2026 and True)))
                db.add(Cuatrimestre(nombre=f"2do Cuatrimestre {anio}", anio=anio, numero=2, activo=False))
            db.commit()
            print("  ✅ Cuatrimestres 2026-2030 creados")
        else:
            # Asegurar que existan cuatrimestres hasta 2030
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
            print(f"  ✅ {len(CATEDRAS)} cátedras cargadas")
        if db.query(Curso).count() == 0:
            for sede_nombre, nombre in CURSOS:
                sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first()
                db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None))
            db.commit()
            print(f"  ✅ {len(CURSOS)} cursos cargados")
        if db.query(Docente).count() == 0:
            for dni, nombre, apellido in DOCENTES:
                db.add(Docente(dni=dni, nombre=nombre, apellido=apellido))
            db.commit()
            print(f"  ✅ {len(DOCENTES)} docentes cargados")
    except ImportError:
        print("  ⚠️ seed_data.py no encontrado")
    except Exception as e:
        print(f"  ⚠️ Seed error: {e}")
    db.close()
    print("🚀 IEA Horarios v4.0 iniciado")


CLAVE_ACCESO = "IEA2026"

@app.get("/")
def root():
    return {"status": "ok", "sistema": "IEA Horarios v4.0"}

@app.get("/api/reparar")
def reparar_bd(db: Session = Depends(get_db)):
    resultado = run_migration(db)
    try:
        from app.seed_data import SEDES, CATEDRAS, CURSOS, DOCENTES
        nuevas_sedes = 0
        for nombre, color in SEDES:
            if not db.query(Sede).filter(Sede.nombre == nombre).first():
                db.add(Sede(nombre=nombre, color=color))
                nuevas_sedes += 1
        if nuevas_sedes > 0:
            db.commit()
            resultado.append(f"✅ {nuevas_sedes} sedes nuevas")
        total_cat = db.query(Catedra).count()
        if total_cat < 10:
            for codigo, nombre in CATEDRAS:
                if not db.query(Catedra).filter(Catedra.codigo == codigo).first():
                    db.add(Catedra(codigo=codigo, nombre=nombre))
            db.commit()
            resultado.append(f"✅ Cátedras: {total_cat} → {db.query(Catedra).count()}")
        else:
            resultado.append(f"OK {total_cat} cátedras ya existen")
        total_cur = db.query(Curso).count()
        if total_cur < 10:
            for sede_nombre, nombre in CURSOS:
                if not db.query(Curso).filter(Curso.nombre == nombre).first():
                    sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first()
                    db.add(Curso(nombre=nombre, sede_id=sede.id if sede else None))
            db.commit()
            resultado.append(f"✅ Cursos: {total_cur} → {db.query(Curso).count()}")
        else:
            resultado.append(f"OK {total_cur} cursos ya existen")
        total_doc = db.query(Docente).count()
        if total_doc < 5:
            for dni, nombre, apellido in DOCENTES:
                if not db.query(Docente).filter(Docente.dni == dni).first():
                    db.add(Docente(dni=dni, nombre=nombre, apellido=apellido))
            db.commit()
            resultado.append(f"✅ Docentes: {total_doc} → {db.query(Docente).count()}")
        else:
            resultado.append(f"OK {total_doc} docentes ya existen")
        # Asegurar cuatrimestres 2026-2030
        for anio in range(2026, 2031):
            for num in [1, 2]:
                nombre_c = f"{'1er' if num == 1 else '2do'} Cuatrimestre {anio}"
                if not db.query(Cuatrimestre).filter(Cuatrimestre.anio == anio, Cuatrimestre.numero == num).first():
                    db.add(Cuatrimestre(nombre=nombre_c, anio=anio, numero=num, activo=False))
        db.commit()
        resultado.append("✅ Cuatrimestres verificados (2026-2030)")
    except ImportError:
        resultado.append("⚠️ seed_data.py no encontrado")
    except Exception as e:
        resultado.append(f"❌ Seed error: {str(e)}")
    return {"resultado": resultado}

@app.get("/api/diagnostico")
def diagnostico_bd(db: Session = Depends(get_db)):
    from sqlalchemy import text, inspect
    info = {}
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        info["tablas"] = tables
        for t in tables:
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


# ==================== SEDES Y CUATRIMESTRES ====================

@app.get("/api/sedes")
def get_sedes(db: Session = Depends(get_db)):
    return [{"id": s.id, "nombre": s.nombre, "color": s.color} for s in db.query(Sede).all()]

@app.get("/api/cuatrimestres")
def get_cuatrimestres(db: Session = Depends(get_db)):
    return [{"id": c.id, "nombre": c.nombre, "anio": c.anio, "numero": c.numero, "activo": c.activo}
            for c in db.query(Cuatrimestre).order_by(Cuatrimestre.anio, Cuatrimestre.numero).all()]


# ==================== CÁTEDRAS ====================

def sort_key_codigo(codigo):
    """Ordena c.1, c.2, ... c.10, c.11, ... c.100 numéricamente"""
    m = re.match(r'c\.(\d+)', codigo or '', re.IGNORECASE)
    return int(m.group(1)) if m else 9999

@app.get("/api/catedras")
def get_catedras(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    catedras = db.query(Catedra).all()
    # Ordenar numéricamente por código
    catedras_sorted = sorted(catedras, key=lambda c: sort_key_codigo(c.codigo))
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
            # v4.0: Docentes sugeridos = ceil(inscriptos / 100)
            docentes_sugeridos = max(1, -(-inscriptos // 100)) if inscriptos > 0 else 0
            result.append({
                "id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "link_meet": getattr(cat, 'link_meet', None),
                "inscriptos": inscriptos,
                "docentes_sugeridos": docentes_sugeridos,
                "cursos_vinculados": cursos_vinc,
                "asignaciones": asigs,
            })
        except Exception:
            result.append({
                "id": cat.id, "codigo": cat.codigo, "nombre": cat.nombre,
                "link_meet": None, "inscriptos": 0, "docentes_sugeridos": 0,
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
    # v4.0: Separar inscriptos de materias inscritas
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
    # Cátedras abiertas = con al menos 1 asignación en el cuatrimestre
    catedras_abiertas_ids = set(a.catedra_id for a in asigs)
    return {
        "total_catedras": total,
        "catedras_abiertas": len(catedras_abiertas_ids),
        "total_asignaciones": len(asigs),
        "asincronicas": len([a for a in asigs if a.modalidad == 'asincronica']),
        "con_docente": len([a for a in asigs if a.docente_id and a.modalidad != 'asincronica']),
        "sin_docente": len([a for a in asigs if not a.docente_id and a.modalidad != 'asincronica']),
        "total_inscripciones": total_inscripciones,
        "alumnos_unicos": alumnos_unicos,
        "materias_con_inscriptos": materias_con_inscriptos,
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

# ===== v4.0 MEJORA 8: Materias que necesitan docente (>5 inscriptos) =====
@app.get("/api/catedras/necesitan-docente")
def get_catedras_necesitan_docente(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    # Contar inscriptos por cátedra
    q = db.query(
        Inscripcion.catedra_id,
        func.count(Inscripcion.id).label('cant_inscriptos')
    )
    if cuatrimestre_id:
        q = q.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
    q = q.group_by(Inscripcion.catedra_id).having(func.count(Inscripcion.id) > 5)
    inscriptos_por_cat = {row.catedra_id: row.cant_inscriptos for row in q.all()}

    result = []
    for cat_id, cant in inscriptos_por_cat.items():
        cat = db.query(Catedra).filter(Catedra.id == cat_id).first()
        if not cat:
            continue
        # Ver si tiene asignación con docente en este cuatrimestre
        asigs = db.query(Asignacion).filter(Asignacion.catedra_id == cat_id)
        if cuatrimestre_id:
            asigs = asigs.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
        asigs = asigs.all()
        docentes_asignados = [a for a in asigs if a.docente_id]
        docentes_sugeridos = max(1, -(-cant // 100))
        necesita = docentes_sugeridos - len(docentes_asignados)
        if necesita > 0 or len(docentes_asignados) == 0:
            docentes_nombres = []
            for a in docentes_asignados:
                if a.docente:
                    docentes_nombres.append(f"{a.docente.nombre} {a.docente.apellido}")
            result.append({
                "catedra_id": cat.id,
                "codigo": cat.codigo,
                "nombre": cat.nombre,
                "inscriptos": cant,
                "docentes_sugeridos": docentes_sugeridos,
                "docentes_asignados": len(docentes_asignados),
                "docentes_faltantes": max(0, necesita),
                "docentes_nombres": docentes_nombres,
                "tiene_asignacion": len(asigs) > 0,
            })
    # Ordenar por código numérico
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
        # v4.0 mejora 2: Permitir crear sin dia/hora (pendiente de confirmar)
        if dia and hora and modalidad != 'asincronica':
            conflict = verificar_solapamiento_catedra(cat_id, dia, hora, cuat_id, None, db)
            if conflict:
                raise HTTPException(status_code=400, detail=conflict)
        asig = Asignacion(
            catedra_id=cat_id, cuatrimestre_id=cuat_id,
            docente_id=data.get("docente_id") if data.get("docente_id") else None,
            modalidad=modalidad,
            dia=dia if dia else None,
            hora_inicio=hora if hora else None,
            hora_fin=data.get("hora_fin") if data.get("hora_fin") else None,
            sede_id=sede_id if sede_id else None,
            recibe_alumnos_presenciales=data.get("recibe_alumnos_presenciales", False),
        )
        db.add(asig)
        db.commit()
        return {"id": asig.id, "ok": True}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error creando asignación: {e}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}. Probá visitar /api/reparar primero.")

# v4.0 mejora 3: Editar asignación existente (asignar docente, cambiar datos)
@app.put("/api/asignaciones/{asignacion_id}")
def actualizar_asignacion(asignacion_id: int, data: dict, db: Session = Depends(get_db)):
    try:
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
                val = data[field]
                if field == "docente_id" and (val == "" or val == "null"):
                    val = None
                elif field in ["sede_id"] and not val:
                    val = None
                setattr(asig, field, val if val else None)
        asig.modificada = True
        db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

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
    try:
        d = db.query(Docente).filter(Docente.id == docente_id).first()
        if not d:
            raise HTTPException(status_code=404, detail="No encontrado")
        try:
            db.query(Asignacion).filter(Asignacion.docente_id == docente_id).update({"docente_id": None})
        except Exception as e:
            print(f"⚠️ Error desasignando docente de asignaciones: {e}")
            db.rollback()
        try:
            db.query(DocenteSede).filter(DocenteSede.docente_id == docente_id).delete()
        except Exception as e:
            print(f"⚠️ Error eliminando docente_sede: {e}")
            db.rollback()
        db.delete(d)
        db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error eliminando docente: {str(e)}")

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
    result = []
    for c in cursos:
        catedras_vinc = []
        try:
            for cc in (c.catedras or []):
                catedras_vinc.append({
                    "id": cc.id,
                    "catedra_id": cc.catedra_id,
                    "catedra_codigo": cc.catedra.codigo if cc.catedra else None,
                    "catedra_nombre": cc.catedra.nombre if cc.catedra else None,
                    "turno": cc.turno,
                })
        except Exception:
            pass
        result.append({
            "id": c.id, "nombre": c.nombre,
            "sede_id": c.sede_id, "sede_nombre": c.sede.nombre if c.sede else None,
            "cant_catedras": len(catedras_vinc),
            "catedras": catedras_vinc,
        })
    return result


# ==================== IMPORTACIONES ====================

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

# ===== v4.0 MEJORA 1: Apertura masiva de cátedras por cuatrimestre =====
@app.post("/api/importar/apertura-catedras")
async def importar_apertura_catedras(
    file: UploadFile = File(...),
    cuatrimestre_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Importa un Excel con cátedras a abrir en un cuatrimestre.
    Crea una asignación 'pendiente' (sin turno, sin docente, sin horario) por cada cátedra.
    Si la cátedra ya tiene asignación en ese cuatrimestre, la ignora.
    Formato: Código | Nombre (o 'c.XX Nombre' en una sola columna)
    """
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        abiertas = 0
        ya_existentes = 0
        errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if not vals or not any(vals):
                continue
            codigo = None
            nombre = None
            # Intentar leer "c.XX Nombre" en columna B (vals[1])
            for v in vals:
                m = re.match(r'^(c\.\d+)\s*(.*)', v, re.IGNORECASE)
                if m:
                    codigo = m.group(1)
                    if m.group(2):
                        nombre = m.group(2).strip()
                    break
            # Si no encontró patrón, intentar con número en col A
            if not codigo and vals[0]:
                try:
                    num = int(float(vals[0]))
                    if num > 0:
                        codigo = f"c.{num}"
                        nombre = vals[1] if len(vals) > 1 else None
                except (ValueError, TypeError):
                    pass
            if not codigo:
                continue
            # Buscar cátedra o crearla
            catedra = db.query(Catedra).filter(Catedra.codigo == codigo).first()
            if not catedra:
                if nombre:
                    catedra = Catedra(codigo=codigo, nombre=nombre)
                    db.add(catedra)
                    db.flush()
                else:
                    errores.append(f"Fila {row_num}: Cátedra {codigo} no existe y no tiene nombre para crearla")
                    continue
            # Verificar si ya tiene asignación en este cuatrimestre
            ya_tiene = db.query(Asignacion).filter(
                Asignacion.catedra_id == catedra.id,
                Asignacion.cuatrimestre_id == cuatrimestre_id
            ).first()
            if ya_tiene:
                ya_existentes += 1
                continue
            # Crear asignación pendiente (sin turno, sin docente, sin horario)
            db.add(Asignacion(
                catedra_id=catedra.id,
                cuatrimestre_id=cuatrimestre_id,
                modalidad='virtual_tm',
                docente_id=None,
                dia=None,
                hora_inicio=None,
                hora_fin=None,
                sede_id=None,
            ))
            abiertas += 1
        db.commit()
        wb.close()
        return {
            "abiertas": abiertas,
            "ya_existentes": ya_existentes,
            "errores": errores[:20]
        }
    except Exception as e:
        db.rollback()
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
        es_formato_combinado = any("apellido y nombre" in h or "apellido, nombre" in h for h in headers)
        creados = 0
        actualizados = 0
        errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if es_formato_combinado:
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

@app.post("/api/importar/catedra-cursos")
async def importar_catedra_cursos(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        creados = 0
        errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if len(vals) < 3: continue
            codigo_num = vals[0]
            materia_texto = vals[1]
            curso_nombre = vals[2]
            sede_nombre = vals[3] if len(vals) > 3 else ""
            m = re.match(r'^(c\.\d+)\s+(.+?)(?:\s*-\s*(Mañana|Noche|Virtual|Tarde))?\s*$', materia_texto, re.IGNORECASE)
            if m:
                codigo = m.group(1)
                turno = m.group(3)
            else:
                codigo = f"c.{codigo_num}" if codigo_num else None
                turno = None
            if not codigo or not curso_nombre: continue
            catedra = db.query(Catedra).filter(Catedra.codigo == codigo).first()
            if not catedra:
                errores.append(f"Fila {row_num}: Cátedra {codigo} no existe")
                continue
            curso = db.query(Curso).filter(Curso.nombre == curso_nombre).first()
            if not curso:
                sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
                curso = Curso(nombre=curso_nombre, sede_id=sede.id if sede else None)
                db.add(curso); db.flush()
            sede = db.query(Sede).filter(Sede.nombre == sede_nombre).first() if sede_nombre else None
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

@app.post("/api/importar/links-meet")
async def importar_links_meet(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        ws = wb[wb.sheetnames[0]]
        actualizados = 0
        errores = []
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            vals = [str(c).strip() if c is not None else "" for c in row]
            if len(vals) < 2: continue
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

# ===== v4.0 MEJORA 4: Importar alumnos (mejorado para archivos consolidados) =====
@app.post("/api/importar/alumnos")
async def importar_alumnos(
    file: UploadFile = File(...),
    cuatrimestre_id: int = 1,
    db: Session = Depends(get_db)
):
    try:
        content = await file.read()
        wb = load_workbook(filename=io.BytesIO(content), read_only=True)
        creados = 0
        inscripciones = 0
        errores = []
        # v4.0: Recorrer TODAS las hojas del archivo (archivo consolidado)
        for ws in wb:
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                vals = [str(c).strip() if c is not None else "" for c in row]
                if len(vals) < 4: continue
                alumno_texto = vals[1]
                dni_raw = str(vals[2]).strip() if vals[2] else ""
                materia_texto = vals[3]
                dni = re.sub(r'[.\-\s]', '', dni_raw)
                if '.' in dni:
                    try: dni = str(int(float(dni)))
                    except: pass
                if not dni or len(dni) < 6: continue
                m_nombre = re.match(r'^(.+?)\s*\(\d+\)', alumno_texto)
                nombre_completo = m_nombre.group(1).strip() if m_nombre else alumno_texto
                partes = nombre_completo.strip().split(' ')
                if len(partes) >= 2:
                    nombre = ' '.join(partes[:-1])
                    apellido = partes[-1]
                else:
                    nombre = nombre_completo
                    apellido = ""
                m_cod = re.match(r'^(c\.\d+)', materia_texto, re.IGNORECASE)
                if not m_cod:
                    errores.append(f"Hoja '{ws.title}' Fila {row_num}: no se pudo leer código de '{materia_texto[:40]}'")
                    continue
                codigo = m_cod.group(1)
                catedra = db.query(Catedra).filter(Catedra.codigo == codigo).first()
                if not catedra:
                    errores.append(f"Hoja '{ws.title}' Fila {row_num}: cátedra {codigo} no existe")
                    continue
                alumno = db.query(Alumno).filter(Alumno.dni == dni).first()
                if not alumno:
                    alumno = Alumno(dni=dni, nombre=nombre, apellido=apellido)
                    db.add(alumno)
                    db.flush()
                    creados += 1
                existe = db.query(Inscripcion).filter(
                    Inscripcion.alumno_id == alumno.id,
                    Inscripcion.catedra_id == catedra.id,
                    Inscripcion.cuatrimestre_id == cuatrimestre_id
                ).first()
                if not existe:
                    db.add(Inscripcion(
                        alumno_id=alumno.id,
                        catedra_id=catedra.id,
                        cuatrimestre_id=cuatrimestre_id
                    ))
                    inscripciones += 1
        db.commit()
        wb.close()
        return {
            "alumnos_nuevos": creados,
            "inscripciones_cargadas": inscripciones,
            "hojas_procesadas": len(wb.sheetnames) if hasattr(wb, 'sheetnames') else 1,
            "errores": errores[:20]
        }
    except Exception as e:
        db.rollback()
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
    try:
        from sqlalchemy import text
        try:
            test = db.execute(text("SELECT id, catedra_id, docente_id, dia, hora_inicio, modalidad FROM asignaciones LIMIT 1"))
        except Exception as col_err:
            print(f"⚠️ Solapamientos - columnas faltantes: {col_err}")
            db.rollback()
            return []
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
                try:
                    cat1 = a1.catedra
                    cat2 = a2.catedra
                except Exception:
                    continue
                if a1.catedra_id == a2.catedra_id:
                    solapamientos.append({
                        "tipo": "CATEDRA", "severidad": "CRITICO",
                        "mensaje": f"Cátedra {cat1.codigo if cat1 else '?'} tiene dos clases {a1.dia} {a1.hora_inicio}. Comparten link Meet.",
                        "catedra": cat1.codigo if cat1 else "?", "dia": a1.dia, "hora": a1.hora_inicio,
                    })
                elif a1.docente_id and a1.docente_id == a2.docente_id:
                    try:
                        doc = a1.docente
                        solapamientos.append({
                            "tipo": "DOCENTE", "severidad": "ALTO",
                            "mensaje": f"{doc.nombre} {doc.apellido} tiene {cat1.codigo if cat1 else '?'} y {cat2.codigo if cat2 else '?'} el {a1.dia} {a1.hora_inicio}.",
                            "docente": f"{doc.nombre} {doc.apellido}" if doc else "?", "dia": a1.dia, "hora": a1.hora_inicio,
                        })
                    except Exception:
                        pass
        return solapamientos
    except Exception as e:
        print(f"❌ Error en solapamientos: {e}")
        return []

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


# ===== v4.0 MEJORA 12: Replicar apertura de cátedras del año anterior =====
@app.post("/api/cuatrimestres/replicar")
def replicar_cuatrimestre(data: dict, db: Session = Depends(get_db)):
    origen_id = data.get("origen_id")
    destino_id = data.get("destino_id")
    if not origen_id or not destino_id:
        raise HTTPException(status_code=400, detail="Se requiere origen_id y destino_id")
    asigs_origen = db.query(Asignacion).filter(Asignacion.cuatrimestre_id == origen_id).all()
    if not asigs_origen:
        raise HTTPException(status_code=400, detail="El cuatrimestre de origen no tiene asignaciones")
    replicadas = 0
    ya_existentes = 0
    for a in asigs_origen:
        # Verificar si ya existe en destino
        ya_existe = db.query(Asignacion).filter(
            Asignacion.catedra_id == a.catedra_id,
            Asignacion.cuatrimestre_id == destino_id,
            Asignacion.modalidad == a.modalidad,
        ).first()
        if ya_existe:
            ya_existentes += 1
            continue
        nueva = Asignacion(
            catedra_id=a.catedra_id,
            cuatrimestre_id=destino_id,
            modalidad=a.modalidad,
            dia=a.dia,
            hora_inicio=a.hora_inicio,
            hora_fin=a.hora_fin,
            sede_id=a.sede_id,
            recibe_alumnos_presenciales=a.recibe_alumnos_presenciales,
            docente_id=None,  # No copiar docente, solo la estructura
        )
        db.add(nueva)
        replicadas += 1
    db.commit()
    return {"replicadas": replicadas, "ya_existentes": ya_existentes}


# ===== v4.0 MEJORA 6: Exportar con una solapa por sede + inscriptos =====
@app.get("/api/exportar/horarios")
def exportar_horarios(cuatrimestre_id: int = None, db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment

    wb = Workbook()

    q = db.query(Asignacion)
    if cuatrimestre_id:
        q = q.filter(Asignacion.cuatrimestre_id == cuatrimestre_id)
    asigs = q.all()

    # Ordenar por código numérico
    asigs_sorted = sorted(asigs, key=lambda a: sort_key_codigo(a.catedra.codigo if a.catedra else 'c.9999'))

    # Contar inscriptos por cátedra
    inscriptos_map = {}
    q_insc = db.query(Inscripcion.catedra_id, func.count(Inscripcion.id).label('cnt'))
    if cuatrimestre_id:
        q_insc = q_insc.filter(Inscripcion.cuatrimestre_id == cuatrimestre_id)
    for row in q_insc.group_by(Inscripcion.catedra_id).all():
        inscriptos_map[row.catedra_id] = row.cnt

    # Colores por sede
    SEDE_FILL = {
        'Avellaneda': '3B82F6',
        'Caballito': '10B981',
        'Vicente López': 'F59E0B',
        'Online - Interior': '8B5CF6',
    }

    header_style = lambda color='1D6F42': (Font(bold=True, color="FFFFFF", size=11), PatternFill("solid", fgColor=color))
    headers = ["#", "Código", "Cátedra", "Inscriptos", "Docente", "Modalidad", "Día", "Hora", "Sede", "Recibe Presenciales"]

    def write_sheet(ws, title, asigs_list, color='1D6F42'):
        ws.title = title
        ws.append(headers)
        hf, hfill = header_style(color)
        for cell in ws[1]:
            cell.font = hf
            cell.fill = hfill
            cell.alignment = Alignment(horizontal="center")
        for i, a in enumerate(asigs_list, 1):
            cat_inscriptos = inscriptos_map.get(a.catedra_id, 0) if a.catedra else 0
            ws.append([
                i,
                a.catedra.codigo if a.catedra else "",
                a.catedra.nombre if a.catedra else "",
                cat_inscriptos,
                f"{a.docente.nombre} {a.docente.apellido}" if a.docente else "Sin asignar",
                a.modalidad or "",
                a.dia or "Pendiente",
                a.hora_inicio or "Pendiente",
                a.sede.nombre if a.sede else "Remoto",
                "Sí" if a.recibe_alumnos_presenciales else "No",
            ])
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 10
        ws.column_dimensions['C'].width = 32
        ws.column_dimensions['D'].width = 12
        ws.column_dimensions['E'].width = 30
        ws.column_dimensions['F'].width = 15
        ws.column_dimensions['G'].width = 12
        ws.column_dimensions['H'].width = 10
        ws.column_dimensions['I'].width = 20
        ws.column_dimensions['J'].width = 18

    # Hoja 1: Todas las asignaciones
    ws1 = wb.active
    write_sheet(ws1, "Todas las sedes", asigs_sorted)

    # Una hoja por cada sede
    sedes_db = db.query(Sede).all()
    for sede in sedes_db:
        asigs_sede = [a for a in asigs_sorted if a.sede_id == sede.id]
        if not asigs_sede:
            continue
        color = SEDE_FILL.get(sede.nombre, '6B7280')
        ws = wb.create_sheet()
        write_sheet(ws, sede.nombre[:31], asigs_sede, color)

    # Hoja para remotos (sin sede)
    asigs_remotos = [a for a in asigs_sorted if not a.sede_id]
    if asigs_remotos:
        ws = wb.create_sheet()
        write_sheet(ws, "Remotos", asigs_remotos, '6B7280')

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    nombre = f"IEA_Horarios{'_Cuat' + str(cuatrimestre_id) if cuatrimestre_id else '_Todos'}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre}"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
