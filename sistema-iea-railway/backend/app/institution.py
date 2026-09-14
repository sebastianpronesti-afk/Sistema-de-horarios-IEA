"""Reglas institucionales compartidas por API, cálculos e interfaz.

Se carga un perfil por despliegue. Esto no implementa aislamiento multiinstitución.
Un perfil explícito inválido detiene el arranque: nunca aplica reglas IEA por error.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Mapping


@dataclass(frozen=True)
class Institution:
    id: str
    nombre: str
    titulo: str
    minimo_inscriptos_apertura: int
    alumnos_por_docente: int
    duracion_clase_minutos: int
    alias_carreras: Mapping[str, str]
    schema_version: int = 1
    corte_turno_minutos: int = 900

    def requiere_docente(self, total: int) -> bool:
        return total >= self.minimo_inscriptos_apertura

    def docentes_sugeridos(self, total: int) -> int:
        if not self.requiere_docente(total):
            return 0
        return (total + self.alumnos_por_docente - 1) // self.alumnos_por_docente

    def public_config(self) -> dict:
        return {name: getattr(self, name) for name in (
            'schema_version', 'id', 'nombre', 'titulo',
            'minimo_inscriptos_apertura', 'alumnos_por_docente',
            'duracion_clase_minutos', 'corte_turno_minutos',
        )}


def load_institution(path=None) -> Institution:
    selected = path if path is not None else os.environ.get('INSTITUTION_CONFIG')
    source = Path(selected) if selected else Path(__file__).parent / 'profiles' / 'iea.json'
    with source.open(encoding='utf-8') as file:
        data = json.load(file)
    required = {
        'schema_version', 'id', 'nombre', 'titulo', 'minimo_inscriptos_apertura',
        'alumnos_por_docente', 'duracion_clase_minutos', 'alias_carreras',
    }
    if not isinstance(data, dict) or not required.issubset(data) or set(data)-required-{'corte_turno_minutos'}:
        raise ValueError('El perfil institucional debe incluir únicamente los campos del esquema v1')
    data.setdefault('corte_turno_minutos',900)
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('Versión de perfil institucional no soportada')
    for name in ('id', 'nombre', 'titulo'):
        if not isinstance(data[name], str) or not data[name].strip() or len(data[name]) > 120:
            raise ValueError(f'Perfil institucional: {name} debe ser un texto de 1 a 120 caracteres')
        data[name] = data[name].strip()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', data['id']):
        raise ValueError('El identificador institucional debe usar minúsculas, números, guion o guion bajo')
    for name, maximum in (
        ('minimo_inscriptos_apertura', 100000),
        ('alumnos_por_docente', 100000),
        ('duracion_clase_minutos', 1440),
        ('corte_turno_minutos',1439),
    ):
        if type(data[name]) is not int or not 1 <= data[name] <= maximum:
            raise ValueError(f'Perfil institucional: {name} debe ser un entero entre 1 y {maximum}')
    aliases = data['alias_carreras']
    if not isinstance(aliases, dict) or any(
        not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
        for k, v in aliases.items()
    ):
        raise ValueError('alias_carreras debe vincular nombres no vacíos con nombres del plan')
    normalized = {k.strip().upper(): v.strip().upper() for k, v in aliases.items()}
    if len(normalized) != len(aliases):
        raise ValueError('alias_carreras contiene nombres equivalentes duplicados')
    data['alias_carreras'] = normalized
    return Institution(**data)


INSTITUCION = load_institution()
