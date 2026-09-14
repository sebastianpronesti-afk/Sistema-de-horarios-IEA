from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.institution import INSTITUCION
from app.curriculum_routes import editor
from app.academic_store import save_offering
from app.academic_planning import require_period, view_plan, suggestions, save_assignment

router=APIRouter(prefix="/api/planificacion",tags=["Planificación por planes"])

@router.get('/{period}/planes/{plan_id}')
def view(period:int,plan_id:str,db:Session=Depends(get_db)):
    return view_plan(db,INSTITUCION,period,plan_id)

@router.put('/{period}/planes/{plan_id}/oferta')
def offer(period:int,plan_id:str,data:dict,db:Session=Depends(get_db)):
    editor(data,db);require_period(db,period)
    return save_offering(db,INSTITUCION.id,period,plan_id,data.get("revision"),data.get("materia_ids"),data.get("catalog_revision"))

@router.get('/{period}/planes/{plan_id}/materias/{subject_id}/sugerencias')
def suggest(period:int,plan_id:str,subject_id:str,sede_id:int=None,modalidad:str="presencial",db:Session=Depends(get_db)):
    return suggestions(db,INSTITUCION,period,plan_id,subject_id,sede_id,modalidad)

@router.post('/{period}/planes/{plan_id}/materias/{subject_id}/asignar')
def assign(period:int,plan_id:str,subject_id:str,data:dict,db:Session=Depends(get_db)):
    editor(data,db)
    return save_assignment(db,INSTITUCION,period,plan_id,subject_id,data)
