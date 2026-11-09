import unittest
from src.storage.parent_documents import expand_parent_documents, format_parent_context


class ParentDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.parents = {name: {'chunk_id': 'pai-'+name, 'artigo_id': name,
                              'estrategia': 'A_artigo', 'caminho_relativo': 'lei.md',
                              'sha256_fonte': 'hash', 'corpo_chunk': text, 'conteudo_chunk': text}
                        for name, text in [('a', 'CAPUT\nPARAGRAFO'), ('b', 'OUTRO ARTIGO')]}
        self.children = {
            'a1': self.child('a', 0, 6), 'a2': self.child('a', 6, 15),
            'b1': self.child('b', 0, 12)}

    def child(self, name, start, end):
        parent = self.parents[name]
        return {'artigo_id': name, 'estrategia': 'D_paragrafo_completo',
                'caminho_relativo': 'lei.md', 'sha256_fonte': 'hash',
                'inicio_no_artigo': start, 'fim_no_artigo': end,
                'corpo_chunk': parent['corpo_chunk'][start:end]}

    def test_deduplication_keeps_full_article_and_best_child_order(self):
        sources, _ = expand_parent_documents(
            [{'chunk_id': 'a2'}, {'chunk_id': 'b1'}, {'chunk_id': 'a1'}], self.children, self.parents)
        self.assertEqual([item['artigo_id'] for item in sources], ['a', 'b'])
        self.assertEqual(sources[0]['corpo_chunk'], 'CAPUT\nPARAGRAFO')
        self.assertEqual(len(sources[0]['retrieval_matches']), 2)

    def test_parent_from_other_source_is_rejected(self):
        self.children['a2']['sha256_fonte'] = 'outro-hash'
        with self.assertRaises(ValueError):
            expand_parent_documents([{'chunk_id': 'a2'}], self.children, self.parents)

    def test_budget_never_truncates_article(self):
        full, _ = expand_parent_documents([{'chunk_id': 'a1'}], self.children, self.parents)
        exact_length = len(format_parent_context(full))
        sources, omitted = expand_parent_documents([{'chunk_id': 'a1'}], self.children, self.parents,
            token_budget=exact_length-1, count_tokens=len)
        self.assertEqual(sources, [])
        self.assertEqual(omitted[0]['reason'], 'orcamento_contexto_artigo_integral')

    def test_no_budget_is_imposed_without_configuration(self):
        sources, _ = expand_parent_documents([{'chunk_id': 'a2'}], self.children, self.parents)
        self.assertEqual(len(sources), 1)

    def test_unknown_synthetic_document_cannot_become_source(self):
        with self.assertRaises(ValueError):
            expand_parent_documents([{'chunk_id': 'hyde-sintetico'}], self.children, self.parents)


if __name__ == '__main__':
    unittest.main()
