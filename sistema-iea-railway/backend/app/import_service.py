"""Preview, scoped reconciliation and reversible transactions for academic files."""
from collections import Counter
from copy import deepcopy
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException
from sqlalchemy import text
from app.import_adapters import parse_file, norm, code, clock, dni, FIELDS
from app.institution import INSTITUCION
from app.identity import teacher_id, document_key, code_key, full_name, name_key

TABLES = ('alumnos', 'asignaciones', 'catedra_curso', 'catedra_dictado', 'catedras',
          'cuatrimestres', 'cursos', 'docente_alias', 'docente_disponibilidad',
          'docente_sede', 'docentes', 'inscripciones', 'plan_carrera', 'sedes')
WRITABLE = {'alumnos', 'docentes', 'asignaciones', 'inscripciones', 'plan_carrera', 'catedras', 'catedra_dictado'}
TARGET = {'horarios':'asignaciones', 'inscripciones':'inscripciones', 'plan':'plan_carrera'}
TOKEN_KEY = os.environ.get('IMPORT_PREVIEW_SECRET', '').encode() or secrets.token_bytes(32)
DAY_NAMES = {norm(day):day for day in ('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo')}
FOREIGN_KEYS = {'alumno_id':'alumnos', 'docente_id':'docentes', 'catedra_id':'catedras'}


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def digest(value): return hashlib.sha256(json_text(value).encode()).hexdigest()


def read_state(db):
    return {table:[dict(row._mapping) for row in db.execute(text(f'SELECT * FROM {table} ORDER BY id'))]
            for table in TABLES}


def lock_state(db):
    # PostgreSQL holds these locks until commit/rollback, including against old writers.
    # Deliberately conservative for the current single-institution deployment.
    db.execute(text('LOCK TABLE ' + ', '.join(TABLES) + ' IN SHARE ROW EXCLUSIVE MODE'))


def token_for(revision):
    issued = str(int(time.time()))
    signature = hmac.new(TOKEN_KEY, f'{issued}:{revision}'.encode(), hashlib.sha256).hexdigest()
    return f'{issued}.{signature}'


def check_token(token, revision):
    try:
        issued, signature = token.split('.', 1)
        age = time.time() - int(issued)
        expected = hmac.new(TOKEN_KEY, f'{issued}:{revision}'.encode(), hashlib.sha256).hexdigest()
        if not 0 <= age <= 1800 or not hmac.compare_digest(signature, expected): raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(409, 'La vista previa venció o cambiaron los datos, el archivo o las opciones. Volvé a analizar antes de confirmar.')


def boolean(value):
    if isinstance(value, bool): return value
    if norm(value) in ('true','1','si'): return True
    if norm(value) in ('false','0','no',''): return False
    raise ValueError('El valor debe ser Sí o No')


