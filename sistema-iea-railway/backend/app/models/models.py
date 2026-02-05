from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text, Time
from sqlalchemy.orm import relationship
from app.database import Base

class Sede(Base):
    __tablename__ = "sedes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), default="bg-blue-500")
    docentes = relationship("DocenteSede", back_populates="sede")

class Cuatrimestre(Base):
    __tablename__ = "cuatrimestres"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    anio = Column(Integer, nullable=False)
    numero = Column(Integer, nullable=False)
    activo = Column(Boolean, default=False)

class Catedra(Base):
    __tablename__ = "catedras"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(200), nullable=False)
    link_meet = Column(String(300), nullable=True)
    asignaciones = relationship("Asignacion", back_populates="catedra")
    inscripciones = relationship("Inscripcion", back_populates="catedra")
    cursos = relationship("CatedraCurso", back_populates="catedra")

class Docente(Base):
    __tablename__ = "docentes"
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(150))
    sedes = relationship("DocenteSede", back_populates="docente", cascade="all, delete-orphan")
    asignaciones = relationship("Asignacion", back_populates="docente")

class DocenteSede(Base):
    __tablename__ = "docente_sede"
    id = Column(Integer, primary_key=True, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False)
    sede_id = Column(Integer, ForeignKey("sedes.id", ondelete="CASCADE"), nullable=False)
    docente = relationship("Docente", back_populates="sedes")
    sede = relationship("Sede", back_populates="docentes")

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
    catedras = relationship("CatedraCurso", back_populates="curso")

class CatedraCurso(Base):
    """
    Relación muchos-a-muchos: qué cátedras pertenecen a qué cursos/carreras.
    Formato de la captura: Codigo | Materia (c.XX Nombre - Turno) | Curso | Sede
    """
    __tablename__ = "catedra_curso"
    id = Column(Integer, primary_key=True, index=True)
    catedra_id = Column(Integer, ForeignKey("catedras.id", ondelete="CASCADE"), nullable=False)
    curso_id = Column(Integer, ForeignKey("cursos.id", ondelete="CASCADE"), nullable=False)
    turno = Column(String(30), nullable=True)  # Mañana, Noche, Virtual
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=True)
    catedra = relationship("Catedra", back_populates="cursos")
    curso = relationship("Curso", back_populates="catedras")
    sede = relationship("Sede")

class Asignacion(Base):
    __tablename__ = "asignaciones"
    id = Column(Integer, primary_key=True, index=True)
    catedra_id = Column(Integer, ForeignKey("catedras.id"), nullable=False)
    cuatrimestre_id = Column(Integer, ForeignKey("cuatrimestres.id"), nullable=False)
    docente_id = Column(Integer, ForeignKey("docentes.id"), nullable=True)
    dia = Column(String(20), nullable=True)
    hora_inicio = Column(String(10), nullable=True)
    hora_fin = Column(String(10), nullable=True)
    modalidad = Column(String(20), nullable=False)
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=True)
    recibe_alumnos_presenciales = Column(Boolean, default=False)
    modificada = Column(Boolean, default=False)
    catedra = relationship("Catedra", back_populates="asignaciones")
    cuatrimestre = relationship("Cuatrimestre")
    docente = relationship("Docente", back_populates="asignaciones")
    sede = relationship("Sede")

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
