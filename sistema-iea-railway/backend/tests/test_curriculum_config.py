"""Catalog configuration tests using synthetic data, without the private IEA file."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import curriculum as c


class CatalogConfigurationTests(unittest.TestCase):
    def test_missing_optional_private_catalog_is_an_empty_catalog(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(c, 'ROOT', Path(directory)), patch.dict(os.environ, {}, clear=True):
            for ident in ('iea', 'institucion-ficticia'):
                result = c.load_catalog(ident)
                self.assertEqual(result['institution_id'], ident)
                self.assertEqual(result['careers'], [])
                self.assertEqual(result['articulations'], [])

    def test_explicit_invalid_catalog_never_silently_becomes_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'missing.json'
            with patch.dict(os.environ, {'CURRICULUM_CATALOG_PATH': str(path)}):
                with self.assertRaises(FileNotFoundError):
                    c.load_catalog('iea')

    def test_private_file_loads_only_for_the_matching_institution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'catalog.json'
            data = {'schema_version': 1, 'institution_id': 'ficticia', 'source': None,
                    'careers': [{'id': 'c-1', 'nombre': 'Carrera de prueba', 'planes': []}],
                    'articulations': []}
            path.write_text(json.dumps(data))
            with patch.dict(os.environ, {'CURRICULUM_CATALOG_PATH': str(path)}):
                self.assertEqual(c.load_catalog('ficticia'), data)
                with self.assertRaises(ValueError):
                    c.load_catalog('iea')
