"""Institutional curriculum catalogs. No writes to operational scheduling tables."""
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import unicodedata
from app.curriculum_bundle import read_bundle

ROOT=Path(__file__).resolve().parent


def norm(value):
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in unicodedata.normalize('NFD',str(value or '').lower())
                                         if unicodedata.category(c) != 'Mn'))


def validate_catalog(data, institution_id):
    if not isinstance(data,dict) or data.get('schema_version')!=1 or data.get('institution_id')!=institution_id:
        raise ValueError('El catálogo de planes no corresponde a esta institución o versión')
    def objects(value):
        if not isinstance(value,list) or any(not isinstance(item,dict) for item in value):
            raise ValueError('El catálogo contiene una lista de registros incompleta')
        return value

    def texts(item, fields):
        if any(item.get(field) is not None and not isinstance(item[field],str) for field in fields):
            raise ValueError('El catálogo contiene un campo de texto inválido')

    def positive_or_missing(value):
        if value is not None and (type(value) is not int or value<1):
            raise ValueError('El catálogo contiene un año o cuatrimestre inválido')

    def named(item):
        if not isinstance(item.get('nombre'),str) or not item['nombre'].strip():
            raise ValueError('El catálogo contiene un registro sin nombre')

    def notes(item):
        values=item.get('observaciones',[])
        if not isinstance(values,list) or any(not isinstance(v,str) for v in values):
            raise ValueError('El catálogo contiene observaciones inválidas')
        origin=item.get('origen')
        if origin is not None:
            if not isinstance(origin,dict): raise ValueError('Origen académico inválido')
            texts(origin,('hoja','celda'))
            positive_or_missing(origin.get('fila'))

    if 'source' not in data: raise ValueError('Fuente del catálogo ausente')
    if data['source'] is not None:
        if not isinstance(data['source'],dict): raise ValueError('Fuente del catálogo inválida')
        texts(data['source'],('filename','revision','sha256'))
    seen=set()
    def unique(item):
        ident=item.get('id')
        if not isinstance(ident,str) or not ident or ident in seen: raise ValueError('Identificadores de catálogo ausentes o duplicados')
        seen.add(ident)

    def subjects(value):
        for subject in objects(value):
            unique(subject); named(subject); notes(subject)
            texts(subject,('codigo_archivo','nombre_sistema_archivo','correlatividades',
                           'anio_sistema_archivo','cuatrimestre_sistema_archivo','plan_origen'))
            positive_or_missing(subject.get('anio'))
            positive_or_missing(subject.get('cuatrimestre'))

    for career in objects(data.get('careers')):
        unique(career); named(career); texts(career,('nivel','origen'))
        for plan in objects(career.get('planes')):
            unique(plan); notes(plan)
            if plan.get('carrera_id')!=career['id']: raise ValueError('Plan vinculado a una carrera incorrecta')
            texts(plan,('etiqueta','nombre_oficial','resolucion','modalidad','jurisdiccion',
                        'titulo','situacion','nota_vigencia'))
            positive_or_missing(plan.get('inicio_informado'))
            subjects(plan.get('materias'))
            for module in objects(plan.get('modulos',[])):
                named(module); notes(module); texts(module,('codigo_archivo',))
                positive_or_missing(module.get('cuatrimestre'))
        subjects(career.get('materias_sin_plan',[]))
    for articulation in objects(data.get('articulations')):
        unique(articulation); named(articulation); notes(articulation)
        for block in objects(articulation.get('bloques')):
            named(block)
            subjects(block.get('materias'))
    return data


@lru_cache(maxsize=8)
def _load(path, institution_id):
    return validate_catalog(json.loads(Path(path).read_text()),institution_id)


def load_catalog(institution_id):
    configured=os.environ.get('CURRICULUM_CATALOG_PATH')
    if configured:
        path=Path(configured)
        if not path.is_absolute(): path=ROOT/path
    else:
        bundle=read_bundle()
        if bundle is not None:
            return validate_catalog(bundle,institution_id)
        if institution_id=='iea' and (ROOT/'profiles/iea_curriculum.json').is_file():
            path=ROOT/'profiles/iea_curriculum.json'
        else:
            return {'schema_version':1,'institution_id':institution_id,'source':None,'careers':[],'articulations':[]}
    return _load(str(path),institution_id)


class Reconciler:
    def __init__(self, catedras):
        self.codes=defaultdict(list);self.names=defaultdict(list)
        for row in catedras:
            item={'id':row['id'],'codigo':row['codigo'],'nombre':row['nombre']}
            self.codes[norm(item['codigo'])].append(item);self.names[norm(item['nombre'])].append(item)

    def subject(self, raw):
        item=deepcopy(raw)
        names=[norm(raw.get('nombre_sistema_archivo')),norm(raw.get('nombre'))]
        names=[n for n in names if n]
        by_code=self.codes.get(norm(raw.get('codigo_archivo')),[])
        candidates={r['id']:r for name in names for r in self.names.get(name,[])}
        for r in by_code: candidates[r['id']]=r
        confirmed=None
        if len(by_code)==1 and norm(by_code[0]['nombre']) in names:
            confirmed=by_code[0];status='coincide'
        elif by_code: status='revisar_asociacion'
        elif candidates: status='revisar_codigo'
        elif norm(raw['nombre']).startswith('edi') and not raw.get('codigo_archivo'): status='espacio_edi'
        else: status='sin_vinculo'
        # A source code alone is insufficient to associate Computación with Administración.
        item['vinculo']={'estado':status,'catedra':confirmed,'candidatas':list(candidates.values())}
        return item

    def plan(self, plan):
        result=deepcopy(plan);result['materias']=[self.subject(s) for s in plan['materias']]
        result['resumen']=self.counts(result['materias'])
        return result

    @staticmethod
    def counts(subjects):
        return {'materias':len(subjects),
                'vinculadas':sum(s['vinculo']['estado']=='coincide' for s in subjects),
                'por_revisar':sum(s['vinculo']['estado'] not in ('coincide','espacio_edi') for s in subjects),
                'datos_academicos_pendientes':sum(s.get('anio') is None or s.get('cuatrimestre') is None for s in subjects)}


def catalog_summary(catalog,reconciler):
    result={'schema_version':1,'institution_id':catalog['institution_id'],'source':catalog['source'],'careers':[],'articulations':[]}
    for career in catalog['careers']:
        row={k:v for k,v in career.items() if k not in ('planes','materias_sin_plan')}
        row['planes']=[];row['materias_sin_plan']=len(career.get('materias_sin_plan',[]))
        for plan in career['planes']:
            parsed=reconciler.plan(plan)
            row['planes'].append({k:v for k,v in parsed.items() if k not in ('materias','modulos')})
        result['careers'].append(row)
    for item in catalog['articulations']:
        result['articulations'].append({**{k:v for k,v in item.items() if k!='bloques'},
                                       'materias':sum(len(b['materias']) for b in item['bloques'])})
    return result
