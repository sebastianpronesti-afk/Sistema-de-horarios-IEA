"""Optional plan confirmations; imported career/course information stays intact.

Documents are scoped to one course or student/course/period. No enrollment is
copied and no plan is inferred. Source fingerprints guard against reused IDs.
"""
from collections import defaultdict
import hashlib
import json
from sqlalchemy import text
from app.academic_store import AcademicDocument, academic_catalog, find_career, find_plan, write_document, reject
from app.models.models import Alumno, Curso, Cuatrimestre, Inscripcion


def token(*parts):
    return hashlib.sha256(json.dumps(parts,ensure_ascii=False).encode()).hexdigest()


def prefix(institution,period):
    return f"enrollment:{institution}:{period}:"


def course_key(institution,period,course):
    return prefix(institution,period)+f"course:{course}"


def student_key(institution,period,course,student):
    return prefix(institution,period)+f"student:{course}:{student}"


def context(db,institution,period,catalog=None):
    if not db.get(Cuatrimestre,period): reject("Cuatrimestre no encontrado",404)
    if catalog is None: catalog,revision=academic_catalog(db,institution)
    else: catalog,revision=catalog
    careers={c['id']:c for c in catalog['careers']}
    plans={p['id']:c['id'] for c in catalog['careers'] for p in c['planes']}
    documents={r.key:(json.loads(r.content),r.revision) for r in db.query(AcademicDocument).filter(
        AcademicDocument.key.startswith(prefix(institution,period),autoescape=True))}
    groups={}
    query=db.query(Inscripcion,Alumno,Curso,text('inscripciones.curso_nombre')).join(Alumno,Alumno.id==Inscripcion.alumno_id).outerjoin(
        Curso,Curso.id==Inscripcion.curso_id).filter(Inscripcion.cuatrimestre_id==period)
    course_names={}
    for enrollment,student,course,raw_course in query:
        # IEA's importer preserves career in curso_nombre without a Curso FK.
        # Negative IDs identify exact source-name groups, never catalog plans.
        informed=(raw_course or '').strip()
        cid=-(int(token('source-course',informed)[:12],16)+1) if informed else course.id if course else 0
        course_name=informed or (course.nombre if course else 'Carrera no informada en la inscripción')
        if cid in course_names and course_names[cid]!=course_name:
            reject('No se pudieron distinguir los cursos informados. Revisá el origen.',503)
        course_names[cid]=course_name
        key=(cid,student.id)
        if key not in groups:
            source=token(period,cid,course_name,student.id,student.dni)
            mapping,mapping_revision=documents.get(course_key(institution,period,cid),({},0))
            mapping_valid=mapping.get('source_token')==token(period,cid,course_name) and mapping.get('career_id') in careers
            career_id=mapping.get('career_id') if mapping_valid else None
            saved,saved_revision=documents.get(student_key(institution,period,cid,student.id),({},0))
            valid=(saved.get('source_token')==source and saved.get('course_revision')==mapping_revision
                   and saved.get('career_id')==career_id and career_id is not None)
            plan=saved.get('plan_id') if valid and plans.get(saved.get('plan_id'))==career_id else None
            groups[key]={'alumno_id':student.id,'nombre':f"{student.apellido or ''}, {student.nombre or ''}".strip(', '),
                'dni':student.dni,'curso_id':cid,'carrera_informada':course_name,'career_id':career_id,
                'plan_id':plan,'estado':'confirmado' if plan else 'pendiente_validar',
                'revision':saved_revision,'course_revision':mapping_revision,'source_token':source,
                'nota':saved.get('nota','') if saved.get('source_token')==source else '',
                'confirmacion_a_revisar':bool(saved.get('plan_id') and not plan),
                'catedra_ids':set()}
        groups[key]['catedra_ids'].add(enrollment.catedra_id)
    courses={}
    for row in groups.values():
        cid=row['curso_id']
        if cid not in courses:
            courses[cid]={'curso_id':cid,'carrera_informada':row['carrera_informada'],
                'career_id':row['career_id'],'revision':row['course_revision'],
                'source_token':token(period,cid,row['carrera_informada']),
                'alumnos':0,'planes_confirmados':0,'planes_pendientes':0}
        courses[cid]['alumnos']+=1
        courses[cid]['planes_confirmados' if row['plan_id'] else 'planes_pendientes']+=1
    return {'catalog':catalog,'catalog_revision':revision,'groups':groups,'courses':courses}


