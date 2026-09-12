import io
import json
import logging
from typing import Optional, Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from openpyxl import Workbook
from app.database import get_db
from app import import_service as service

router = APIRouter(prefix='/api/importaciones', tags=['Importaciones recuperables'])
Kind = Literal['horarios','inscripciones','plan']
Mode = Literal['actualizar','reemplazar']
Format = Literal['auto','estandar','iea']


def parse_mapping(value):
    try: return json.loads(value or '{}')
    except ValueError: raise HTTPException(422,'No se pudo interpretar el mapeo de columnas')


def translate_error(exc):
    if isinstance(exc,HTTPException): raise exc
    if isinstance(exc,ValueError): raise HTTPException(422,str(exc))
    logging.getLogger(__name__).exception('Import transaction failed')
    raise HTTPException(500,'No se pudo completar la operación. Se conservaron los datos anteriores.')


@router.post('/vista-previa')
async def preview(file: UploadFile=File(...), tipo:Kind=Query(...), sede_id:int=Query(...,ge=0),
                  cuatrimestre_id:Optional[int]=None, modo:Mode='actualizar', formato:Format='auto',
                  mapeo:str=Form('{}'), db:Session=Depends(get_db)):
    try:
        data, _, _ = service.build_preview(db,await file.read(),file.filename or 'archivo.xlsx',tipo,
                                          cuatrimestre_id,sede_id,modo,formato,parse_mapping(mapeo))
        return data
    except Exception as exc:
        db.rollback(); translate_error(exc)


@router.post('/aplicar')
async def apply(file: UploadFile=File(...), tipo:Kind=Query(...), sede_id:int=Query(...,ge=0),
                cuatrimestre_id:Optional[int]=None, modo:Mode='actualizar', formato:Format='auto',
                mapeo:str=Form('{}'), token:str=Form(...), db:Session=Depends(get_db)):
    try:
        return service.apply_import(db,await file.read(),file.filename or 'archivo.xlsx',tipo,
                                    cuatrimestre_id,sede_id,modo,formato,parse_mapping(mapeo),token)
    except Exception as exc:
        db.rollback(); translate_error(exc)


@router.get('/historial')
def history(cuatrimestre_id:Optional[int]=None, db:Session=Depends(get_db)):
    clause = ' WHERE cuatrimestre_id=:period OR cuatrimestre_id IS NULL' if cuatrimestre_id else ''
    rows = db.execute(text('SELECT id,tipo,cuatrimestre_id,sede_id,archivo,creado_en,restaurada_en FROM importaciones_historial'+clause+' ORDER BY id DESC LIMIT 100'),{'period':cuatrimestre_id})
    return {'historial':[dict(row._mapping) for row in rows]}


@router.post('/historial/{history_id}/vista-previa')
def recovery_preview(history_id:int, db:Session=Depends(get_db)):
    try:
        data,_ = service.restoration_preview(db,history_id)
        return data
    except Exception as exc:
        db.rollback(); translate_error(exc)


@router.post('/historial/{history_id}/restaurar')
def recover(history_id:int, data:dict, db:Session=Depends(get_db)):
    try: return service.restore_import(db,history_id,data.get('token'))
    except Exception as exc:
        db.rollback(); translate_error(exc)


TEMPLATES = {
    'horarios':['asignacion_id','codigo_materia','materia','carrera','sede','periodo_id','comision','turno','dia','hora_inicio','hora_fin','docente_id','docente','modalidad','link_meet','recibe_alumnos_presenciales'],
    'inscripciones':['codigo_materia','dni','nombre','apellido','email','carrera','sede','periodo_id','turno','modalidad','es_edi','edi_materia'],
    'plan':['codigo_materia','materia','carrera','sede','anno','dia_tm','hora_tm','dia_tn','hora_tn'],
}


@router.get('/plantilla')
def template(tipo:Kind):
    workbook=Workbook(); sheet=workbook.active; sheet.title='Datos'
    sheet.append(TEMPLATES[tipo]); sheet.freeze_panes='A2'
    for col in sheet.columns: sheet.column_dimensions[col[0].column_letter].width=24
    instructions=workbook.create_sheet('Instructivo')
    instructions.append(['Completá las columnas de Datos; conservá los encabezados.'])
    instructions.append(['Usá códigos de materias y sedes que ya existan en el sistema.'])
    instructions.append(['En horarios, conservá asignacion_id al editar. Sin ID, un cambio de día u hora crea otra franja. Una comisión puede tener varias franjas.'])
    instructions.append(['En inscripciones, reemplazar elimina inscripciones ausentes del alcance, sin borrar personas.'])
    instructions.append(['El plan es compartido entre períodos y se reemplaza solamente en las sedes seleccionadas.'])
    instructions.column_dimensions['A'].width=110
    buffer=io.BytesIO(); workbook.save(buffer); buffer.seek(0)
    return StreamingResponse(buffer,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             headers={'Content-Disposition':f'attachment; filename=plantilla_{tipo}.xlsx'})
