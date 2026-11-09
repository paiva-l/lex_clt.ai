import unittest
from src.rag.evaluation_08 import retrieval_metrics, load_test, validate_frozen, evaluate, sha
from pathlib import Path


class EvaluationMetricsTests(unittest.TestCase):
    def test_exact_device_and_deduplication(self):
        refs = [{'norma': 'clt', 'posicao_inicio': '10', 'trecho_evidencia_selecionado': 'regra'}]
        wrong = {'caminho_relativo': 'outra_lei', 'posicao_inicio': 10, 'conteudo_chunk': 'regra'}
        correct = {'caminho_relativo': 'clt', 'posicao_inicio': 10, 'conteudo_chunk': 'a regra completa'}
        metrics = retrieval_metrics([wrong, wrong, correct], refs)
        self.assertEqual(metrics['recall'], 1)
        self.assertEqual(metrics['mrr'], .5)
        self.assertAlmostEqual(metrics['ndcg'], 1 / __import__('math').log2(3))
        self.assertEqual(metrics['cobertura_evidencias'], 1)

    def test_negative_does_not_create_fake_hit(self):
        self.assertTrue(all(value is None for value in retrieval_metrics([], []).values()))

    def test_empty_retrieval_is_zero_for_positive(self):
        refs = [{'norma': 'clt', 'posicao_inicio': 10, 'trecho_evidencia_selecionado': 'regra'}]
        self.assertTrue(all(value == 0 for value in retrieval_metrics([], refs).values()))

    def test_literal_evidence_must_be_in_matching_device(self):
        refs = [{'norma': 'clt', 'posicao_inicio': 10, 'trecho_evidencia_selecionado': 'regra'}]
        sources = [{'caminho_relativo': 'clt', 'posicao_inicio': 10, 'conteudo_chunk': 'outro texto'},
            {'caminho_relativo': 'outra_lei', 'posicao_inicio': 10, 'conteudo_chunk': 'regra'}]
        self.assertEqual(retrieval_metrics(sources, refs)['cobertura_evidencias'], 0)

    def test_parent_source_original_position(self):
        refs = [{'norma': 'clt', 'posicao_inicio': '10', 'trecho_evidencia_selecionado': 'regra'}]
        sources = [{'caminho_relativo': 'clt', 'posicao_inicio_original': 10, 'conteudo_chunk': 'regra'}]
        self.assertEqual(retrieval_metrics(sources, refs)['recall'], 1)

    def test_evaluation_resolves_null_position_only_with_matching_source(self):
        import tempfile
        import json
        import pandas as pd
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / 'data/processed/legislacao/legislacao_artigos_completos.json'
            base.parent.mkdir(parents=True)
            base.write_text(json.dumps([{'artigo_id': 'a', 'caminho_relativo': 'clt',
                'sha256_fonte': 'fonte', 'posicao_inicio': 10,
                'texto_original': 'regra completa', 'texto_artigo_completo': 'regra completa'}]), encoding='utf-8')
            questions = pd.DataFrame([{'query_id': 'q', 'pergunta': 'pergunta',
                'rotulo_resposta': 'respondível', 'base_sha256_anotacao': sha(base.read_bytes())}])
            refs = pd.DataFrame([{'query_id': 'q', 'norma': 'clt', 'posicao_inicio': 10,
                'trecho_evidencia_selecionado': 'regra'}])
            source = {'artigo_id': 'a', 'caminho_relativo': 'clt', 'sha256_fonte': 'fonte',
                'posicao_inicio_original': None, 'corpo_chunk': 'regra completa', 'conteudo_chunk': 'regra completa'}
            results = [{'query_id': 'q', 'pergunta': 'pergunta', 'configuracao_sha256': 'teste',
                'status_execucao': 'concluida', 'sources': [source]}]
            _, summary = evaluate(root, {'configuracao_sha256': 'teste'}, questions, refs, results)
            self.assertEqual(summary['recall'], 1)
            self.assertIsNone(source['posicao_inicio_original'])
            source['sha256_fonte'] = 'fonte-divergente'
            with self.assertRaisesRegex(ValueError, 'não corresponde'):
                evaluate(root, {'configuracao_sha256': 'teste'}, questions, refs, results)

    def test_frozen_project_and_test_identity(self):
        root = Path(__file__).resolve().parents[1]
        validate_frozen(root)
        questions, references, identity = load_test(root)
        self.assertEqual(len(questions), 9)
        self.assertFalse(references.empty)
        self.assertEqual(identity, '7d094eddf4d34e7e3ce0cc39045b425630170b501b20a8a29ed236500b5e8b74')


if __name__ == '__main__':
    unittest.main()
