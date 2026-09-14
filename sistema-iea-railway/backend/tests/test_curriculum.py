import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.curriculum import load_catalog,validate_catalog,Reconciler,catalog_summary

spec=importlib.util.spec_from_file_location('build_curriculum',ROOT/'tools/build_iea_curriculum.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class CurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/'backend/app/profiles/iea_curriculum.json'
        if not path.is_file():
            raise unittest.SkipTest('Requiere el catálogo privado IEA; ver docs/PLANES_V21.md')
        cls.data=json.loads(path.read_text())

    def career(self,name):return next(c for c in self.data['careers'] if c['origen']==name)
    def plan(self,name,label):return next(p for p in self.career(name)['planes'] if p['etiqueta']==label)

    def test_banking_uses_confirmed_columns_and_preserves_missing_semester(self):
        plan=self.plan('BANCARIA','Plan 1')
        subject=next(s for s in plan['materias'] if s['nombre']=='Informática')
        self.assertEqual((subject['anio'],subject['cuatrimestre'],subject['codigo_archivo']),(1,2,'c.2'))
        practice=next(s for s in plan['materias'] if 'Acercamiento' in s['nombre'])
        self.assertIsNone(practice['cuatrimestre'])

    def test_versions_and_jurisdictions_are_not_collapsed(self):
        plans=self.career('Seguridad e Higiene')['planes']
        self.assertEqual(len(plans),6)
        self.assertEqual(sum(p['jurisdiccion']=='CABA' for p in plans),2)
        self.assertEqual(sum(p['jurisdiccion']=='Provincia de Buenos Aires' for p in plans),2)
        for p in plans:
            if p['ambito_origen']=='CIED':
                self.assertEqual(p['modalidad'],'distancia');self.assertIsNone(p['jurisdiccion'])

    def test_official_semester_is_used_even_when_old_system_differs(self):
        p=self.plan('Comercio','Plan 2')
        s=next(s for s in p['materias'] if s['nombre']=='Técnicas del Comercio Exterior')
        self.assertEqual(s['cuatrimestre'],1);self.assertEqual(s['cuatrimestre_sistema_archivo'],'2')
        p=self.plan('Trabajo social','Plan 1')
        s=next(s for s in p['materias'] if s['nombre']=='Derecho')
        self.assertIsNone(s['anio']);self.assertIsNone(s['cuatrimestre'])
        self.assertEqual(s['anio_sistema_archivo'],'1')

    def test_psychopedagogy_proposal_is_separate_from_approved_presential_plan(self):
        c=self.career('psicopedagogia');self.assertEqual(len(c['planes']),2)
        self.assertEqual(len(self.plan('psicopedagogia','Plan 1')['materias']),41)
        proposal=self.plan('psicopedagogia','Propuesta a distancia')
        self.assertEqual(len(proposal['materias']),28);self.assertEqual(proposal['resolucion'],'')
        self.assertEqual(proposal['situacion'],'por_confirmar')

    def test_hotel_conflicting_plan_labels_are_not_silently_reassigned(self):
        c=self.career('Hoteleria')
        self.assertEqual(len(self.plan('Hoteleria','Plan 5')['materias']),28)
        self.assertEqual(len(self.plan('Hoteleria','Plan 6')['materias']),0)
        self.assertEqual(len(c['materias_sin_plan']),28)
        self.assertTrue(all(any('cabecera' in n for n in s['observaciones']) for s in c['materias_sin_plan']))

    def test_future_does_not_replace_existing_plan_and_dates_are_not_invented(self):
        p=self.plan('ciencia de datos','Plan 2')
        self.assertEqual((p['inicio_informado'],p['situacion']),(2027,'futuro'))
        p=self.plan('Publicidad','Plan 1')
        self.assertEqual(p['resolucion'],'');self.assertIn('3805',p['resolucion_original'])

    def test_secondary_modules_are_distinct_from_subjects_and_no_year_is_invented(self):
        p=self.career('BCE 2026')['planes'][0]
        self.assertEqual(len(p['modulos']),6);self.assertEqual(len(p['materias']),30)
        self.assertTrue(all(s['anio'] is None for s in p['materias']))
        self.assertEqual(len(self.career('BEA')['planes'][0]['materias']),27)

    def test_empty_program_and_unassigned_rows_are_preserved(self):
        self.assertEqual(self.career('Gastronomia')['planes'],[])
        self.assertEqual(self.career('Guia de Turismo')['materias_sin_plan'][0]['origen']['fila'],21)

    def test_double_titles_are_evidence_not_duplicate_programs(self):
        self.assertEqual(len(self.data['careers']),32);self.assertEqual(len(self.data['articulations']),15)
        self.assertFalse(any('doble' in c['origen'].lower() for c in self.data['careers']))
        self.assertTrue(all(a['situacion']=='por_confirmar' for a in self.data['articulations']))

    def test_only_academic_data_is_carried_from_control_sheets(self):
        self.assertEqual(set(self.data['source']['excluded_control_sheets']),builder.CONTROL)
        for c in self.data['careers']:
            self.assertNotIn(c['origen'],builder.CONTROL)
        self.assertNotIn('responsable',json.dumps(self.data).lower())

    def test_schema_rejects_cross_institution_and_duplicate_ids(self):
        validate_catalog(self.data,'iea')
        with self.assertRaises(ValueError):validate_catalog(self.data,'otro')
        duplicate=copy.deepcopy(self.data);duplicate['careers'].append(duplicate['careers'][0])
        with self.assertRaises(ValueError):validate_catalog(duplicate,'iea')

    def test_other_institution_never_receives_iea_default(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(load_catalog('otro')['careers'],[])

    def test_malformed_catalog_records_are_rejected_before_rendering(self):
        invalids=[[],None,{**self.data,'careers':[None]},{**self.data,'source':[]}]
        for field,value in (('planes',None),('planes',[None]),('nombre',{})):
            data=copy.deepcopy(self.data);data['careers'][0][field]=value;invalids.append(data)
        for field,value in (('materias',[None]),('modulos',None),('observaciones',[{}]),('jurisdiccion',{})):
            data=copy.deepcopy(self.data);data['careers'][0]['planes'][0][field]=value;invalids.append(data)
        for data in invalids:
            with self.subTest(data_type=type(data).__name__),self.assertRaises(ValueError):
                validate_catalog(data,'iea')

    def test_invalid_subject_positions_fail_but_unconfirmed_positions_remain_allowed(self):
        for field,value in (('anio',True),('cuatrimestre',0),('anio','1'),('nombre',{}),('origen',[])):
            data=copy.deepcopy(self.data)
            data['careers'][0]['planes'][0]['materias'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):validate_catalog(data,'iea')
        other=copy.deepcopy(self.data);other['institution_id']='otra'
        other['careers'][0]['planes'][0]['materias'][0].update(anio=None,cuatrimestre=None)
        self.assertIs(validate_catalog(other,'otra'),other)

    def test_current_catalog_codes_are_authoritative_and_source_conflict_stays_pending(self):
        catalog=[{'id':1,'codigo':'c.1','nombre':'Administración'},{'id':2,'codigo':'c.2','nombre':'Informática I'}]
        original=copy.deepcopy(catalog);r=Reconciler(catalog)
        row=next(s for s in self.plan('Administracion','Plan 1')['materias'] if s['nombre']=='Computacion I')
        result=r.subject(row)
        self.assertEqual(row['codigo_archivo'],'c.1')
        self.assertIsNone(result['vinculo']['catedra']);self.assertEqual(result['vinculo']['estado'],'revisar_asociacion')
        self.assertEqual(catalog,original)
        exact=r.subject({**row,'nombre':'Administración','nombre_sistema_archivo':''})
        self.assertEqual(exact['vinculo']['catedra']['codigo'],'c.1')

    def test_name_match_with_another_code_is_a_candidate_not_an_automatic_recode(self):
        r=Reconciler([{'id':42,'codigo':'MAT-42','nombre':'Cálculo'}])
        source={'id':'s','nombre':'Cálculo','codigo_archivo':'c.42'}
        out=r.subject(source)
        self.assertIsNone(out['vinculo']['catedra']);self.assertEqual(out['vinculo']['candidatas'][0]['codigo'],'MAT-42')
        self.assertEqual(source['codigo_archivo'],'c.42')

    def test_summary_reads_do_not_mutate_source(self):
        before=copy.deepcopy(self.data)
        result=catalog_summary(self.data,Reconciler([]))
        self.assertEqual(self.data,before);self.assertNotIn('materias',result['careers'][0]['planes'][0])

    def test_plan_block_does_not_leak_to_the_next_table_without_a_header(self):
        self.assertEqual(len(self.plan('Comercio','Plan 5')['materias']),23)
        self.assertEqual(len(self.plan('Seguridad e Higiene','Plan 6')['materias']),24)


if __name__=='__main__':unittest.main(verbosity=2)