class Planner:
    def __init__(self, state, kind, period, campus, mode):
        if kind not in TARGET: raise ValueError('Tipo de importación desconocido')
        if mode not in ('actualizar','reemplazar'): raise ValueError('Elegí actualizar o reemplazar')
        if campus is None or campus < 0: raise ValueError('Elegí una sede o Todas las sedes')
        if campus and not any(s['id']==campus for s in state['sedes']): raise ValueError('La sede no existe')
        if kind != 'plan' and not any(p['id']==period for p in state['cuatrimestres']):
            raise ValueError('Elegí un período existente')
        if kind == 'plan' and period is not None:
            raise ValueError('El plan de carrera es un molde compartido; no pertenece a un período')
        self.state, self.kind, self.period, self.campus, self.mode = state, kind, period, campus, mode
        self.changes, self.errors, self.warnings, self.records = {}, [], [], []
        self.next_id, self.seen, self.matched = -1, {}, set()
        self.original = deepcopy(state)

    def rows(self, table): return self.state[table]

    def put(self, table, before, values, origin=None):
        after = {**(before or {}), **values}
        if before is None:
            after['id'] = self.next_id; self.next_id -= 1
        key = (table, after['id'])
        previous = self.changes.get(key)
        original = previous['antes'] if previous else deepcopy(before)
        if after != original:
            self.changes[key] = {'tabla':table,'id':after['id'],'antes':original,'despues':deepcopy(after),'origen':origin}
        elif key in self.changes: del self.changes[key]
        if before is None: self.state[table].append(after)
        else: before.clear(); before.update(after)
        return after

    def issue(self, raw, message):
        self.errors.append({'hoja':raw.get('_hoja',''),'fila':raw.get('_fila',0),'mensaje':message})

    def resolve(self, table, field, value, label):
        normalizer = code_key if table=='catedras' and field=='codigo' else norm
        matches = [r for r in self.rows(table) if normalizer(r.get(field)) == normalizer(value)]
        if len(matches) != 1: raise ValueError(f'{label} desconocido o ambiguo: {value}')
        return matches[0]

    def campus_id(self, value, required=True):
        if not value:
            if self.campus: return self.campus
            if required: raise ValueError('Falta la sede; indicá una sede o “Remoto” explícitamente')
            return None
        if norm(value) in ('remoto','sinsede'): return None
        aliases = {'vte lopez':'Vicente López','vicente lopez':'Vicente López','cied':'Online - Interior',
                   'online':'Online - Interior','online interior':'Online - Interior'} if INSTITUCION.id == 'iea' else {}
        value = {norm(k):v for k,v in aliases.items()}.get(norm(value), value)
        return self.resolve('sedes','nombre',value,'Sede')['id']

    def campus_name(self, campus):
        return next((r['nombre'] for r in self.rows('sedes') if r['id']==campus), None)

    def in_scope(self, row):
        if self.kind != 'plan' and row['cuatrimestre_id'] != self.period: return False
        if not self.campus: return True
        if self.kind == 'horarios': return row.get('sede_id') == self.campus
        if not (row.get('sede') if self.kind=='plan' else row.get('sede_referencia')): return False
        try: return self.campus_id(row.get('sede') if self.kind=='plan' else row.get('sede_referencia'), False) == self.campus
        except ValueError: return False

    def unique(self, key, values):
        comparable = {k:v for k,v in values.items() if not k.startswith('_')}
        if key in self.seen:
            if self.seen[key] != comparable: raise ValueError('Hay filas incompatibles para el mismo registro; corregí el duplicado')
            self.warnings.append('Se omitió una fila idéntica repetida en el archivo')
            return False
        self.seen[key] = comparable
        return True

    def teacher(self, raw):
        document = document_key(raw.get('docente_dni'), strict=True)
        if raw.get('docente_id'):
            ident = teacher_id(raw['docente_id'])
            found = [r for r in self.rows('docentes') if r['id'] == ident]
            if len(found)!=1: raise ValueError('El ID de docente no existe')
            teacher = found[0]
            if document and document_key(teacher.get('dni')) != document:
                raise ValueError('El ID y el documento del docente no coinciden')
        elif document:
            matches = [r for r in self.rows('docentes') if document_key(r.get('dni')) == document]
            if len(matches)>1: raise ValueError('Documento docente ambiguo; revisá las fichas e indicá su ID')
            if matches: teacher=matches[0]
            else:
                name=raw.get('docente','').strip()
                if not name or len(name)>100: raise ValueError('Una nueva alta necesita documento y nombre de docente válido')
                keys={name_key(name)}
                if any(keys & {full_name(r.get('nombre'),r.get('apellido')),full_name(r.get('apellido'),r.get('nombre'))}
                       and not document_key(r.get('dni')) for r in self.rows('docentes')):
                    raise ValueError('Hay una ficha sin documento con ese nombre; completá su identidad antes de importar')
                teacher=self.put('docentes',None,{'dni':document,'nombre':name,'apellido':'','activo':True},raw)
                self.warnings.append('Se creará un docente identificado por documento; revisá el alta antes de confirmar')
        elif raw.get('docente'):
            key = norm(raw['docente'])
            ids = {r['id'] for r in self.rows('docentes') if key in
                   {norm(f"{r.get('nombre') or ''} {r.get('apellido') or ''}"),
                    norm(f"{r.get('apellido') or ''} {r.get('nombre') or ''}")}}
            ids.update(r['docente_id'] for r in self.rows('docente_alias') if norm(r['alias'])==key)
            if len(ids)>1: raise ValueError('Nombre docente ambiguo; usá docente_id o DNI docente')
            if ids: teacher = next(r for r in self.rows('docentes') if r['id']==next(iter(ids)))
            else:
                raise ValueError('Docente no identificado. Usá docente_id o documento; un nombre solo no permite dar una nueva alta')
            self.warnings.append('Se identificó un docente existente por nombre o alias. Conservá su docente_id en futuras planillas; los nombres repetidos requieren ID.')
        else: return None
        if raw.get('docente_id') and raw.get('docente'):
            key=norm(raw['docente'])
            named={r['id'] for r in self.rows('docentes') if key in
                   {norm(f"{r.get('nombre') or ''} {r.get('apellido') or ''}"),
                    norm(f"{r.get('apellido') or ''} {r.get('nombre') or ''}")}}
            named.update(r['docente_id'] for r in self.rows('docente_alias') if norm(r['alias'])==key)
            if named and teacher['id'] not in named:
                raise ValueError('El nombre corresponde a otro docente. Corregí DOCENTE_ID y el nombre antes de importar')
        if teacher.get('activo') is False: raise ValueError('El docente está inactivo')
        return teacher['id']

    def schedule(self, raw, campus):
        cat = self.resolve('catedras','codigo',code(raw.get('codigo_materia')),'Materia')
        modalidad = (raw.get('modalidad') or ('remoto' if campus is None else 'presencial_virtual')).lower()
        if modalidad not in ('virtual_tm','virtual_tn','presencial','asincronica','remoto','presencial_virtual','virtual'):
            raise ValueError('Modalidad desconocida')
        day = DAY_NAMES.get(norm(raw.get('dia')))
        start, end = clock(raw.get('hora_inicio')), clock(raw.get('hora_fin'))
        if modalidad != 'asincronica' and (not day or not start): raise ValueError('Falta un día u horario válido; completá la fila o indicá modalidad asincronica')
        if raw.get('dia') and not day: raise ValueError('Día desconocido')
        if end and not start: raise ValueError('La hora de fin necesita una hora de inicio')
        if end and end <= start: raise ValueError('La hora final debe ser posterior a la inicial dentro del mismo día')
        commission = raw.get('comision','').strip()
        if len(commission)>100 or len(raw.get('carrera',''))>300 or len(raw.get('turno',''))>30: raise ValueError('Comisión, carrera o turno demasiado largo')
        candidates = [r for r in self.rows('asignaciones') if self.in_scope(r)]
        if raw.get('asignacion_id'):
            existing = [r for r in self.rows('asignaciones') if str(r['id'])==raw['asignacion_id']]
            if len(existing)!=1 or not self.in_scope(existing[0]) or existing[0]['catedra_id']!=cat['id']:
                raise ValueError('El ID de asignación no pertenece a la materia, sede o período elegidos')
            matches = existing
        else:
            matches = [r for r in candidates if (r['catedra_id'],r.get('sede_id'),r.get('modalidad'),r.get('dia'),r.get('hora_inicio'),r.get('comision') or '')
                       == (cat['id'],campus,modalidad,day,start,commission)]
            self.warnings.append('Sin ID de asignación, un cambio de día u hora se interpreta como una nueva franja. En Actualizar se conserva la anterior; usá los IDs de la planilla exportada para editarla.')
        if len(matches)>1: raise ValueError('Varias asignaciones coinciden; identificá cada una con asignacion_id o comisión')
        before = matches[0] if matches else None
        identity = before['id'] if before and before['id']>0 else (cat['id'],campus,commission,modalidad,day,start)
        if not self.unique(('horarios',str(identity)), raw): return
        teacher_id = self.teacher(raw)
        values = {'catedra_id':cat['id'],'cuatrimestre_id':self.period,'docente_id':teacher_id,
                  'sede_id':campus,'modalidad':modalidad,'dia':day,'hora_inicio':start,'hora_fin':end}
        if before is None: values.update(recibe_alumnos_presenciales=False,modificada=False)
        for field in ('comision','carrera','turno'):
            if field in raw: values[field] = raw[field] or None
        if 'recibe_alumnos_presenciales' in raw: values['recibe_alumnos_presenciales'] = boolean(raw['recibe_alumnos_presenciales'])
        after = self.put('asignaciones', before, values, raw)
        self.matched.add(after['id'])
        if raw.get('link_meet'):
            link = raw['link_meet']
            if not link.startswith(('https://','http://')) or len(link)>300: raise ValueError('El enlace debe ser HTTP(S) y no superar 300 caracteres')
            self.unique(('link',cat['id']), {'link':link})
            self.put('catedras',cat,{'link_meet':link},raw)
        existing_dictado = next((r for r in self.rows('catedra_dictado') if r['catedra_id']==cat['id'] and r['cuatrimestre_id']==self.period), None)
        self.put('catedra_dictado',existing_dictado,{'catedra_id':cat['id'],'cuatrimestre_id':self.period,'se_dicta':True},raw)
        self.records.append({**raw,'codigo_materia':cat['codigo'],'sede':self.campus_name(campus),'docente_id':teacher_id})

    def enrollment(self, raw, campus):
        document = dni(raw.get('dni'))
        cat = self.resolve('catedras','codigo',code(raw.get('codigo_materia')),'Materia')
        existing_student = next((r for r in self.rows('alumnos') if r['dni']==document), None)
        values = {'dni':document}
        if raw.get('alumno') and not raw.get('nombre'):
            parts = raw['alumno'].rsplit(' ',1)
            values.update(nombre=parts[0],apellido=parts[1] if len(parts)>1 else '')
        for field in ('nombre','apellido','email'):
            if field in raw: values[field] = raw[field] or None
        if not existing_student and not values.get('nombre'): raise ValueError('Falta el nombre del alumno nuevo')
        if any(len(values.get(field) or '')>limit for field,limit in [('nombre',100),('apellido',100),('email',150)]): raise ValueError('Nombre, apellido o correo demasiado largo')
        self.unique(('alumno',document), values)
        if not self.unique(('inscripcion',document,cat['id']), raw): return
        student = self.put('alumnos',existing_student,values,raw)
        matches = [r for r in self.rows('inscripciones') if r['alumno_id']==student['id'] and r['catedra_id']==cat['id'] and r['cuatrimestre_id']==self.period]
        if len(matches)>1: raise ValueError('La base contiene inscripciones duplicadas para este alumno y materia')
        before = matches[0] if matches else None
        if before and not self.in_scope(before): raise ValueError('La inscripción existente pertenece a otra sede; no se moverá desde una importación parcial')
        modality = raw.get('modalidad') or 'presencial'
        if modality not in ('presencial','virtual'): raise ValueError('Modalidad de alumno desconocida; usá presencial o virtual')
        if len(raw.get('carrera',''))>200 or len(raw.get('edi_materia',''))>100: raise ValueError('Carrera o referencia EDI demasiado larga')
        values = {'alumno_id':student['id'],'catedra_id':cat['id'],'cuatrimestre_id':self.period,
                  'sede_referencia':self.campus_name(campus),'turno':raw.get('turno') or None,
                  'modalidad_alumno':modality,'curso_nombre':raw.get('carrera') or None,
                  'es_edi':boolean(raw.get('es_edi')),'edi_materia':raw.get('edi_materia') or None}
        after = self.put('inscripciones',before,values,raw); self.matched.add(after['id'])
        self.records.append({**raw,'dni':document,'codigo_materia':cat['codigo'],'sede':self.campus_name(campus)})

    def career_plan(self, raw, campus):
        if not raw.get('carrera') or not raw.get('anno') or not raw.get('materia'):
            raise ValueError('Cada materia del plan necesita carrera, año y nombre')
        campus_name = self.campus_name(campus)
        if campus_name is None: raise ValueError('El plan de carrera necesita una sede identificada')
        if INSTITUCION.id=='iea' and campus_name=='Online - Interior': campus_name='CIED'
        values = {'sede':campus_name,'carrera':raw['carrera'],'anno':raw['anno'],
                  'codigo_catedra':code(raw.get('codigo_materia')),'nombre_catedra':raw['materia']}
        for shift in ('tm','tn'):
            day = raw.get('dia_'+shift)
            if day and norm(day) not in DAY_NAMES: raise ValueError('Día del plan desconocido')
            values['dia_'+shift] = DAY_NAMES.get(norm(day)) if day else None
            values['hora_'+shift] = clock(raw.get('hora_'+shift))
        identity = (norm(campus_name),norm(values['carrera']),norm(values['anno']),code_key(values['codigo_catedra']))
        if not self.unique(('plan',*identity), values): return
        matches = [r for r in self.rows('plan_carrera') if (norm(r['sede']),norm(r['carrera']),norm(r['anno']),code_key(r['codigo_catedra']))==identity]
        if len(matches)>1: raise ValueError('Hay materias repetidas en el plan vigente; revisá sus identificadores')
        after = self.put('plan_carrera',matches[0] if matches else None,values,raw)
        self.matched.add(after['id']); self.records.append(raw)

    def build(self, records):
        for raw in records:
            try:
                if any(isinstance(value,str) and value.startswith('=') for key,value in raw.items() if not key.startswith('_')):
                    raise ValueError('Hay fórmulas en campos de datos; pegá sus valores')
                if raw.get('periodo_id') and (self.period is None or raw['periodo_id'] != str(self.period)):
                    raise ValueError('El período indicado en la fila no coincide con el destino')
                campus = self.campus_id(raw.get('sede'))
                if self.campus and campus != self.campus: raise ValueError('La fila pertenece a otra sede; corregí el alcance o el archivo')
                if self.kind=='horarios': self.schedule(raw,campus)
                elif self.kind=='inscripciones': self.enrollment(raw,campus)
                else: self.career_plan(raw,campus)
            except (ValueError, KeyError) as exc: self.issue(raw,str(exc))
        target = TARGET[self.kind]
        if self.mode == 'reemplazar':
            for before in self.original[target]:
                if self.in_scope(before) and before['id'] not in self.matched:
                    self.changes[(target,before['id'])] = {'tabla':target,'id':before['id'],'antes':before,'despues':None,'origen':None}
        return list(self.changes.values())


