"""Curriculum edits and scheduling against a disposable database; no private IEA source."""
from copy import deepcopy
from unittest.mock import patch
import os
import unittest
import test_institution_api as base
from app import academic_store as store, curriculum_routes as routes
from app.academic_planning import minutes, interval
from app.models.models import Asignacion

def fixture():
    def subject(ident,name,chair=None):
        s={"id":ident,"nombre":name,"anio":1,"cuatrimestre":1,"codigo_archivo":"",
           "correlatividades":"","observaciones":[]}
        if chair is not None: s["catedra_id"]=chair
        return s
    def plan(ident,subjects):
        return {"id":ident,"carrera_id":"career","etiqueta":ident,"nombre_oficial":"Carrera ficticia",
                "materias":subjects,"modulos":[],"observaciones":[]}
    return {"schema_version":1,"institution_id":"iea","source":None,"articulations":[],
            "careers":[{"id":"career","nombre":"Carrera ficticia","nivel":"terciario",
                "planes":[plan("p1",[subject("s1","Materia de prueba",1),subject("s2","Materia de prueba 2",2)]),
                          plan("p2",[subject("s3","Materia compartida",1)])],
                "materias_sin_plan":[subject("pending","Materia pendiente")]}]}

class AcademicWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.InstitutionApiTests.setUpClass();cls.client=base.InstitutionApiTests.client
    def setUp(self):
        base.InstitutionApiTests.setUp(self)
        self.source=fixture()
        for target in (store,routes):
            p=patch.object(target,"load_catalog",side_effect=lambda *_:deepcopy(self.source));p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{"BOOTSTRAP_EDITOR_PASSWORD":"fixture-editor-only","BOOTSTRAP_CONSULTA_PASSWORD":"fixture-reader-only"});p.start();self.addCleanup(p.stop)
        base.sql("UPDATE docentes SET catedras_referencia='c.1,c.2',activo=true WHERE id=1")
        base.sql("INSERT INTO docente_sede(docente_id,sede_id) VALUES(1,1)")
        for time in ("09:00","09:30","10:00","10:30"):
            base.sql("INSERT INTO docente_disponibilidad(docente_id,dia,hora,disponible) VALUES(1,'Lunes',:time,true)",{"time":time})
    def edit(self,**data):
        return self.client.post("/api/planes-estudio/editar",json={"clave_edicion":"fixture-editor-only",**data})
    def offer(self,plan="p1",ids=None,revision=0,period=1):
        return self.client.put(f"/api/planificacion/{period}/planes/{plan}/oferta",json={
            "clave_edicion":"fixture-editor-only","revision":revision,"catalog_revision":self.client.get("/api/planes-estudio").json()["revision"],"materia_ids":ids if ids is not None else ["s1"]})
    def assignment(self,**data):
        view=self.client.get("/api/planificacion/1/planes/p1").json()
        return self.client.post("/api/planificacion/1/planes/p1/materias/s1/asignar",json={
            "clave_edicion":"fixture-editor-only","docente_id":1,"dia":"Lunes","hora_inicio":"09:00","hora_fin":"10:30",
            "modalidad":"presencial","sede_id":1,"catalog_revision":view["revision"],"oferta_revision":view["oferta_revision"],**data})
    def test_editor_required_and_reader_cannot_write(self):
        for key in (None,"fixture-reader-only","wrong"):
            response=self.client.post("/api/planes-estudio/editar",json={"operation":"plan","plan_id":"p1","revision":0,"changes":{"resolucion":"Nueva"},"clave_edicion":key})
            self.assertEqual(response.status_code,401)
        self.assertEqual(base.sql("SELECT count(*) FROM academic_documents")[0][0],0)
    def test_edit_persists_academic_fields_and_link_without_rewriting_chair_or_source(self):
        before=deepcopy(self.source)
        r=self.edit(operation="subject",plan_id="p1",subject_id="s2",revision=0,changes={"anio":2,"cuatrimestre":2,"catedra_id":1,"correlativa_ids":["s1"]})
        self.assertEqual(r.status_code,200,r.text)
        detail=self.client.get("/api/planes-estudio/p1").json()
        subject=detail["materias"][1]
        self.assertEqual((subject["anio"],subject["cuatrimestre"]),(2,2))
        self.assertEqual(subject["vinculo"]["catedra"]["id"],1)
        self.assertEqual(subject["vinculo"]["estado"],"confirmado")
        self.assertEqual(self.source,before)
        self.assertEqual(base.sql("SELECT nombre FROM catedras WHERE id=1")[0][0],"Materia de prueba")
        self.assertEqual(base.sql("SELECT count(*) FROM academic_changes")[0][0],1)
    def test_stale_edit_does_not_overwrite_saved_plan(self):
        first=self.edit(operation="plan",plan_id="p1",revision=0,changes={"resolucion":"RES-A"})
        self.assertEqual(first.status_code,200,first.text)
        stale=self.edit(operation="plan",plan_id="p1",revision=0,changes={"resolucion":"RES-B"})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(self.client.get("/api/planes-estudio/p1").json()["resolucion"],"RES-A")
    def test_correlatives_reject_other_plan_self_reference_and_cycles(self):
        for ids in (["s3"],["s1"],["missing"]):
            r=self.edit(operation="subject",plan_id="p1",subject_id="s1",revision=0,changes={"correlativa_ids":ids})
            self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(self.edit(operation="subject",plan_id="p1",subject_id="s1",revision=0,changes={"correlativa_ids":["s2"]}).status_code,200)
        self.assertEqual(self.edit(operation="subject",plan_id="p1",subject_id="s2",revision=1,changes={"correlativa_ids":["s1"]}).status_code,422)
        self.assertEqual(self.client.get("/api/planes-estudio/p1").json()["revision"],1)
    def test_move_preserves_subject_identity_and_removes_pending_record(self):
        r=self.edit(operation="move",career_id="career",plan_id="p1",subject_id="pending",revision=0,changes={"catedra_id":2,"anio":2,"cuatrimestre":1,"correlativa_ids":["s1"]})
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn("pending",[s["id"] for s in self.client.get("/api/planes-estudio/p1").json()["materias"]])
        self.assertEqual(self.client.get("/api/planes-estudio/carreras/career/pendientes").json()["materias"],[])
    def test_unknown_chair_invalid_year_and_new_plan_subject(self):
        for changes in ({"catedra_id":999},{"anio":0},{"cuatrimestre":True}):
            self.assertEqual(self.edit(operation="subject",plan_id="p1",subject_id="s1",revision=0,changes=changes).status_code,422)
        r=self.edit(operation="new_plan",career_id="career",revision=0)
        self.assertEqual(r.status_code,200,r.text)
        catalog=self.client.get("/api/planes-estudio").json()
        new=next(p for p in catalog["careers"][0]["planes"] if p["id"] not in ("p1","p2"))
        self.assertEqual(self.edit(operation="new_subject",plan_id=new["id"],revision=1,changes={"nombre":"Nueva materia"}).status_code,200)
    def test_offer_is_explicit_and_does_not_filter_master_plan(self):
        before=self.client.get("/api/planificacion/1/planes/p1").json()
        self.assertFalse(any(s["ofertada"] for s in before["materias"]))
        self.assertEqual(self.offer().status_code,200)
        self.assertEqual(len(self.client.get("/api/planes-estudio/p1").json()["materias"]),2)
        self.assertFalse(any(s["ofertada"] for s in self.client.get("/api/planificacion/2/planes/p1").json()["materias"]))
        self.assertEqual(self.offer(revision=0).status_code,409)
        self.assertEqual(self.offer(period=999).status_code,404)
    def test_demand_deduplicates_students_and_shared_chairs(self):
        base.sql("INSERT INTO inscripciones(alumno_id,catedra_id,cuatrimestre_id) VALUES(1,1,1),(1,1,2)")
        self.offer();self.offer(plan="p2",ids=["s3"],revision=1)
        a=self.client.get("/api/planificacion/1/planes/p1").json()
        b=self.client.get("/api/planificacion/1/planes/p2").json()
        self.assertEqual(a["materias"][0]["inscriptos"],101)
        self.assertEqual(b["materias"][0]["inscriptos"],101)
        self.assertEqual(a["alumnos_distintos"],101)
        self.assertEqual(self.client.get("/api/planificacion/2/planes/p1").json()["materias"][0]["inscriptos"],1)
    def test_suggestions_use_full_interval_eligibility_and_other_period_is_ignored(self):
        self.offer()
        base.sql("INSERT INTO asignaciones(catedra_id,cuatrimestre_id,docente_id,dia,hora_inicio,hora_fin,modalidad,sede_id) VALUES(2,2,1,'Lunes','09:00','11:00','presencial',1)")
        url="/api/planificacion/1/planes/p1/materias/s1/sugerencias?sede_id=1"
        r=self.client.get(url);self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(r.json()["candidatos"])
        base.sql("DELETE FROM docente_disponibilidad WHERE hora='09:30'")
        candidates=self.client.get(url).json()["candidatos"]
        self.assertFalse(any(c["hora_inicio"]=="09:00" for c in candidates))
        base.sql("UPDATE docentes SET catedras_referencia='c.2' WHERE id=1")
        self.assertEqual(self.client.get(url).json()["candidatos"],[])
    def test_assignment_revalidates_and_is_shared_by_plans(self):
        self.offer();self.offer(plan="p2",ids=["s3"],revision=1)
        response=self.assignment();self.assertEqual(response.status_code,200,response.text)
        shared=self.client.get("/api/planificacion/1/planes/p2").json()["materias"][0]["asignaciones"]
        self.assertEqual(shared[0]["id"],response.json()["id"])
        self.assertIn(self.assignment().status_code,(409,422))
        self.assertEqual(base.sql("SELECT count(*) FROM asignaciones")[0][0],1)
    def test_assignment_rejects_stale_suggestion_and_missing_demand(self):
        self.offer()
        base.sql("INSERT INTO asignaciones(catedra_id,cuatrimestre_id,docente_id,dia,hora_inicio,hora_fin,modalidad) VALUES(2,1,1,'Lunes','10:00','11:00','presencial')")
        self.assertEqual(self.assignment().status_code,422)
        base.sql("DELETE FROM asignaciones")
        base.sql("DELETE FROM inscripciones")
        self.assertEqual(self.assignment().status_code,422)
    def test_hours_derive_only_from_selected_period_and_scheduled_classes(self):
        base.sql("UPDATE docentes SET horas_asignadas=999 WHERE id=1")
        base.sql("INSERT INTO asignaciones(catedra_id,cuatrimestre_id,docente_id,dia,hora_inicio,hora_fin,modalidad) VALUES(1,1,1,'Lunes','09:00','10:30','presencial'),(2,1,1,NULL,NULL,NULL,'presencial'),(1,2,1,'Martes','09:00','12:00','presencial')")
        data=self.client.get("/api/docentes/carga-horaria?cuatrimestre_id=1").json()
        self.assertEqual(data["docentes"][0]["horas"],1.5)
        self.assertEqual(data["docentes"][0]["clases_pendientes"],1)
    def test_assignment_rejects_changed_catalog_and_turn(self):
        self.offer()
        self.assertEqual(self.assignment(catalog_revision=99).status_code,409)
        self.assertEqual(self.assignment(modalidad="virtual_tn").status_code,422)
        self.assertEqual(base.sql("SELECT count(*) FROM asignaciones")[0][0],0)

    def test_invalid_clock_is_rejected(self):
        self.assertIsNone(minutes("25:00"));self.assertIsNone(minutes("09:99"))
        self.offer();self.assertEqual(self.assignment(hora_fin="08:00").status_code,422)

if __name__=="__main__": unittest.main()
