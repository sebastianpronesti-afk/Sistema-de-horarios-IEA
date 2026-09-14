"""Catalog configuration tests using synthetic data, without the private IEA file."""
import json
import base64
import gzip
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import curriculum as c
from app import curriculum_bundle as bundle


class CatalogConfigurationTests(unittest.TestCase):
    def bundle_settings(self, data):
        raw=json.dumps(data).encode()
        encoded=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
        parts=[encoded[i:i+32] for i in range(0,len(encoded),32)]
        return {bundle.PREFIX+'PARTS':str(len(parts)),bundle.PREFIX+'SHA256':hashlib.sha256(raw).hexdigest(),
                **{f'{bundle.PREFIX}PART_{i:02d}':part for i,part in enumerate(parts,1)}}

    def test_private_variables_preserve_data_without_writing_files(self):
        data={'schema_version':1,'institution_id':'ficticia','source':None,'careers':[],'articulations':[]}
        with tempfile.TemporaryDirectory() as directory,patch.object(c,'ROOT',Path(directory)),patch.dict(os.environ,self.bundle_settings(data),clear=True):
            self.assertEqual(c.load_catalog('ficticia'),data)
            self.assertEqual(list(Path(directory).iterdir()),[])
            with self.assertRaises(ValueError):c.load_catalog('iea')

    def test_incomplete_or_corrupt_private_variables_fail_explicitly(self):
        data={'schema_version':1,'institution_id':'iea','source':None,'careers':[],'articulations':[]}
        settings=self.bundle_settings(data)
        for key,value in ((bundle.PREFIX+'PART_01',''),(bundle.PREFIX+'SHA256','0'*64),
                          (bundle.PREFIX+'PARTS','65'),(bundle.PREFIX+'PART_01','!invalid!')):
            with self.subTest(key=key),patch.dict(os.environ,{**settings,key:value},clear=True):
                with self.assertRaises(ValueError):c.load_catalog('iea')

    def test_decompressed_catalog_has_a_size_limit(self):
        settings=self.bundle_settings({'oversized':'x'*500})
        bundle._decode.cache_clear()
        with patch.dict(os.environ,settings,clear=True),patch.object(bundle,'MAX_BYTES',10):
            with self.assertRaises(ValueError):bundle.read_bundle()

    def test_explicit_private_file_takes_precedence_over_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'catalog.json'
            data={'schema_version':1,'institution_id':'iea','source':None,'careers':[],'articulations':[]}
            path.write_text(json.dumps(data))
            with patch.dict(os.environ,{'CURRICULUM_CATALOG_PATH':str(path),bundle.PREFIX+'PARTS':'bad'},clear=True):
                self.assertEqual(c.load_catalog('iea'),data)

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
