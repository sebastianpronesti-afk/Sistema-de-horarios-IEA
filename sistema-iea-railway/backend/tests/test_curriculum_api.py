"""Read-only catalog integration against the disposable database used by the suite."""
from unittest.mock import patch
import json
import os
from pathlib import Path
import tempfile
import unittest
import test_institution_api as base
from app import curriculum_routes as routes
from app.curriculum import load_catalog
from app.institution import load_institution


class CurriculumApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (base.PROFILES/'iea_curriculum.json').is_file():
            raise unittest.SkipTest('Requiere el catálogo privado IEA; ver docs/PLANES_V21.md')
        base.InstitutionApiTests.setUpClass();cls.client=base.InstitutionApiTests.client

    def setUp(self):
        base.InstitutionApiTests.setUp(self)
        base.sql("UPDATE catedras SET nombre='Administración' WHERE id=1")
        base.sql("UPDATE catedras SET nombre='Informática I' WHERE id=2")

    def test_catalog_works_without_a_period_and_does_not_mutate_scheduling_data(self):
        before={table:base.sql('SELECT * FROM '+table+' ORDER BY id') for table in ('catedras','plan_carrera','asignaciones','cursos')}
        response=self.client.get('/api/planes-estudio');self.assertEqual(response.status_code,200)
        data=response.json();self.assertEqual(len(data['careers']),32)
        pid=next(c for c in data['careers'] if c['origen']=='BANCARIA')['planes'][0]['id']
        response=self.client.get('/api/planes-estudio/'+pid);self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['materias'][0]['vinculo']['catedra']['codigo'],'c.1')
        after={table:base.sql('SELECT * FROM '+table+' ORDER BY id') for table in before}
        self.assertEqual(before,after)

    def test_cross_profile_catalog_does_not_expose_iea_plans(self):
        pid=load_catalog('iea')['careers'][0]['planes'][0]['id']
        with patch.object(routes,'INSTITUCION',load_institution(base.PROFILES/'institucion-ejemplo.json')):
            data=self.client.get('/api/planes-estudio').json();self.assertEqual(data['careers'],[])
            self.assertEqual(self.client.get('/api/planes-estudio/'+pid).status_code,404)

    def test_articulations_and_pending_subjects_are_accessible_separately(self):
        data=self.client.get('/api/planes-estudio').json()
        ident=data['articulations'][0]['id']
        self.assertEqual(self.client.get('/api/planes-estudio/articulaciones/'+ident).status_code,200)
        hotel=next(c for c in data['careers'] if c['origen']=='Hoteleria')
        rows=self.client.get('/api/planes-estudio/carreras/'+hotel['id']+'/pendientes').json()['materias']
        self.assertEqual(len(rows),28)
        for path in ('/unknown','/articulaciones/unknown','/carreras/unknown/pendientes'):
            self.assertEqual(self.client.get('/api/planes-estudio'+path).status_code,404)

    def test_bad_config_is_visible_and_never_falls_back_to_another_profile(self):
        with patch.object(routes,'load_catalog',side_effect=ValueError('invalid')):
            self.assertEqual(self.client.get('/api/planes-estudio').status_code,503)

    def test_malformed_config_file_returns_an_explained_error_on_all_catalog_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'catalog.json';path.write_text(json.dumps([]))
            with patch.dict(os.environ,{'CURRICULUM_CATALOG_PATH':str(path)}):
                for suffix in ('','/unknown','/articulaciones/unknown','/carreras/unknown/pendientes'):
                    response=self.client.get('/api/planes-estudio'+suffix)
                    self.assertEqual(response.status_code,503)
                    self.assertEqual(response.json()['detail'],'No se pudo cargar el catálogo institucional de planes')


if __name__=='__main__':unittest.main(verbosity=2)
