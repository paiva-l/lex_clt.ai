import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from src.storage.pgvector_store import load_database_url, vector_hash, verify_stored_row


class CorrespondenceTests(unittest.TestCase):
    def setUp(self):
        self.vector = np.zeros(1024, dtype=np.float32)
        self.vector[0] = 1
        self.chunk = {'chunk_id': 'chunk-a', 'artigo_id': 'artigo-a',
                      'caminho_relativo': 'norma.md', 'conteudo_chunk': 'Texto original',
                      'corpo_chunk': 'Corpo'}
        self.identity = {'text_sha256': hashlib.sha256(b'Texto original').hexdigest(),
                         'vector_sha256': vector_hash(self.vector)}
        metadata = {key: value for key, value in self.chunk.items()
                    if key not in {'conteudo_chunk', 'corpo_chunk'}}
        self.stored = [0, 'chunk-a', 'artigo-a', 'norma.md', 'Texto original',
                       self.identity['text_sha256'], self.identity['vector_sha256'], metadata, self.vector.copy()]

    def check(self):
        verify_stored_row(self.stored, 0, [self.chunk], [self.identity])

    def test_valid_round_trip(self):
        self.check()

    def test_pgvector_wrapper_round_trip(self):
        from pgvector import Vector
        self.stored[-1] = Vector(self.vector)
        self.check()

    def test_changed_vector_rejected_even_with_original_hash_column(self):
        self.stored[-1] = np.roll(self.vector, 1)
        with self.assertRaises(ValueError):
            self.check()

    def test_other_chunk_rejected(self):
        self.stored[1] = 'chunk-b'
        with self.assertRaises(ValueError):
            self.check()

    def test_reordered_rows_rejected(self):
        with self.assertRaises(ValueError):
            verify_stored_row(self.stored, 1, [self.chunk], [self.identity])

    def test_changed_source_metadata_rejected(self):
        self.stored[-2]['caminho_relativo'] = 'outra-norma.md'
        with self.assertRaises(ValueError):
            self.check()

    def test_connection_reads_local_file_without_execution(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            file = Path(directory) / 'test.env'
            file.write_text('DATABASE_URL="postgresql://user:example@host/database"\n', encoding='utf-8')
            self.assertEqual(load_database_url(file), 'postgresql://user:example@host/database')

    def test_empty_connection_is_not_an_import(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            file = Path(directory) / 'test.env'
            file.write_text('DATABASE_URL=\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_database_url(file)


if __name__ == '__main__':
    unittest.main()
