from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.institution import INSTITUCION
from app.curriculum_routes import editor
from app.enrollment_plans import course_index, students, save_course, save_student

router=APIRouter(prefix='/api/inscripciones-planes',tags=['Carreras informadas y planes opcionales'])

@router.get('/{period}')
def index(period:int,db:Session=Depends(get_db)):
    return course_index(db,INSTITUCION.id,period)

@router.get('/{period}/cursos/{course}')
def detail(period:int,course:int,q:str=Query('',max_length=100),pendientes:bool=False,
           offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db)):
    return students(db,INSTITUCION.id,period,course,q,pendientes,offset,limit)

@router.put('/{period}/cursos/{course}')
def associate_course(period:int,course:int,data:dict,db:Session=Depends(get_db)):
    editor(data,db)
    return save_course(db,INSTITUCION.id,period,course,data)

@router.put('/{period}/cursos/{course}/alumnos/{student}')
def associate_student(period:int,course:int,student:int,data:dict,db:Session=Depends(get_db)):
    editor(data,db)
    return save_student(db,INSTITUCION.id,period,course,student,data)