def build_preview(db, content, filename, kind, period, campus, mode, formato='auto', mapping=None):
    if formato not in ('auto','iea','estandar'): raise ValueError('Formato desconocido')
    state = read_state(db)
    initial_digest = digest(state)
    planner = Planner(state,kind,period,campus,mode)
    records, errors, warnings, headers = parse_file(content,filename,kind,formato,mapping)
    changes = planner.build(records)
    errors.extend(planner.errors); warnings.extend(planner.warnings)
    scope = {'cuatrimestre_id':period,'sede_id':campus,'sede':planner.campus_name(campus) if campus else 'Todas las sedes'}
    count = Counter('altas' if op['antes'] is None else 'bajas' if op['despues'] is None else 'modificaciones' for op in changes if op['tabla']==TARGET[kind])
    unchanged = max(0,len(planner.matched)-count['altas']-count['modificaciones'])
    revision = digest({'version':1,'estado':initial_digest,'archivo':hashlib.sha256(content).hexdigest(),
                       'nombre_archivo':filename,'tipo':kind,'alcance':scope,'modo':mode,'formato':formato,'mapeo':mapping or {},
                       'perfil':INSTITUCION.public_config(),'cambios':changes})
    public = {'tipo':kind,'archivo':filename,'alcance':scope,'modo':mode,'formato':formato,
              'resumen':{'altas':count['altas'],'modificaciones':count['modificaciones'],'bajas':count['bajas'],'sin_cambios':unchanged,
                         'cambios_relacionados':sum(op['tabla']!=TARGET[kind] for op in changes)},
              'errores':errors,'advertencias':sorted(set(warnings)), 'columnas':headers,
              'campos':list(FIELDS),
              'cambios':changes, 'filas_normalizadas':planner.records,
              'puede_aplicar':bool(records) and not errors,
              'token':token_for(revision) if records and not errors else None}
    return public, changes, revision


