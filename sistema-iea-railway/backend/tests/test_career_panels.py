"""Synthetic fixtures; the imported helper enforces a disposable localhost DB."""
import unittest
import test_institution_api as base


class CareerPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.InstitutionApiTests.setUpClass()
        cls.client=base.InstitutionApiTests.client

    def setUp(self):
        base.InstitutionApiTests.setUp(self)
        base.sql("INSERT INTO sedes(id,nombre) VALUES (2,'Avellaneda')")
        base.sql("INSERT INTO plan_carrera(sede,carrera,anno,codigo_catedra,nombre_catedra) VALUES ('Caballito','Carrera de prueba','1ER AÑO','c.1','Primera'),('Avellaneda','Carrera de prueba','1ER AÑO','c.1','Primera'),('Caballito','Carrera de prueba','1ER AÑO','c.2','Segunda')")
        base.sql("INSERT INTO asignaciones(catedra_id,docente_id,cuatrimestre_id,sede_id,dia,hora_inicio,modalidad) VALUES (1,1,1,1,'Lunes','18:00','presencial'),(1,1,2,1,'Martes','19:00','presencial')")

    def rows(self,endpoint,period=1,**params):
        response=self.client.get(endpoint,params={'cuatrimestre_id':period,**params})
        self.assertEqual(response.status_code,200,response.text[:300])
        return response.json()

    def test_both_services_require_one_existing_period(self):
        for path in ('/api/plan-carrera/sugerencias','/api/sugerencias-armado'):
            self.assertEqual(self.client.get(path).status_code,422)
            self.assertEqual(self.client.get(path+'?cuatrimestre_id=999').status_code,404)

    def test_changing_period_changes_course_schedule_and_demand(self):
        def first(period):return self.rows('/api/plan-carrera/sugerencias',period)['sedes']['Caballito']['Carrera de prueba']['1ER AÑO'][0]
        self.assertEqual(first(1)['actual_tn'],'Lunes 18:00')
        self.assertEqual(first(2)['actual_tn'],'Martes 19:00')
        self.assertEqual(first(2)['inscriptos'],0)

    def test_physical_assignment_does_not_appear_in_another_campus(self):
        for path in ('/api/plan-carrera/sugerencias','/api/sugerencias-armado'):
            other=self.rows(path)['sedes']['Avellaneda']['Carrera de prueba']['1ER AÑO'][0]
            self.assertIsNone(other.get('docente',other.get('docente_actual')))
            self.assertFalse(other.get('tiene_docente',False))

    def test_own_campus_names_with_apostrophes_and_codes_are_supported(self):
        campus="Campus d'Art"
        base.sql("UPDATE plan_carrera SET sede=:s,codigo_catedra='ART101' WHERE sede='Caballito' AND codigo_catedra='c.1'",{'s':campus})
        base.sql("UPDATE catedras SET codigo='ART101' WHERE id=1")
        base.sql("UPDATE sedes SET nombre=:s WHERE id=1",{'s':campus})
        with base.InstitutionApiTests.profile(self,'institucion-ejemplo.json'):
            for path in ('/api/plan-carrera/sugerencias','/api/sugerencias-armado'):
                data=self.rows(path,sede=campus)
                self.assertEqual(list(data['sedes']),[campus])
                self.assertEqual(data['sedes'][campus]['Carrera de prueba']['1ER AÑO'][0]['codigo'],'ART101')

    def test_low_enrollment_is_reviewable_in_another_institution(self):
        with base.InstitutionApiTests.profile(self,'institucion-ejemplo.json'):
            for path in ('/api/plan-carrera/sugerencias','/api/sugerencias-armado'):
                rows=self.rows(path)['sedes']['Caballito']['Carrera de prueba']['1ER AÑO']
                self.assertEqual(next(r for r in rows if r['codigo']=='c.2')['criterio'],'REVISAR APERTURA')

    def test_iea_keeps_its_low_enrollment_rule(self):
        base.sql('DELETE FROM inscripciones WHERE catedra_id=2 AND alumno_id=10')
        rows=self.rows('/api/plan-carrera/sugerencias')['sedes']['Caballito']['Carrera de prueba']['1ER AÑO']
        self.assertEqual(next(r for r in rows if r['codigo']=='c.2')['criterio'],'ASINCRÓNICA')

    def test_suggestions_read_stored_references_and_exclude_inactive_teachers(self):
        base.sql("UPDATE docentes SET catedras_referencia='c.1',activo=TRUE WHERE id=1")
        base.sql("INSERT INTO docente_disponibilidad(docente_id,dia,hora,disponible) VALUES (1,'Miércoles','18:00',TRUE)")
        def candidate():return self.rows('/api/sugerencias-armado')['sedes']['Avellaneda']['Carrera de prueba']['1ER AÑO'][0]['sugerencia_docente']
        self.assertEqual(candidate(),'Docente Ficticio')
        base.sql('UPDATE docentes SET activo=FALSE WHERE id=1')
        self.assertIsNone(candidate())


if __name__=='__main__':unittest.main(verbosity=2)
