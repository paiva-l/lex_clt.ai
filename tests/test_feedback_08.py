import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.rag.evaluation_08 import write, sha, output_folder, read
from src.rag.feedback_08 import export_feedback
from src.rag.review_08 import parse_review


class FeedbackTests(unittest.TestCase):
    def test_review_marker_and_multiline_final_answer(self):
        parsed = parse_review('<!-- INICIO_AVALIACAO_08 -->\n**Decisão:** APROVADO.\n\n'
            '**Resposta corrigida pela revisora:** Minha resposta.\nSegunda linha.\n\n**Revisor(a):** Laisa')
        self.assertEqual(parsed['decisao'], 'aprovada')
        self.assertEqual(parsed['resposta_corrigida_revisora'], 'Minha resposta.\nSegunda linha.')

    def test_feedback_preserves_decision_raw_answer_and_human_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frozen = {'configuracao_sha256': 'teste'}
            raw_answer = 'Resposta original.'
            final = 'Minhas observações.\nMinha resposta final.'
            rows = [{'query_id': 'q', 'resposta_sha256': sha(raw_answer.encode()),
                'decisao': 'aprovada', 'revisor': 'Laisa', 'resposta_corrigida_revisora': final}]
            result = {'query_id': 'q', 'status_execucao': 'concluida', 'resposta': raw_answer,
                'resposta_sha256': sha(raw_answer.encode()), 'pergunta': 'Pergunta?', 'sources': []}
            path = output_folder(root, frozen) / 'respostas_teste.json'
            write(path, [result])
            original_bytes = path.read_bytes()
            with patch('src.rag.feedback_08.validate_frozen', return_value=frozen), patch(
                    'src.rag.feedback_08.save_notebook_reviews', return_value=rows):
                records, summary = export_feedback(root)
                self.assertEqual(records[0]['texto_final_informado_pela_revisora'], final)
                self.assertEqual(records[0]['resposta_real_modelo'], raw_answer)
                self.assertEqual(records[0]['decisao_sobre_resposta_original'], 'aprovada')
                self.assertFalse(records[0]['elegivel_treinamento_automatico'])
                self.assertEqual(summary['revisoes_registradas'], 1)
                self.assertEqual(path.read_bytes(), original_bytes)
                self.assertEqual(export_feedback(root)[1]['feedback_sha256'], summary['feedback_sha256'])
                rows[0]['resposta_sha256'] = 'outra-resposta'
                with self.assertRaises(ValueError):
                    export_feedback(root)
