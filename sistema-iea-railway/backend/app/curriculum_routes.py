from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Catedra
from app.institution import INSTITUCION
from app.curriculum import load_catalog, Reconciler, catalog_summary

router=APIRouter(prefix='/api/planes-estudio',tags=['Planes de estudio'])


def context(db):
    try: catalog=load_catalog(INSTITUCION.id)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        raise HTTPException(503,'No se pudo cargar el catálogo institucional de planes') from exc
    records=db.query(Catedra.id,Catedra.codigo,Catedra.nombre).all()
    return catalog,Reconciler([{'id':r.id,'codigo':r.codigo,'nombre':r.nombre} for r in records])


@router.get('')
def index(db:Session=Depends(get_db)):
    catalog,reconciler=context(db)
    return catalog_summary(catalog,reconciler)


@router.get('/articulaciones/{ident}')
def articulation(ident:str,db:Session=Depends(get_db)):
    catalog,reconciler=context(db)
    for item in catalog['articulations']:
        if item['id']==ident:
            return {**item,'bloques':[{**block,'materias':[reconciler.subject(s) for s in block['materias']]} for block in item['bloques']]}
    raise HTTPException(404,'Articulación no encontrada')


@router.get('/carreras/{ident}/pendientes')
def pending(ident:str,db:Session=Depends(get_db)):
    catalog,reconciler=context(db)
    for career in catalog['careers']:
        if career['id']==ident:
            return {'nombre':career['nombre'],'materias':[reconciler.subject(s) for s in career.get('materias_sin_plan',[])]}
    raise HTTPException(404,'Carrera no encontrada')


@router.get('/{ident}')
def detail(ident:str,db:Session=Depends(get_db)):
    catalog,reconciler=context(db)
    for career in catalog['careers']:
        for plan in career['planes']:
            if plan['id']==ident:
                return {**reconciler.plan(plan),'carrera':career['nombre'],'nivel':career['nivel']}
    raise HTTPException(404,'Plan de estudios no encontrado')
