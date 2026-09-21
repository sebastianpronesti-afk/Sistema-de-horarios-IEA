"""Stable existing IDs and conservative identity matching; never merge people by name."""
from collections import defaultdict
import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import text


def teacher_label(ident):
    return f"DOC-{ident:06d}"


def teacher_id(value):
    raw = str(value or '').strip()
    if raw.upper().startswith('DOC-'):
        raw = raw[4:]
    if not re.fullmatch(r'[0-9]+', raw) or int(raw) < 1:
        raise ValueError('ID de docente inválido; usá su ID o DOC-000001')
    return int(raw)


def document_key(value, strict=False):
    raw = re.sub(r'\s', '', str(value or ''))
    if re.fullmatch(r'[0-9]+\.0+', raw):
        raw = raw.split('.')[0]
    else:
        raw = raw.replace('.', '').replace('-', '')
    if not raw:
        return None
    if not re.fullmatch(r'[0-9]{6,12}', raw):
        if strict:
            raise ValueError('Documento inválido; usá entre 6 y 12 dígitos, sin letras')
        return None
    return raw.lstrip('0') or '0'


def code_key(value):
    # Punctuation and leading zeros are meaningful: MAT-1 is not MAT1.
    return str(value or '').strip().lower()


def name_key(value):
    raw = unicodedata.normalize('NFD', str(value or '').casefold())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in raw if unicodedata.category(c) != 'Mn')).split())


def full_name(nombre, apellido):
    return name_key(f'{nombre or ""} {apellido or ""}')


def name_keys(nombre, apellido):
    return {full_name(nombre, apellido), full_name(apellido, nombre)} - {''}


def lock_teachers(db):
    # Same order as import_service.lock_state; before reading identities.
    db.execute(text('LOCK TABLE docentes IN SHARE ROW EXCLUSIVE MODE'))


def teacher_values(db, data, existing=None):
    from app.models.models import Docente
    if 'id' in data and data['id'] != (existing.id if existing else None):
        raise HTTPException(422, 'El ID del docente es permanente y no se puede cambiar')
    values = {field: getattr(existing, field, None) if existing else None
              for field in ('nombre', 'apellido', 'dni', 'email')}
    for field in values:
        if field in data:
            if data[field] is not None and not isinstance(data[field], (str, int)):
                raise HTTPException(422, 'Datos del docente inválidos')
            values[field] = str(data[field] or '').strip()
    values['nombre'] = values['nombre'] or ''
    values['apellido'] = values['apellido'] or ''
    if not values['nombre'] and not values['apellido']:
        raise HTTPException(422, 'Indicá al menos nombre o apellido')
    if len(values['nombre']) > 100 or len(values['apellido']) > 100 or len(values['email'] or '') > 150:
        raise HTTPException(422, 'Nombre, apellido o email demasiado largo')
    # An old invalid document remains evidence until explicitly corrected.
    if 'dni' in data or not existing:
        try:
            if existing and (values['dni'] or '') == (existing.dni or ''):
                values['dni'] = existing.dni
            else:
                normalized = document_key(values['dni'], strict=True)
                # Do not rewrite an unchanged historical duplicate to the exact raw
                # document of another fiche while saving unrelated fields.
                values['dni'] = existing.dni if existing and normalized and normalized == document_key(existing.dni) else normalized
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    document = document_key(values['dni'])
    people = [d for d in db.query(Docente).all() if not existing or d.id != existing.id]
    if document and (not existing or document != document_key(existing.dni)):
        matches = [d for d in people if document_key(d.dni) == document]
        if matches:
            raise HTTPException(409, 'Ese documento ya está asociado a ' + ', '.join(teacher_label(d.id) for d in matches) + '. Editá la ficha existente.')
    name = full_name(values['nombre'], values['apellido'])
    identity_changed = not existing or name != full_name(existing.nombre, existing.apellido) or document != document_key(existing.dni)
    if identity_changed:
        # Real homonyms with different confirmed documents remain different people.
        matches = [d for d in people if name_keys(d.nombre, d.apellido) & name_keys(values['nombre'],values['apellido'])
                   and (not document or not document_key(d.dni))]
        if matches:
            raise HTTPException(409, 'Posible docente repetido: ' + ', '.join(teacher_label(d.id) for d in matches) + '. Completá el documento en la ficha existente antes de dar otra alta.')
    return values


def find_teacher(db, data):
    """Imports resolve by explicit ID/document. Names only identify review candidates."""
    from app.models.models import Docente
    people = db.query(Docente).all()
    raw_id = data.get('docente_id')
    doc = document_key(data.get('dni'), strict=True)
    if raw_id:
        ident = teacher_id(raw_id)
        person = next((d for d in people if d.id == ident), None)
        if not person:
            raise ValueError('El ID docente no existe')
        if doc and document_key(person.dni) and doc != document_key(person.dni):
            raise ValueError('El ID y el documento pertenecen a identidades distintas; corregí la ficha antes de importar')
        return person
    if doc:
        matches = [d for d in people if document_key(d.dni) == doc]
        if len(matches) > 1:
            raise ValueError('Documento repetido en fichas anteriores; indicá docente_id y revisá las fichas')
        if matches:
            return matches[0]
    elif not raw_id:
        raise ValueError('Falta docente_id o documento; completá la identidad antes de importar')
    return None


def find_chair(db, code):
    from app.models.models import Catedra
    matches = [c for c in db.query(Catedra).all() if code_key(c.codigo) == code_key(code)]
    if len(matches) > 1:
        raise ValueError('Código de cátedra ambiguo; revisá los registros existentes')
    return matches[0] if matches else None


def plan_key(career_id, plan):
    fields = ('resolucion', 'jurisdiccion', 'modalidad')
    if any(not name_key(plan.get(field)) for field in fields):
        return None
    # Never derive the persistent ID from editable academic attributes.
    return (career_id, *(name_key(plan[field]) for field in fields), name_key(plan.get('version_plan') or '1'))


def plan_identity(career_id, plan, plans):
    key = plan_key(career_id, plan)
    matches = [p['id'] for p in plans if p['id'] != plan['id'] and key and plan_key(career_id, p) == key]
    missing = [f for f in ('resolucion', 'jurisdiccion', 'modalidad') if not name_key(plan.get(f))]
    return {'id': plan['id'], 'version': plan.get('version_plan') or '1',
            'estado': 'posible_duplicado' if matches else 'incompleta' if missing else 'completa',
            'campos_pendientes': missing, 'coincidencias': matches}


def identity_report(db):
    from app.models.models import Docente, Catedra
    people = db.query(Docente).order_by(Docente.id).all()
    chairs = db.query(Catedra).order_by(Catedra.id).all()
    documents, names, codes = defaultdict(list), defaultdict(list), defaultdict(list)
    for d in people:
        if document_key(d.dni): documents[document_key(d.dni)].append(d.id)
        for key in name_keys(d.nombre,d.apellido): names[key].append(d.id)
    for c in chairs:
        codes[code_key(c.codigo)].append(c.id)
    return {
        'documentos_repetidos': [ids for ids in documents.values() if len(ids) > 1],
        'nombres_coincidentes': [list(ids) for ids in sorted({tuple(ids) for ids in names.values() if len(ids)>1})],
        'docentes_sin_documento_valido': [d.id for d in people if not document_key(d.dni)],
        'codigos_repetidos': [ids for ids in codes.values() if len(ids) > 1],
        'mensaje': 'Las coincidencias requieren revisión. No se fusionan fichas ni se modifican códigos automáticamente.'}
