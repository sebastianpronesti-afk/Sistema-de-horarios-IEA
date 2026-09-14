"""Persistent academic edits and explicit offerings; source catalog remains intact."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.exc import IntegrityError
from app.database import Base
from app.curriculum import load_catalog, validate_catalog, Reconciler
from app.models.models import Catedra

class AcademicDocument(Base):
    __tablename__ = "academic_documents"
    key = Column(String(200), primary_key=True)
    revision = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)

class AcademicChange(Base):
    __tablename__ = "academic_changes"
    id = Column(String(36), primary_key=True)
    document_key = Column(String(200), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    created_at = Column(String(40), nullable=False)
    action = Column(String(100), nullable=False)
    previous_content = Column(Text, nullable=False)

def reject(message, status=422):
    raise HTTPException(status, message)

def read_document(db, key, fallback):
    row = db.get(AcademicDocument, key)
    return (json.loads(row.content), row.revision) if row else (deepcopy(fallback()), 0)

def write_document(db, key, expected, content, action):
    if type(expected) is not int or expected < 0:
        reject("Recargá los datos antes de guardar", 409)
    encoded = json.dumps(content, ensure_ascii=False)
    if len(encoded.encode()) > 16 * 1024 * 1024:
        reject("El catálogo excede el tamaño admitido")
    previous = db.get(AcademicDocument, key)
    old = previous.content if previous else "null"
    try:
        if expected == 0:
            if previous: reject("Otra persona modificó estos datos. Recargá antes de guardar.", 409)
            db.add(AcademicDocument(key=key, revision=1, content=encoded))
            db.flush()
        else:
            changed = db.query(AcademicDocument).filter_by(key=key, revision=expected).update(
                {"content": encoded, "revision": expected + 1}, synchronize_session=False)
            if changed != 1:
                db.rollback()
                reject("Otra persona modificó estos datos. Recargá antes de guardar.", 409)
        db.add(AcademicChange(id=str(uuid4()), document_key=key, revision=expected+1,
            created_at=datetime.now(timezone.utc).isoformat(), action=action, previous_content=old))
        db.commit()
    except IntegrityError:
        db.rollback()
        reject("Otra persona guardó cambios. Recargá antes de continuar.", 409)
    return expected + 1

def academic_catalog(db, institution_id):
    return read_document(db, "catalog:"+institution_id, lambda: load_catalog(institution_id))

def find_plan(catalog, ident):
    for career in catalog["careers"]:
        for plan in career["planes"]:
            if plan["id"] == ident:
                return career, plan
    reject("Plan no encontrado", 404)

def find_career(catalog, ident):
    for career in catalog["careers"]:
        if career["id"] == ident: return career
    reject("Carrera no encontrada", 404)

def validate_graph(plan):
    subjects = {s["id"]:s for s in plan["materias"]}
    graph = {}
    for ident, subject in subjects.items():
        refs = subject.get("correlativa_ids")
        if refs is None: continue  # Legacy text is evidence, not an inferred graph.
        if not isinstance(refs,list) or any(not isinstance(x,str) for x in refs):
            reject("Seleccioná las correlatividades dentro del plan")
        if len(set(refs)) != len(refs) or ident in refs or any(x not in subjects for x in refs):
            reject("Una correlatividad debe ser otra materia del mismo plan")
        graph[ident] = refs
    visiting, done = set(), set()
    def visit(ident):
        if ident in visiting: reject("Las correlatividades forman un ciclo")
        if ident in done: return
        visiting.add(ident)
        for ref in graph.get(ident,[]): visit(ref)
        visiting.remove(ident); done.add(ident)
    for ident in graph: visit(ident)

def reconciler(db):
    return Reconciler([{"id":c.id,"codigo":c.codigo,"nombre":c.nombre} for c in db.query(Catedra).all()])

def validate_subject(db, subject, changes):
    allowed = {"nombre","anio","cuatrimestre","catedra_id","correlativa_ids","revision_nota"}
    if set(changes) - allowed: reject("La edición contiene campos no admitidos")
    for field in ("anio","cuatrimestre"):
        if field in changes:
            value = changes[field]
            if value is not None and (type(value) is not int or value < 1 or value > 50):
                reject("Año y cuatrimestre deben ser enteros positivos")
    if "nombre" in changes and (not isinstance(changes["nombre"],str) or not changes["nombre"].strip()):
        reject("La materia necesita un nombre")
    if "catedra_id" in changes:
        ident = changes["catedra_id"]
        if ident is not None and (type(ident) is not int or not db.get(Catedra,ident)):
            reject("Seleccioná una cátedra existente")
    if "revision_nota" in changes and (not isinstance(changes["revision_nota"],str) or len(changes["revision_nota"])>2000):
        reject("La nota de revisión admite hasta 2000 caracteres")
    subject.update(changes)
    if "nombre" in changes: subject["nombre"] = subject["nombre"].strip()

def edit_catalog(db, institution_id, expected, operation, payload):
    catalog, revision = academic_catalog(db,institution_id)
    if revision != expected: reject("El catálogo cambió. Recargá antes de guardar.",409)
    if operation == "plan":
        _, plan = find_plan(catalog,payload["plan_id"])
        changes = payload.get("changes",{})
        allowed = {"etiqueta","nombre_oficial","resolucion","modalidad","jurisdiccion","titulo","situacion","nota_vigencia","inicio_informado"}
        if set(changes)-allowed: reject("Campos del plan no admitidos")
        if changes.get("modalidad") not in (None,"","presencial","distancia"):
            reject("Modalidad inválida")
        plan.update(changes)
    elif operation == "subject":
        _,plan = find_plan(catalog,payload["plan_id"])
        subject = next((s for s in plan["materias"] if s["id"]==payload["subject_id"]),None)
        if not subject: reject("Materia no encontrada en el plan",404)
        validate_subject(db,subject,payload.get("changes",{}))
        validate_graph(plan)
    elif operation == "move":
        career = find_career(catalog,payload["career_id"])
        target_career,plan = find_plan(catalog,payload["plan_id"])
        if target_career["id"] != career["id"]: reject("Elegí un plan de la misma carrera")
        subject = next((s for s in career.get("materias_sin_plan",[]) if s["id"]==payload["subject_id"]),None)
        if not subject: reject("Materia pendiente no encontrada",404)
        validate_subject(db,subject,payload.get("changes",{}))
        plan["materias"].append(subject)
        career["materias_sin_plan"].remove(subject)
        validate_graph(plan)
    elif operation == "new_plan":
        career = find_career(catalog,payload["career_id"])
        plan = {"id":str(uuid4()),"carrera_id":career["id"],"etiqueta":"Plan nuevo",
                "nombre_oficial":"","resolucion":"","modalidad":"","jurisdiccion":"",
                "titulo":"","situacion":"por_confirmar","inicio_informado":None,
                "nota_vigencia":"","materias":[],"modulos":[],"observaciones":[]}
        career["planes"].append(plan)
    elif operation == "new_subject":
        _,plan = find_plan(catalog,payload["plan_id"])
        subject={"id":str(uuid4()),"nombre":"Materia nueva","codigo_archivo":"",
                 "anio":None,"cuatrimestre":None,"correlatividades":"",
                 "correlativa_ids":[],"catedra_id":None,"observaciones":[]}
        validate_subject(db,subject,payload.get("changes",{}))
        plan["materias"].append(subject)
        validate_graph(plan)
    else: reject("Operación no admitida")
    try: validate_catalog(catalog,institution_id)
    except ValueError as exc: reject(str(exc))
    revision=write_document(db,"catalog:"+institution_id,expected,catalog,operation)
    return {"ok":True,"revision":revision}

def resolved_catalog(db,institution_id):
    catalog,revision=academic_catalog(db,institution_id)
    match=reconciler(db)
    for career in catalog["careers"]:
        for plan in career["planes"]:
            for subject in plan["materias"]:
                if "catedra_id" not in subject:
                    linked=match.subject(subject)["vinculo"]["catedra"]
                    subject["catedra_id"]=linked["id"] if linked else None
    return catalog,revision

def offering(db,institution_id,period_id):
    return read_document(db,f"offering:{institution_id}:{period_id}",lambda:{"plans":{}})

def save_offering(db,institution_id,period_id,plan_id,expected,subject_ids,catalog_revision):
    catalog,current_revision=resolved_catalog(db,institution_id)
    if catalog_revision!=current_revision: reject('El plan cambió. Recargá antes de configurar su oferta.',409)
    _,plan=find_plan(catalog,plan_id)
    if not isinstance(subject_ids,list) or any(not isinstance(x,str) for x in subject_ids):
        reject("Seleccioná las materias a ofrecer")
    subjects={s["id"]:s for s in plan["materias"]}
    if len(set(subject_ids))!=len(subject_ids) or any(x not in subjects for x in subject_ids):
        reject("La oferta debe contener materias de este plan, sin duplicados")
    for ident in subject_ids:
        s=subjects[ident]
        if not s.get("anio") or not s.get("cuatrimestre") or not s.get("catedra_id") or not db.get(Catedra,s["catedra_id"]):
            reject("Completá año, cuatrimestre y asociación confirmada antes de ofrecer una materia")
    document,revision=offering(db,institution_id,period_id)
    if revision!=expected: reject("La oferta cambió. Recargá antes de guardar.",409)
    document["plans"][plan_id]=subject_ids
    return {"ok":True,"revision":write_document(db,f"offering:{institution_id}:{period_id}",expected,document,"offering")}
