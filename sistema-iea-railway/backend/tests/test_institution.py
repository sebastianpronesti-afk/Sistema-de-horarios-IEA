import json
from pathlib import Path
import tempfile
import unittest

from app.institution import load_institution

PROFILES = Path(__file__).resolve().parents[1] / 'app' / 'profiles'


class InstitutionTests(unittest.TestCase):
    def test_iea_boundaries_preserve_staffing(self):
        profile = load_institution(PROFILES / 'iea.json')
        for total, expected in [(0, 0), (1, 0), (9, 0), (10, 1), (100, 1), (101, 2), (200, 2), (201, 3)]:
            with self.subTest(total=total):
                self.assertEqual(profile.docentes_sugeridos(total), expected)

    def test_second_profile_has_independent_rules(self):
        profile = load_institution(PROFILES / 'institucion-ejemplo.json')
        for total, expected in [(0, 0), (14, 0), (15, 1), (40, 1), (41, 2), (81, 3)]:
            with self.subTest(total=total):
                self.assertEqual(profile.docentes_sugeridos(total), expected)
        self.assertEqual(profile.duracion_clase_minutos, 60)
        self.assertNotIn('ADMINISTRACIÓN DE EMPRESAS', profile.alias_carreras)

    def test_invalid_profile_never_falls_back_to_iea(self):
        original = json.loads((PROFILES / 'iea.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            for field, value in [('alumnos_por_docente', 0), ('minimo_inscriptos_apertura', True),
                                 ('duracion_clase_minutos', 1441), ('corte_turno_minutos', 1440), ('schema_version', 2),
                                 ('alias_carreras', {'': 'Carrera'}), ('campo_inexistente', 1)]:
                with self.subTest(field=field):
                    path.write_text(json.dumps({**original, field: value}))
                    with self.assertRaises(ValueError):
                        load_institution(path)
            path.write_text('{')
            with self.assertRaises(ValueError):
                load_institution(path)

    def test_turn_boundary_is_configurable_and_has_a_legacy_default(self):
        original = json.loads((PROFILES / 'iea.json').read_text())
        self.assertEqual(load_institution(PROFILES / 'iea.json').corte_turno_minutos, 900)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            path.write_text(json.dumps({**original, 'corte_turno_minutos': 840}))
            self.assertEqual(load_institution(path).corte_turno_minutos, 840)

    def test_missing_explicit_profile_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            load_institution(PROFILES / 'no-existe.json')

    def test_public_profile_has_only_display_and_rule_fields(self):
        public = load_institution(PROFILES / 'iea.json').public_config()
        self.assertEqual(public['titulo'], 'IEA Horarios')
        self.assertNotIn('alias_carreras', public)
        self.assertEqual(set(public), {'schema_version', 'id', 'nombre', 'titulo',
                         'minimo_inscriptos_apertura', 'alumnos_por_docente', 'duracion_clase_minutos', 'corte_turno_minutos'})


if __name__ == '__main__':
    unittest.main()