def write_row(db, table, before, after):
    if table not in WRITABLE: raise ValueError('Tabla no admitida en una operación de importación')
    if after is None:
        db.execute(text(f'DELETE FROM {table} WHERE id = :id'), {'id':before['id']})
        return None
    values = dict(after)
    if before is None:
        if values.get('id',0)<0: values.pop('id')
        names = list(values)
        query = f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join(':'+n for n in names)}) RETURNING *"
    else:
        names = [name for name in values if name!='id']
        query = f"UPDATE {table} SET {', '.join(name+' = :'+name for name in names)} WHERE id = :id RETURNING *"
    row = db.execute(text(query),values).fetchone()
    if not row: raise ValueError('El registro cambió durante la operación')
    return dict(row._mapping)


def execute_changes(db, changes):
    ids, actual = {}, []
    for change in changes:
        after = deepcopy(change['despues'])
        if after:
            for field, target in FOREIGN_KEYS.items():
                if after.get(field) is not None and after[field] < 0: after[field] = ids[(target,after[field])]
        saved = write_row(db, change['tabla'], change['antes'], after)
        if change['antes'] is None: ids[(change['tabla'],change['id'])] = saved['id']
        actual.append({**change,'id':saved['id'] if saved else change['id'],'despues':saved})
    return actual


