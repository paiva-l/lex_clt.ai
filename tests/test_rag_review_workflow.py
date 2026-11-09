import tempfile
import unittest
from pathlib import Path

from src.rag.workflow_07 import (extract_field, review_status, execute_corrections,
    write_json, text_hash, append_answer_cells, read_json, persist_reviews)


class ReviewWorkflowTests(unittest.TestCase):
    def test_decisions_do_not_promote_pending(self):
        self.assertEqual(review_status('Aprovada por Laisa.'), 'aprovada_por_revisor')
        self.assertEqual(review_status('Reprovada por Laisa.'), 'reprovada')
        self.assertEqual(review_status('pendente'), 'pendente_revisao')

    def test_multiline_reference_does_not_include_action(self):
        text = '**Resposta de referência para correção**\n\nA [Fonte 3]\n\nB\n\n**Ação:** corrigir'
        self.assertEqual(extract_field(text, 'Resposta de referência para correção'), 'A [Fonte 3]\n\nB')

    def test_failed_correction_is_not_automatically_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root/'reports/legislacao/integracao_rag/respostas_rag_dev.json',
                [{'query_id':'q', 'pergunta':'Pergunta', 'resposta':'Original', 'sources':[]}])
            calls = []
            def generate(question, sources):
                calls.append(question)
                raise RuntimeError('Falha de geração de teste')
            namespace = {'prepare_prompt':lambda q,s:None, 'generate_answer':generate,
                'inspect_citations':lambda a,s:{}, 'SYSTEM_PROMPT_LEGAL':'Regras',
                'GENERATION_OPTIONS':{}, 'MODEL_DIGEST':'digest'}
            review = {'query_id':'q','status_revisao':'reprovada','motivo':'Erro',
                'acao':'Corrigir', 'resposta_referencia_revisada':'Referência',
                'celula_sha256':'snapshot', 'resposta_original_sha256':text_hash('Original')}
            first = execute_corrections(root,[review],namespace)
            second = execute_corrections(root,[review],namespace)
            self.assertEqual(len(calls),1)
            self.assertEqual(first[0]['status_execucao'],'falha')
            self.assertTrue(second[0]['tentativa_reutilizada'])
            self.assertEqual(second[0]['status_revisao'],'pendente_revisao')

    def test_new_render_preserves_manual_review_and_versions_changed_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'notebooks/07_integracao_rag_legislacao.ipynb'
            write_json(path, {'cells':[{'id':'original','source':['Preservar']} ]})
            result = {'query_id':'q','pergunta':'Pergunta','resposta':'Resposta um',
                'status_execucao':'concluida','sources':[]}
            append_answer_cells(root,[result],[])
            nb = read_json(path)
            nb['cells'][-1]['source'].append('\nRevisado manualmente.')
            write_json(path,nb)
            append_answer_cells(root,[result],[])
            same = read_json(path)
            self.assertEqual(same,nb)
            append_answer_cells(root,[dict(result,resposta='Resposta dois')],[])
            changed = read_json(path)
            self.assertEqual(changed['cells'][:2],nb['cells'])
            self.assertEqual(len(changed['cells']),3)

    def test_approval_cannot_be_transferred_to_changed_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root/'reports/legislacao/integracao_rag/respostas_rag_dev.json',
                [{'query_id':'q_dev_test','resposta':'Nova resposta sem revisão'}])
            write_json(root/'notebooks/07_integracao_rag_legislacao.ipynb', {'cells':[
                {'id':'visualizacao_respostas_q_dev_test', 'source':[
                    '**Revisão jurídica:** aprovada por Revisora.\n\n**Resposta gerada**\n\nResposta antiga.']} ]})
            with self.assertRaisesRegex(ValueError,'não transferir sua revisão'):
                persist_reviews(root)


if __name__ == '__main__':
    unittest.main()
