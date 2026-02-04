from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text, Time
from sqlalchemy.orm import relationship
from app.database import Base

class Sede(Base):
    __tablename__ = "sedes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), default="bg-blue-500")
    
    # Relación con docentes (muchos a muchos)
    docentes = relationship("DocenteSede", back_populates="sede")

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
    # El link de meet es único por cátedra (compartido entre turnos y sedes)
    link_meet = Column(String(300), nullable=True)
    
    asignaciones = relationship("Asignacion", back_populates="catedra")
    inscripciones = relationship("Inscripcion", back_populates="catedra")

class Docente(Base):
    """
    Docente SIN sede fija por defecto.
    Las sedes se asignan a través de la tabla DocenteSede.
    El tipo de modalidad se deduce automáticamente de sus asignaciones:
    - PRESENCIAL_VIRTUAL: tiene al menos una asignación con recibe_alumnos_presenciales=True
    - SEDE_VIRTUAL: tiene asignaciones con sede pero ninguna recibe alumnos presenciales
    - REMOTO: solo tiene asignaciones sin sede física (trabaja desde casa)
    """
    __tablename__ = "docentes"
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(150))
    
    # Relaciones
    sedes = relationship("DocenteSede", back_populates="docente", cascade="all, delete-orphan")
    asignaciones = relationship("Asignacion", back_populates="docente")

class DocenteSede(Base):
    """
    Tabla intermedia para relación muchos a muchos entre Docente y Sede.
    Permite que un docente esté asignado a múltiples sedes.
    """
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

class Asignacion(Base):
    """
    Una cátedra puede tener múltiples asignaciones por cuatrimestre.
    
    Campos clave:
    - modalidad: 'virtual_tm', 'virtual_tn', 'presencial', 'asincronica'
    - sede_id: sede FÍSICA donde el docente da la clase (puede ser NULL si es remoto)
    - recibe_alumnos_presenciales: indica si van alumnos a la sede a ver la clase
    
    Tipos de docente (deducidos de las asignaciones):
    1. Presencial + Virtual: sede_id != NULL AND recibe_alumnos_presenciales = True
    2. Sede Virtual: sede_id != NULL AND recibe_alumnos_presenciales = False
    3. Remoto: sede_id = NULL (trabaja desde casa)
    
    Regla de solapamiento:
    - La MISMA cátedra NO puede estar en el MISMO día y hora, sin importar la sede
    - (porque comparten el link de Meet)
    """
    __tablename__ = "asignaciones"
    id = Column(Integer, primary_key=True, index=True)
    catedra_id = Column(Integer, ForeignKey("catedras.id"), nullable=False)
    cuatrimestre_id = Column(Integer, ForeignKey("cuatrimestres.id"), nullable=False)
    docente_id = Column(Integer, ForeignKey("docentes.id"), nullable=True)
    
    # Horario
    dia = Column(String(20), nullable=True)  # Lunes, Martes, etc.
    hora_inicio = Column(String(10), nullable=True)  # "08:00"
    hora_fin = Column(String(10), nullable=True)  # "10:00"
    
    # Modalidad de la CLASE (no del docente)
    modalidad = Column(String(20), nullable=False)  # virtual_tm, virtual_tn, presencial, asincronica
    
    # Sede física donde el docente da la clase (NULL = remoto desde casa)
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=True)
    
    # ¿Recibe alumnos presenciales en la sede?
    # True = docente tipo "Presencial + Virtual"
    # False = docente tipo "Sede Virtual" (va a la sede pero solo da virtual)
    recibe_alumnos_presenciales = Column(Boolean, default=False)
    
    modificada = Column(Boolean, default=False)
    
    # Relaciones
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
