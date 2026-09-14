"""Planning derives demand and schedules from catalog links and the selected period."""
from collections import defaultdict
import re
from sqlalchemy import text
from app.academic_store import resolved_catalog, offering, find_plan, reject
from app.models.models import Asignacion, Cuatrimestre, Inscripcion, Catedra, Docente, DocenteSede, Sede
from app.enrollment_plans import demand_breakdown

DAYS = ("Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo")

def minutes(value):
    if not isinstance(value,str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",value): return None
    h,m=map(int,value.split(":")); return h*60+m

def hour(value):
    return f"{value//60:02d}:{value%60:02d}"

def interval(assignment, duration):
    start=minutes(assignment.hora_inicio)
    if start is None or assignment.dia not in DAYS or assignment.modalidad=="asincronica": return None
    end=minutes(assignment.hora_fin) if assignment.hora_fin else start+duration
    return (start,end) if end is not None and start<end<1440 else None

def overlaps(a,b):
    return a[0]<b[1] and b[0]<a[1]

def require_period(db, ident):
    if not db.get(Cuatrimestre,ident): reject("Cuatrimestre no encontrado",404)

def demand(db, period):
    # A student enrolled twice in the same chair is counted once.
    result=defaultdict(set)
    for student,chair in db.query(Inscripcion.alumno_id,Inscripcion.catedra_id).filter_by(cuatrimestre_id=period):
        result[chair].add(student)
    return result

def planned_subjects(catalog, document):
    result=[]
    for career in catalog["careers"]:
        for plan in career["planes"]:
            selected=set(document["plans"].get(plan["id"],[]))
            for subject in plan["materias"]:
                if subject["id"] in selected:
                    result.append((plan,subject))
    return result

def scheduling_context(db,institution,period):
    require_period(db,period)
    catalog,revision=resolved_catalog(db,institution.id)
    document,offer_revision=offering(db,institution.id,period)
    chairs={c.id:c for c in db.query(Catedra).all()}
    assignments=db.query(Asignacion).filter_by(cuatrimestre_id=period).all()
    return {"catalog":catalog,"revision":revision,"offering":document,"offer_revision":offer_revision,
            "chairs":chairs,"assignments":assignments,"demand":demand(db,period),
            "planned":planned_subjects(catalog,document)}

def view_plan(db,institution,period,plan_id):
    ctx=scheduling_context(db,institution,period)
    career,plan=find_plan(ctx["catalog"],plan_id)
    selected=set(ctx["offering"]["plans"].get(plan_id,[]))
    breakdown=demand_breakdown(db,institution.id,period,career['id'],plan_id,(ctx['catalog'],ctx['revision']))
    rows=[]
    for s in plan["materias"]:
        chair=ctx["chairs"].get(s.get("catedra_id"))
        total=len(ctx["demand"].get(chair.id,set())) if chair else None
        current=[a for a in ctx["assignments"] if chair and a.catedra_id==chair.id]
        rows.append({**s,"ofertada":s["id"] in selected,
            "catedra":{"id":chair.id,"codigo":chair.codigo,"nombre":chair.nombre} if chair else None,
            "inscriptos":total,
            "detalle_inscriptos":breakdown.get(chair.id,{}) if chair else {},
            "criterio":"ASOCIAR CÁTEDRA" if chair is None else "ABRIR" if institution.requiere_docente(total) else "REVISAR APERTURA" if total else "SIN ALUMNOS",
            "docentes_requeridos":institution.docentes_sugeridos(total) if total is not None else None,
            "asignaciones":[{"id":a.id,"docente_id":a.docente_id,"docente":f"{a.docente.apellido}, {a.docente.nombre}" if a.docente else None,
                            "dia":a.dia,"hora_inicio":a.hora_inicio,"hora_fin":a.hora_fin,"sede_id":a.sede_id,"modalidad":a.modalidad,
                            "comision":a.comision} for a in current]})
    unique_chairs={s["catedra"]["id"] for s in rows if s["ofertada"] and s["catedra"]}
    return {"plan":{k:v for k,v in plan.items() if k not in ("materias","modulos")},
            "carrera":career["nombre"],"revision":ctx["revision"],"oferta_revision":ctx["offer_revision"],
            "cuatrimestre_id":period,"materias":rows,
            "estado_oferta":"configurada" if plan_id in ctx['offering']['plans'] else "sin_configurar",
            "demanda_catedras":sum(len(ctx["demand"].get(c,set())) for c in unique_chairs),
            "alumnos_distintos":len(set().union(*(ctx["demand"].get(c,set()) for c in unique_chairs))),
            "alcance_inscriptos":"Cátedra y período; incluye alumnos de todos los planes y sedes. No es un conteo por plan."}

def teacher_context(db):
    teachers={d.id:d for d in db.query(Docente).all()}
    extras={r[0]:{"refs":{x.strip() for x in (r[1] or "").split(",") if x.strip()},"activo":r[2] is not False}
            for r in db.execute(text("SELECT id,catedras_referencia,activo FROM docentes"))}
    availability=defaultdict(set)
    for did,day,time in db.execute(text("SELECT docente_id,dia,hora FROM docente_disponibilidad WHERE disponible = TRUE")):
        start=minutes(time)
        if day in DAYS and start is not None: availability[did].add((day,start))
    campuses=defaultdict(set)
    for row in db.query(DocenteSede).all(): campuses[row.docente_id].add(row.sede_id)
    return teachers,extras,availability,campuses

def candidate_reasons(ctx,institution,chair,teacher,day,start,end,availability,extras,campuses,campus,mode,exclude_id=None):
    reasons=[]
    extra=extras.get(teacher.id,{})
    if not extra.get("activo",True): reasons.append("Docente inactivo")
    cutoff=institution.corte_turno_minutos
    if mode=="virtual_tm" and end>cutoff: reasons.append("La clase excede el turno de mañana")
    if mode=="virtual_tn" and start<cutoff: reasons.append("La clase comienza antes del turno de noche")
    if chair.codigo not in extra.get("refs",set()): reasons.append("La cátedra no está habilitada en la ficha docente")
    if mode=="presencial" and campus not in campuses.get(teacher.id,set()): reasons.append("Docente sin disponibilidad en esa sede")
    # Every half-hour cell touched by the class must be available.
    if any((day,t) not in availability.get(teacher.id,set()) for t in range((start//30)*30,end,30)):
        reasons.append("La disponibilidad no cubre toda la clase")
    groups={(p["id"],s.get("anio"),s.get("cuatrimestre")) for p,s in ctx["planned"] if s.get("catedra_id")==chair.id}
    conflicting_chairs={s.get("catedra_id") for p,s in ctx["planned"]
                       if (p["id"],s.get("anio"),s.get("cuatrimestre")) in groups and s.get("catedra_id")!=chair.id}
    for a in ctx["assignments"]:
        if a.id==exclude_id or a.dia!=day: continue
        span=interval(a,institution.duracion_clase_minutos)
        if span is None or not overlaps((start,end),span): continue
        if a.docente_id==teacher.id: reasons.append("Superposición del docente")
        if a.catedra_id in conflicting_chairs: reasons.append("Superposición de materias del mismo año y cuatrimestre del plan")
    return list(dict.fromkeys(reasons))

def suggestions(db,institution,period,plan_id,subject_id,campus=None,mode="presencial"):
    ctx=scheduling_context(db,institution,period)
    _,plan=find_plan(ctx["catalog"],plan_id)
    subject=next((s for s in plan["materias"] if s["id"]==subject_id),None)
    if not subject: reject("Materia no encontrada",404)
    if subject_id not in ctx["offering"]["plans"].get(plan_id,[]): reject("Agregá esta materia a la oferta del período")
    chair=ctx["chairs"].get(subject.get("catedra_id"))
    if not chair: reject("Confirmá primero la asociación con una cátedra")
    if mode not in ("presencial","virtual_tm","virtual_tn"): reject("Modalidad no admitida")
    if campus is not None and not db.get(Sede,campus): reject("Sede no encontrada",404)
    if mode=="presencial" and campus is None: reject("Seleccioná la sede presencial")
    total=len(ctx["demand"].get(chair.id,set()))
    if not institution.requiere_docente(total): return {"candidatos":[],"motivo":"La demanda no alcanza el mínimo institucional","inscriptos":total}
    teachers,extras,availability,campuses=teacher_context(db)
    result=[]
    for did,teacher in teachers.items():
        if chair.codigo not in extras.get(did,{}).get("refs",set()): continue
        for day,start in sorted(availability.get(did,set()),key=lambda x:(DAYS.index(x[0]),x[1])):
            end=start+institution.duracion_clase_minutos
            if end>=1440: continue
            if not candidate_reasons(ctx,institution,chair,teacher,day,start,end,availability,extras,campuses,campus,mode):
                load=sum((span[1]-span[0]) for a in ctx["assignments"] if a.docente_id==did
                         if (span:=interval(a,institution.duracion_clase_minutos)))
                result.append({"docente_id":did,"docente":f"{teacher.apellido}, {teacher.nombre}","dia":day,
                    "hora_inicio":hour(start),"hora_fin":hour(end),"minutos_asignados":load})
    result.sort(key=lambda x:(x["minutos_asignados"],x["docente"],DAYS.index(x["dia"]),x["hora_inicio"]))
    return {"candidatos":result[:60],"total_opciones":len(result),"inscriptos":total,
            "motivo":None if result else "No hay docentes habilitados con una franja completa libre para esta sede"}

def save_assignment(db,institution,period,plan_id,subject_id,payload):
    # Serialize writes from this workflow; the legacy APIs still need general concurrency control.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"),{"key":period})
    ctx=scheduling_context(db,institution,period)
    if payload.get("catalog_revision")!=ctx["revision"] or payload.get("oferta_revision")!=ctx["offer_revision"]:
        reject("El plan o su oferta cambiaron. Recargá antes de asignar.",409)
    _,plan=find_plan(ctx["catalog"],plan_id)
    subject=next((s for s in plan["materias"] if s["id"]==subject_id),None)
    if not subject or subject_id not in ctx["offering"]["plans"].get(plan_id,[]): reject("Materia fuera de la oferta seleccionada")
    chair=ctx["chairs"].get(subject.get("catedra_id"))
    if not chair: reject("La materia necesita una cátedra confirmada")
    if not institution.requiere_docente(len(ctx["demand"].get(chair.id,set()))): reject("La demanda no alcanza el mínimo institucional")
    ident=payload.get("asignacion_id")
    assignment=db.get(Asignacion,ident) if ident is not None else None
    if ident is not None and (not assignment or assignment.cuatrimestre_id!=period or assignment.catedra_id!=chair.id):
        reject("La asignación no pertenece a esta materia y período",404)
    if assignment:
        current={k:getattr(assignment,k) for k in ("docente_id","dia","hora_inicio","hora_fin","sede_id","modalidad","comision")}
        if payload.get("previous")!=current: reject("La asignación cambió. Recargá antes de editar.",409)
    day=payload.get("dia"); start=minutes(payload.get("hora_inicio")); end=minutes(payload.get("hora_fin"))
    if day not in DAYS or start is None or end is None or not start<end: reject("Indicá un día y un intervalo horario válidos")
    campus=payload.get("sede_id"); mode=payload.get("modalidad")
    if mode not in ("presencial","virtual_tm","virtual_tn"): reject("Seleccioná una modalidad de clase")
    if campus is not None and (type(campus) is not int or not db.get(Sede,campus)): reject("Sede inválida")
    if mode=="presencial" and campus is None: reject("La clase presencial necesita sede")
    did=payload.get("docente_id")
    if type(did) is not int: reject("Seleccioná un docente")
    teachers,extras,availability,campuses=teacher_context(db)
    teacher=teachers.get(did)
    if not teacher: reject("Docente no encontrado",404)
    reasons=candidate_reasons(ctx,institution,chair,teacher,day,start,end,availability,extras,campuses,campus,mode,ident)
    if reasons: reject("; ".join(reasons))
    commission=payload.get("comision") or None
    if commission is not None and (not isinstance(commission,str) or len(commission)>100): reject("Comisión inválida")
    for a in ctx["assignments"]:
        if a.id!=ident and (a.catedra_id,a.dia,a.hora_inicio,a.hora_fin,a.sede_id,a.comision)==(chair.id,day,hour(start),hour(end),campus,commission):
            reject("Esta clase ya está asignada; editá la existente",409)
    if assignment is None:
        assignment=Asignacion(catedra_id=chair.id,cuatrimestre_id=period)
        db.add(assignment)
    assignment.docente_id=did;assignment.dia=day
    assignment.hora_inicio=hour(start);assignment.hora_fin=hour(end)
    assignment.sede_id=campus;assignment.modalidad=mode;assignment.comision=commission
    assignment.modificada=True
    db.commit()
    return {"ok":True,"id":assignment.id}