def course_index(db,institution,period):
    ctx=context(db,institution,period)
    return {'catalog_revision':ctx['catalog_revision'],
            'courses':sorted(ctx['courses'].values(),key=lambda c:c['carrera_informada'].casefold()),
            'careers':[{'id':c['id'],'nombre':c['nombre'],'planes':[
                {k:p.get(k) for k in ('id','etiqueta','resolucion','jurisdiccion','modalidad')} for p in c['planes']
            ]} for c in ctx['catalog']['careers']],
            'alcance':'La carrera informada se conserva. El plan es opcional y requiere confirmación; no se deduce por materias.'}


def students(db,institution,period,course,query='',pending_only=False,offset=0,limit=50):
    ctx=context(db,institution,period)
    if course not in ctx['courses']: reject('No hay inscripciones de ese curso en este período',404)
    rows=[r for r in ctx['groups'].values() if r['curso_id']==course and
          (not pending_only or not r['plan_id']) and query.casefold() in (r['nombre']+' '+r['dni']).casefold()]
    rows.sort(key=lambda r:(r['nombre'].casefold(),r['alumno_id']))
    return {'course':ctx['courses'][course],'catalog_revision':ctx['catalog_revision'],'total':len(rows),
            'rows':[{**r,'catedra_ids':sorted(r['catedra_ids'])} for r in rows[offset:offset+limit]]}


def save_course(db,institution,period,course,payload):
    ctx=context(db,institution,period)
    current=ctx['courses'].get(course)
    if current is None: reject('No hay inscripciones de ese curso en este período',404)
    if payload.get('catalog_revision')!=ctx['catalog_revision'] or payload.get('source_token')!=current['source_token']:
        reject('Los datos de origen o el catálogo cambiaron. Recargá antes de guardar.',409)
    if payload.get('revision')!=current['revision']: reject('La asociación cambió. Recargá antes de guardar.',409)
    ident=payload.get('career_id')
    if ident is not None: find_career(ctx['catalog'],ident)
    # A null-course group may contain several careers: never map it as one career.
    if course==0 and ident is not None: reject('Las inscripciones sin curso no pueden asociarse juntas a una carrera')
    revision=write_document(db,course_key(institution,period,course),current['revision'],
        {'career_id':ident,'source_token':current['source_token']},'enrollment_course')
    return {'ok':True,'revision':revision}


def save_student(db,institution,period,course,student,payload):
    ctx=context(db,institution,period)
    row=ctx['groups'].get((course,student))
    if row is None: reject('El alumno no tiene inscripciones en ese curso y período',404)
    if (payload.get('catalog_revision')!=ctx['catalog_revision'] or
        payload.get('course_revision')!=row['course_revision'] or payload.get('source_token')!=row['source_token']):
        reject('La carrera, el catálogo o los datos de origen cambiaron. Recargá antes de guardar.',409)
    plan_id=payload.get('plan_id')
    if plan_id is not None:
        career,_=find_plan(ctx['catalog'],plan_id)
        if career['id']!=row['career_id']: reject('Seleccioná un plan de la carrera asociada')
    note=payload.get('nota','')
    if not isinstance(note,str) or len(note)>1000: reject('La nota admite hasta 1000 caracteres')
    revision=write_document(db,student_key(institution,period,course,student),payload.get('revision'),
        {'career_id':row['career_id'],'plan_id':plan_id,'nota':note.strip(),
         'source_token':row['source_token'],'course_revision':row['course_revision']},'enrollment_plan')
    return {'ok':True,'revision':revision}


def demand_breakdown(db,institution,period,career_id,plan_id,catalog=None):
    ctx=context(db,institution,period,catalog)
    buckets=defaultdict(lambda:{k:set() for k in ('carrera','plan_confirmado','plan_pendiente','carrera_sin_asociar')})
    for row in ctx['groups'].values():
        for chair in row['catedra_ids']:
            b=buckets[chair];student=row['alumno_id']
            if row['career_id']==career_id:
                b['carrera'].add(student)
                if row['plan_id']==plan_id: b['plan_confirmado'].add(student)
                elif row['plan_id'] is None: b['plan_pendiente'].add(student)
            elif row['career_id'] is None: b['carrera_sin_asociar'].add(student)
    # A duplicate imported registration must not make a confirmed student pending.
    for b in buckets.values(): b['plan_pendiente']-=b['plan_confirmado']
    return {chair:{k:len(v) for k,v in bucket.items()} for chair,bucket in buckets.items()}
