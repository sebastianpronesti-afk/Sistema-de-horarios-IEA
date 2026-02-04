from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Sede(Base):
    __tablename__ = "sedes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), default="bg-blue-500")

class Cuatrimestre(Base):
    __tablename__ = "cuatrimestres"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    anio = Column(Integer, nullable=False)
    numero = Column(Integer, nullable=False)  # 1 o 2
    activo = Column(Boolean, default=False)

class Catedra(Base):
    __tablename__ = "catedras"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(200), nullable=False)
    asignaciones = relationship("Asignacion", back_populates="catedra")
    inscripciones = relationship("Inscripcion", back_populates="catedra")

class Docente(Base):
    __tablename__ = "docentes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    dni = Column(String(20), unique=True, nullable=False)
    email = Column(String(150))
    sede_id = Column(Integer, ForeignKey("sedes.id"))
    sede = relationship("Sede")
    asignaciones = relationship("Asignacion", back_populates="docente")

class Alumno(Base):
    __tablename__ = "alumnos"
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(100))
    apellido = Column(String(100))
    email = Column(String(150))
    inscripciones = relationship("Inscripcion", back_populates="alumno")

class Curso(Base):
    __tablename__ = "cursos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(300), nullable=False)
    sede_id = Column(Integer, ForeignKey("sedes.id"))
    sede = relationship("Sede")

class Asignacion(Base):
    """Una cátedra puede tener múltiples asignaciones por cuatrimestre"""
    __tablename__ = "asignaciones"
    id = Column(Integer, primary_key=True, index=True)
    catedra_id = Column(Integer, ForeignKey("catedras.id"), nullable=False)
    cuatrimestre_id = Column(Integer, ForeignKey("cuatrimestres.id"), nullable=False)
    modalidad = Column(String(20), nullable=False)  # virtual_tm, virtual_tn, presencial, asincronica
    docente_id = Column(Integer, ForeignKey("docentes.id"), nullable=True)
    dia = Column(String(20), nullable=True)
    hora = Column(String(10), nullable=True)
    modificada = Column(Boolean, default=False)
    
    catedra = relationship("Catedra", back_populates="asignaciones")
    cuatrimestre = relationship("Cuatrimestre")
    docente = relationship("Docente", back_populates="asignaciones")

class Inscripcion(Base):
    __tablename__ = "inscripciones"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    catedra_id = Column(Integer, ForeignKey("catedras.id"), nullable=False)
    cuatrimestre_id = Column(Integer, ForeignKey("cuatrimestres.id"), nullable=False)
    curso_id = Column(Integer, ForeignKey("cursos.id"), nullable=True)
    
    alumno = relationship("Alumno", back_populates="inscripciones")
    catedra = relationship("Catedra", back_populates="inscripciones")
    cuatrimestre = relationship("Cuatrimestre")
    curso = relationship("Curso")
