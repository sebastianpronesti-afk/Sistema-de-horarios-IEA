from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Catedra
from app.institution import INSTITUCION
from app.curriculum import load_catalog, Reconciler, catalog_summary
from app.academic_store import read_document, edit_catalog

router=APIRouter(prefix='/api/planes-estudio',tags=['Planes de estudio'])


def context(db):
    try:
        catalog, revision=read_document(db, 'catalog:'+INSTITUCION.id, lambda: load_catalog(INSTITUCION.id))
        catalog['_revision']=revision
    except (ValueError,OSError,KeyError,TypeError) as exc:
        raise HTTPException(503,'No se pudo cargar el catálogo institucional de planes') from exc
    records=db.query(Catedra.id,Catedra.codigo,Catedra.nombre).all()
    return catalog,Reconciler([{'id':r.id,'codigo':r.codigo,'nombre':r.nombre} for r in records])


@router.get('')
def index(db:Session=Depends(get_db)):
    catalog,reconciler=context(db)
    return {**catalog_summary(catalog,reconciler),'revision':catalog['_revision']}


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
            return {'revision':catalog['_revision'],'nombre':career['nombre'],'materias':[reconciler.subject(s) for s in career.get('materias_sin_plan',[])]}
    raise HTTPException(404,'Carrera no encontrada')



@router.get('/opciones')
def options(db:Session=Depends(get_db)):
    return {"catedras":[{"id":c.id,"codigo":c.codigo,"nombre":c.nombre} for c in db.query(Catedra).order_by(Catedra.codigo).all()]}

def editor(data,db):
    from app.main import verificar_clave
    if verificar_clave(db,data.pop("clave_edicion",None))!="editor":
        raise HTTPException(401,"Ingresá la clave de edición para guardar")

@router.post('/editar')
def edit(data:dict,db:Session=Depends(get_db)):
    editor(data,db)
    operation=data.get("operation")
    required={"plan":("plan_id",),"subject":("plan_id","subject_id"),"move":("career_id","plan_id","subject_id"),
              "new_plan":("career_id",),"new_subject":("plan_id",)}
    if operation not in required or any(not isinstance(data.get(k),str) for k in required[operation]):
        raise HTTPException(422,"Solicitud de edición incompleta")
    if not isinstance(data.get("changes",{}),dict): raise HTTPException(422,"Campos inválidos")
    return edit_catalog(db,INSTITUCION.id,data.get("revision"),operation,data)

@router.get('/{ident}')
def detail(ident:str,db:Session=Depends(get_db)):
    catalog,reconciler=context(db)
    for career in catalog['careers']:
        for plan in career['planes']:
            if plan['id']==ident:
                return {'revision':catalog['_revision'],**reconciler.plan(plan),'carrera':career['nombre'],'nivel':career['nivel']}
    raise HTTPException(404,'Plan de estudios no encontrado')