def insert_history(db, payload):
    return db.execute(text('INSERT INTO importaciones_historial (tipo, cuatrimestre_id, sede_id, archivo, datos) VALUES (:t,:p,:s,:a,:d) RETURNING id'),
                      {'t':payload['tipo'],'p':payload['alcance'].get('cuatrimestre_id'),'s':payload['alcance'].get('sede_id'),
                       'a':payload.get('archivo',''),'d':json_text(payload)}).scalar_one()


def apply_import(db, content, filename, kind, period, campus, mode, formato, mapping, token):
    try:
        lock_state(db)
        preview, changes, revision = build_preview(db,content,filename,kind,period,campus,mode,formato,mapping)
        if not preview['puede_aplicar']: raise HTTPException(422, {'mensaje':'Corregí las filas indicadas antes de importar','errores':preview['errores']})
        check_token(token,revision)
        if not changes:
            db.rollback()
            return {'ok':True,'sin_cambios':True,'resumen':preview['resumen'],'historial_id':None}
        payload = {'version':1,'tipo':kind,'archivo':filename,'alcance':preview['alcance'],'modo':mode,'cambios':changes}
        history_id = insert_history(db,payload)  # Must succeed before any business write.
        payload['cambios'] = execute_changes(db,changes)
        db.execute(text('UPDATE importaciones_historial SET datos=:datos WHERE id=:id'), {'datos':json_text(payload),'id':history_id})
        db.commit()
        return {'ok':True,'sin_cambios':False,'resumen':preview['resumen'],'historial_id':history_id,'mensaje':'Importación aplicada. Se guardó el estado completo de los registros afectados.'}
    except Exception:
        db.rollback()
        raise


