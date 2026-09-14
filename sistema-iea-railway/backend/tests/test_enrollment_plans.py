"""No real students: optional plans must not invent certainty or change demand."""
from copy import deepcopy
from unittest.mock import patch
import os
import unittest
import test_academic_workflow as academic
import test_institution_api as base
from app import academic_store as store, curriculum_routes as routes, enrollment_routes
from app.institution import load_institution


class EnrollmentPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.InstitutionApiTests.setUpClass();cls.client=base.InstitutionApiTests.client

    def setUp(self):
        base.InstitutionApiTests.setUp(self)
        self.source=academic.fixture()
        other=deepcopy(self.source['careers'][0]);other.update(id='other',nombre='Otra carrera')
        other['planes']=[{'id':'other-plan','carrera_id':'other','etiqueta':'Otro','materias':[]}]
        other['materias_sin_plan']=[];self.source['careers'].append(other)
        for target in (store,routes):
            p=patch.object(target,'load_catalog',side_effect=lambda *_:deepcopy(self.source));p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{'BOOTSTRAP_EDITOR_PASSWORD':'fixture-editor-only','BOOTSTRAP_CONSULTA_PASSWORD':'fixture-reader-only'});p.start();self.addCleanup(p.stop)
        base.sql("INSERT INTO cursos(id,nombre,sede_id) VALUES(1,'Carrera informada en origen',1),(2,'Segundo curso',1)")
        base.sql('UPDATE inscripciones SET curso_id=1')

    def get(self,path):
        r=self.client.get(path);self.assertEqual(r.status_code,200,r.text);return r.json()

    def associate(self,course=1,career='career',period=1,**overrides):
        data=self.get(f'/api/inscripciones-planes/{period}/cursos/{course}')
        return self.client.put(f'/api/inscripciones-planes/{period}/cursos/{course}',json={
            'clave_edicion':'fixture-editor-only','career_id':career,'catalog_revision':data['catalog_revision'],
            'revision':data['course']['revision'],'source_token':data['course']['source_token'],**overrides})

    def confirm(self,plan='p1',student=1,course=1,period=1,**overrides):
        data=self.get(f'/api/inscripciones-planes/{period}/cursos/{course}')
        row=next(r for r in data['rows'] if r['alumno_id']==student)
        return self.client.put(f'/api/inscripciones-planes/{period}/cursos/{course}/alumnos/{student}',json={
            'clave_edicion':'fixture-editor-only','plan_id':plan,'nota':'Confirmación ficticia',
            'catalog_revision':data['catalog_revision'],'course_revision':row['course_revision'],
            'revision':row['revision'],'source_token':row['source_token'],**overrides})

    def test_read_preserves_known_course_all_plans_pending_and_writes_nothing(self):
        index=self.get('/api/inscripciones-planes/1')
        row=index['courses'][0]
        self.assertEqual(row['carrera_informada'],'Carrera informada en origen')
        self.assertEqual((row['alumnos'],row['planes_confirmados'],row['planes_pendientes']),(101,0,101))
        data=self.get('/api/inscripciones-planes/1/cursos/1')
        self.assertEqual(data['total'],101);self.assertEqual(len(data['rows']),50)
        self.assertTrue(all(r['plan_id'] is None for r in data['rows']))
        self.assertEqual(base.sql('SELECT count(*) FROM academic_documents')[0][0],0)

    def test_associating_course_does_not_assign_plans_or_change_original_registrations(self):
        before=base.sql('SELECT * FROM inscripciones ORDER BY id')
        self.assertEqual(self.associate().status_code,200)
        data=self.get('/api/inscripciones-planes/1/cursos/1')
        self.assertTrue(all(r['career_id']=='career' and r['plan_id'] is None for r in data['rows']))
        self.assertEqual(before,base.sql('SELECT * FROM inscripciones ORDER BY id'))
        view=self.get('/api/planificacion/1/planes/p1')['materias'][0]
        self.assertEqual(view['inscriptos'],101)
        self.assertEqual(view['detalle_inscriptos']['plan_pendiente'],101)
        self.assertEqual(view['detalle_inscriptos']['plan_confirmado'],0)

    def test_iea_imported_career_text_is_read_without_a_course_foreign_key(self):
        base.sql("UPDATE inscripciones SET curso_id=NULL,curso_nombre='Carrera de origen IEA - CIED'")
        row=self.get('/api/inscripciones-planes/1')['courses'][0]
        self.assertEqual(row['carrera_informada'],'Carrera de origen IEA - CIED')
        self.assertLess(row['curso_id'],0)
        self.assertEqual((row['alumnos'],row['planes_pendientes']),(101,101))
        self.assertEqual(self.associate(course=row['curso_id']).status_code,200)
        self.assertEqual(self.confirm(course=row['curso_id']).status_code,200)
        self.assertEqual(base.sql('SELECT count(*) FROM inscripciones WHERE curso_id IS NOT NULL')[0][0],0)
        self.assertEqual(self.get('/api/inscripciones-planes/1')['courses'][0]['planes_confirmados'],1)

    def test_different_imported_careers_remain_separate_even_when_sharing_student_and_chair(self):
        base.sql("UPDATE inscripciones SET curso_id=NULL,curso_nombre='Primera carrera'")
        base.sql("INSERT INTO inscripciones(alumno_id,catedra_id,cuatrimestre_id,curso_nombre) VALUES(1,1,1,'Segunda carrera')")
        rows=self.get('/api/inscripciones-planes/1')['courses']
        self.assertEqual({r['carrera_informada'] for r in rows},{'Primera carrera','Segunda carrera'})
        self.assertEqual(len({r['curso_id'] for r in rows}),2)
        self.assertEqual(self.get('/api/planificacion/1/planes/p1')['materias'][0]['inscriptos'],101)

    def test_confirm_only_same_career_and_pending_can_be_restored(self):
        self.associate()
        self.assertEqual(self.confirm('other-plan').status_code,422)
        self.assertEqual(self.confirm().status_code,200)
        row=self.get('/api/inscripciones-planes/1/cursos/1')['course']
        self.assertEqual((row['planes_confirmados'],row['planes_pendientes']),(1,100))
        self.assertEqual(self.confirm(None).status_code,200)
        self.assertEqual(self.get('/api/inscripciones-planes/1/cursos/1')['course']['planes_confirmados'],0)

    def test_confirmations_are_isolated_by_period_and_course(self):
        base.sql('INSERT INTO inscripciones(alumno_id,catedra_id,cuatrimestre_id,curso_id) VALUES(1,1,2,1),(1,1,1,2)')
        self.associate();self.confirm()
        for path in ('/api/inscripciones-planes/2/cursos/1','/api/inscripciones-planes/1/cursos/2'):
            self.assertIsNone(self.get(path)['rows'][0]['plan_id'])

    def test_stale_confirmations_and_reused_source_identifiers_are_rejected(self):
        self.associate();self.assertEqual(self.confirm().status_code,200)
        self.assertEqual(self.confirm('p2',revision=0).status_code,409)
        self.assertEqual(self.confirm('p2',course_revision=0).status_code,409)
        self.assertEqual(self.confirm('p2',source_token='old').status_code,409)
        base.sql("UPDATE alumnos SET dni='99999999' WHERE id=1")
        row=next(r for r in self.get('/api/inscripciones-planes/1/cursos/1')['rows'] if r['alumno_id']==1)
        self.assertIsNone(row['plan_id']);self.assertTrue(row['confirmacion_a_revisar'])
        self.assertEqual(row['nota'],'')

    def test_changing_career_invalidates_old_plan_confirmation(self):
        self.associate();self.confirm()
        self.assertEqual(self.associate(career='other').status_code,200)
        row=next(r for r in self.get('/api/inscripciones-planes/1/cursos/1')['rows'] if r['alumno_id']==1)
        self.assertEqual(row['career_id'],'other');self.assertIsNone(row['plan_id'])
        self.assertTrue(row['confirmacion_a_revisar'])

    def test_demand_deduplicates_and_never_assigns_pending_students_to_each_plan(self):
        base.sql('INSERT INTO inscripciones(alumno_id,catedra_id,cuatrimestre_id,curso_id) VALUES(1,1,1,1)')
        self.associate();self.confirm()
        a=self.get('/api/planificacion/1/planes/p1')['materias'][0]
        b=self.get('/api/planificacion/1/planes/p2')['materias'][0]
        self.assertEqual((a['inscriptos'],b['inscriptos']),(101,101))
        self.assertEqual((a['detalle_inscriptos']['plan_confirmado'],b['detalle_inscriptos']['plan_confirmado']),(1,0))
        self.assertEqual((a['detalle_inscriptos']['plan_pendiente'],b['detalle_inscriptos']['plan_pendiente']),(100,100))
        self.assertEqual(a['detalle_inscriptos']['carrera'],101)

    def test_no_course_cannot_be_assumed_one_career_and_writer_key_is_required(self):
        base.sql('UPDATE inscripciones SET curso_id=NULL')
        self.assertEqual(self.associate(course=0).status_code,422)
        self.assertEqual(self.associate(course=0,clave_edicion='fixture-reader-only').status_code,401)
        self.assertEqual(self.confirm(course=0,clave_edicion=None).status_code,401)
        self.assertEqual(base.sql('SELECT count(*) FROM academic_documents')[0][0],0)

    def test_generic_institution_uses_same_optional_plan_contract(self):
        self.source['institution_id']='institucion-ejemplo'
        profile=load_institution(base.PROFILES/'institucion-ejemplo.json')
        self.source['institution_id']=profile.id
        with patch.object(enrollment_routes,'INSTITUCION',profile):
            self.assertEqual(self.associate().status_code,200)
            self.assertEqual(self.confirm().status_code,200)
        # Returning to the IEA profile does not read the other profile's documents.
        self.source['institution_id']='iea'
        self.assertEqual(self.get('/api/inscripciones-planes/1/cursos/1')['course']['planes_confirmados'],0)

    def test_pending_subject_can_link_any_chair_without_selecting_a_plan(self):
        base.sql("INSERT INTO catedras(id,codigo,nombre) VALUES(99,'c.99','Cátedra fuera de las candidatas')")
        payload={'clave_edicion':'fixture-editor-only','operation':'pending_subject','career_id':'career',
                 'subject_id':'pending','revision':0,'changes':{'catedra_id':99,'anio':2,'cuatrimestre':1}}
        r=self.client.post('/api/planes-estudio/editar',json=payload);self.assertEqual(r.status_code,200,r.text)
        row=self.get('/api/planes-estudio/carreras/career/pendientes')['materias'][0]
        self.assertEqual(row['id'],'pending');self.assertEqual(row['vinculo']['catedra']['id'],99)
        self.assertEqual(len(self.get('/api/planes-estudio/p1')['materias']),2)
        payload.update(revision=1,changes={'correlativa_ids':['s1']})
        self.assertEqual(self.client.post('/api/planes-estudio/editar',json=payload).status_code,422)

    def test_search_pagination_and_empty_offer_are_explicit(self):
        self.assertEqual(len(self.get('/api/inscripciones-planes/1/cursos/1?offset=100')['rows']),1)
        self.assertEqual(self.get('/api/inscripciones-planes/1/cursos/1?q=98000001')['total'],1)
        self.assertEqual(self.get('/api/planificacion/1/planes/p1')['estado_oferta'],'sin_configurar')
        self.client.put('/api/planificacion/1/planes/p1/oferta',json={'clave_edicion':'fixture-editor-only','revision':0,'catalog_revision':0,'materia_ids':[]})
        self.assertEqual(self.get('/api/planificacion/1/planes/p1')['estado_oferta'],'configurada')

if __name__=='__main__': unittest.main()
