"""Compatibility of existing access when bootstrap secrets are deployment settings."""
import os
import secrets
import unittest
from unittest.mock import patch
import test_institution_api as base
from app import main as m


class BootstrapAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.InstitutionApiTests.setUpClass()
        cls.client = base.InstitutionApiTests.client

    def setUp(self):
        base.InstitutionApiTests.setUp(self)
        self.editor = secrets.token_urlsafe(24)
        self.reader = secrets.token_urlsafe(24)
        self.settings = patch.dict(os.environ, {
            'BOOTSTRAP_EDITOR_PASSWORD': self.editor,
            'BOOTSTRAP_CONSULTA_PASSWORD': self.reader,
        })
        self.settings.start()
        self.addCleanup(self.settings.stop)

    def login(self, value):
        return self.client.post('/api/login', json={'clave': value})

    def test_bootstrap_settings_keep_both_existing_roles(self):
        self.assertEqual(self.login(self.editor).json()['rol'], 'editor')
        self.assertEqual(self.login(self.reader).json()['rol'], 'consulta')
        self.assertEqual(self.login('').status_code, 401)
        self.assertEqual(self.login(secrets.token_urlsafe(24)).status_code, 401)

    def test_saved_passwords_take_precedence_over_bootstrap_settings(self):
        saved = secrets.token_urlsafe(24)
        base.sql('INSERT INTO configuracion(clave,valor) VALUES (:k,:v)',
                 {'k': 'clave_editor', 'v': m._hash_clave(saved)})
        self.assertEqual(self.login(saved).json()['rol'], 'editor')
        self.assertEqual(self.login(self.editor).status_code, 401)
        with patch.dict(os.environ, {'BOOTSTRAP_EDITOR_PASSWORD': '', 'BOOTSTRAP_CONSULTA_PASSWORD': ''}):
            self.assertEqual(self.login(saved).json()['rol'], 'editor')
            self.assertEqual(self.login(self.reader).status_code, 401)

    def test_changing_password_preserves_the_other_configured_role(self):
        changed = secrets.token_urlsafe(24)
        response = self.client.post('/api/auth/cambiar-clave', json={
            'clave_actual': self.editor, 'clave_nueva': changed, 'cual': 'editor',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.login(changed).json()['rol'], 'editor')
        self.assertEqual(self.login(self.editor).status_code, 401)
        self.assertEqual(self.login(self.reader).json()['rol'], 'consulta')
        self.assertEqual(base.sql("SELECT valor FROM configuracion WHERE clave='clave_consulta'")[0][0],
                         m._hash_clave(self.reader))

    def test_missing_reader_setting_never_creates_a_hash_for_an_empty_password(self):
        with patch.dict(os.environ, {'BOOTSTRAP_CONSULTA_PASSWORD': ''}):
            response = self.client.post('/api/auth/cambiar-clave', json={
                'clave_actual': self.editor, 'clave_nueva': secrets.token_urlsafe(24), 'cual': 'editor',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(base.sql("SELECT valor FROM configuracion WHERE clave='clave_consulta'"), [])
            self.assertEqual(self.login(self.reader).status_code, 401)


if __name__ == '__main__':
    unittest.main(verbosity=2)