def restoration_preview(db, history_id):
    row = db.execute(text('SELECT * FROM importaciones_historial WHERE id=:id'),{'id':history_id}).mappings().first()
    if not row: raise HTTPException(404,'No se encontró esa importación')
    if row['restaurada_en']: raise HTTPException(409,'Esta operación ya fue restaurada')
    try:
        data = json.loads(row['datos'])
        if data.get('version')!=1: raise ValueError()
        changes = data['cambios']
        if not isinstance(changes,list) or any(c['tabla'] not in WRITABLE for c in changes): raise ValueError()
    except (ValueError, KeyError, TypeError): raise HTTPException(422,'El respaldo no tiene un formato válido')
    state = read_state(db)
    conflicts = []
    restored_rows = {(c['tabla'],c['id']):c['antes'] for c in changes}
    for change in changes:
        current = next((r for r in state[change['tabla']] if r['id']==change['id']), None)
        if digest(current)!=digest(change['despues']):
            conflicts.append(f"{change['tabla']} #{change['id']} fue modificado después de la importación")
        if change['antes'] is None and change['tabla'] in ('alumnos','docentes'):
            field = 'alumno_id' if change['tabla']=='alumnos' else 'docente_id'
            for table, rows in state.items():
                if any(r.get(field)==change['id'] and
                       ((table,r['id']) not in restored_rows or
                        (restored_rows[(table,r['id'])] or {}).get(field)==change['id']) for r in rows):
                    conflicts.append(f"{change['tabla']} #{change['id']} tiene referencias posteriores en {table}")
    inverse = [{**c,'antes':c['despues'],'despues':c['antes']} for c in reversed(changes)]
    revision = digest({'historial':history_id,'datos':data,'estado':state})
    return {'historial_id':history_id,'alcance':data['alcance'],'tipo':data['tipo'],'cambios':inverse,
            'conflictos':sorted(set(conflicts)),'puede_restaurar':not conflicts,
            'token':token_for(revision) if not conflicts else None}, revision


def restore_import(db, history_id, token):
    try:
        lock_state(db)
        preview, revision = restoration_preview(db,history_id)
        if not preview['puede_restaurar']: raise HTTPException(409,{'mensaje':'La recuperación afectaría cambios posteriores','conflictos':preview['conflictos']})
        check_token(token,revision)
        payload = {'version':1,'tipo':'restauracion','archivo':f'Recuperación de #{history_id}',
                   'alcance':preview['alcance'],'restauracion_de':history_id,'cambios':preview['cambios']}
        undo_id = insert_history(db,payload)
        payload['cambios'] = execute_changes(db,preview['cambios'])
        db.execute(text('UPDATE importaciones_historial SET datos=:datos WHERE id=:id'),{'datos':json_text(payload),'id':undo_id})
        db.execute(text('UPDATE importaciones_historial SET restaurada_en=CURRENT_TIMESTAMP WHERE id=:id'),{'id':history_id})
        db.commit()
        return {'ok':True,'historial_id':undo_id,'mensaje':'Se recuperó el estado anterior de todos los registros afectados.'}
    except Exception:
        db.rollback()
        raise
