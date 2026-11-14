import tempfile
import unittest
from pathlib import Path

from src.rag.workflow_07 import write_json, read_json, text_hash
from src.rag.review_persistence_07 import (parse_generated_cell,
    persist_generated_reviews, matching_review)


def cell_text(body, decision='Aprovada.'):
    return ('**Revisão jurídica desta nova versão:** '+decision+
        '\n\n**Nova resposta do modelo:** '+body+
        '\n\n**Fontes efetivamente entregues nesta execução**\n\nFontes')


class GeneratedReviewTests(unittest.TestCase):
    def test_legacy_scope_refusal_keeps_explicit_approval_for_same_question(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=root/'reports/legislacao/integracao_rag'
            refusal='Essa não é uma pergunta ligada ao Direito do Trabalho.'
            current={'query_id':'v1','pergunta':'Pergunta sobre divórcio','resposta':refusal,
                'status_execucao':'concluida','sources':[{'source_id':'Fonte 1'}]}
            write_json(report/'correcoes/respostas_corrigidas_dev.json',[])
            write_json(report/'variantes/respostas_variantes_rag.json',[current])
            text='**Pergunta:** Pergunta sobre divórcio\n\n'+cell_text(refusal)
            write_json(root/'notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb',{'cells':[
                {'id':'novas_respostas_07_variante_v1','source':[text]}]})
            legacy=parse_generated_cell(text,current,'Laisa')
            legacy.update(tipo='variante',query_id='v1',contexto_fontes_sha256=None)
            write_json(report/'revisoes/novas/historico/legado.json',legacy)
            current_reviews=persist_generated_reviews(root,'Laisa')
            self.assertEqual(current_reviews[0]['status_revisao'],'aprovada_por_revisor')

    def test_reexecution_keeps_old_review_without_approving_new_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=root/'reports/legislacao/integracao_rag'
            write_json(report/'correcoes/respostas_corrigidas_dev.json',[])
            original={'query_id':'v1','pergunta':'Pergunta','resposta':'Texto revisado.',
                'status_execucao':'concluida','sources':[]}
            write_json(report/'variantes/respostas_variantes_rag.json',[original])
            write_json(root/'notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb',{'cells':[
                {'id':'novas_respostas_07_variante_v1','source':[cell_text('Texto revisado.')]}]})
            persist_generated_reviews(root,'Laisa')
            new=dict(original,resposta='Texto de outra execução.')
            write_json(report/'variantes/respostas_variantes_rag.json',[new])
            current=persist_generated_reviews(root,'Laisa')
            self.assertEqual(current[0]['status_revisao'],'sem_anotacao_local')
            preserved=read_json(report/'revisoes_versoes_revisadas.json')
            self.assertEqual(preserved[0]['resposta_modelo_original'],'Texto revisado.')
            self.assertEqual(preserved[0]['status_revisao'],'aprovada_por_revisor')
            self.assertNotEqual(preserved[0]['resposta_modelo_sha256'],current[0]['resposta_modelo_sha256'])

    def test_same_words_with_different_sources_do_not_inherit_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=root/'reports/legislacao/integracao_rag'
            write_json(report/'correcoes/respostas_corrigidas_dev.json',[])
            original={'query_id':'v1','pergunta':'Pergunta','resposta':'Texto revisado.',
                'status_execucao':'concluida','sources':[{'source_id':'Fonte 1','conteudo_chunk':'Fonte antiga'}]}
            write_json(report/'variantes/respostas_variantes_rag.json',[original])
            write_json(root/'notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb',{'cells':[
                {'id':'novas_respostas_07_variante_v1','source':[cell_text('Texto revisado.')]}]})
            persist_generated_reviews(root,'Laisa')
            write_json(report/'variantes/respostas_variantes_rag.json',[dict(original,sources=[{'source_id':'Fonte 1','conteudo_chunk':'Outra fonte'}])])
            current=persist_generated_reviews(root,'Laisa')
            self.assertEqual(current[0]['status_revisao'],'sem_anotacao_local')

    def test_unchanged_model_answer_approval_is_bound_to_its_hash(self):
        result=parse_generated_cell(cell_text('Resposta original.'),{'resposta':'Resposta original.'},'Laisa')
        self.assertEqual(result['status_revisao'],'aprovada_por_revisor')
        self.assertEqual(result['status_revisao_modelo_original'],'aprovada_por_revisor')
        self.assertEqual(result['resposta_modelo_sha256'],text_hash('Resposta original.'))

    def test_added_reference_is_not_attributed_to_model(self):
        result=parse_generated_cell(cell_text('Minha referência.\n\nResposta original.','Reprovada.'),
            {'resposta':'Resposta original.'},'Laisa')
        self.assertEqual(result['texto_acrescentado_antes_da_resposta'],'Minha referência.')
        self.assertEqual(result['resposta_modelo_original'],'Resposta original.')
        self.assertEqual(result['status_revisao'],'reprovada')
        self.assertEqual(result['status_revisao_modelo_original'],'nao_inferido_de_celula_editada')

    def test_complete_replacement_keeps_original_separately(self):
        result=parse_generated_cell(cell_text('Texto substituído.'),{'resposta':'Resposta original.'})
        self.assertTrue(result['celula_tem_edicoes_na_resposta'])
        self.assertFalse(result['resposta_modelo_original_presente'])
        self.assertEqual(result['texto_substituido_ou_editado'],'Texto substituído.')

    def test_explicit_rejection_targets_original_despite_added_reference(self):
        text='**Revisão da saída original do modelo:** Reprovada por Laisa.\n\n'+cell_text(
            'Minha referência.\n\nResposta original.','Reprovada.')
        result=parse_generated_cell(text,{'resposta':'Resposta original.'},'Laisa')
        self.assertTrue(result['celula_tem_edicoes_na_resposta'])
        self.assertEqual(result['status_revisao_modelo_original'],'reprovada')
        self.assertEqual(result['escopo_status'],'decisao_explicita_sobre_saida_original_modelo')

    def test_persist_preserves_notebook_raw_outputs_and_failed_missing_cell(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=root/'reports/legislacao/integracao_rag'
            raw=[{'query_id':'v1','pergunta':'Pergunta','status_execucao':'concluida',
                'resposta':'Resposta original.','sources':[]},
                {'query_id':'v2','pergunta':'Outra','status_execucao':'falha','erro':'limite','sources':[]}]
            write_json(report/'variantes/respostas_variantes_rag.json',raw)
            write_json(report/'correcoes/respostas_corrigidas_dev.json',[])
            notebook=root/'notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb'
            write_json(notebook,{'cells':[{'id':'novas_respostas_07_variante_v1',
                'source':[cell_text('Resposta original.')]}]})
            old_notebook=notebook.read_bytes()
            old_raw=(report/'variantes/respostas_variantes_rag.json').read_bytes()
            reviews=persist_generated_reviews(root,'Laisa')
            self.assertEqual(notebook.read_bytes(),old_notebook)
            self.assertEqual((report/'variantes/respostas_variantes_rag.json').read_bytes(),old_raw)
            self.assertEqual(reviews[1]['status_revisao'],'falha_tecnica_sem_resposta')
            self.assertIsNone(matching_review(root,'variante',dict(raw[0],resposta='Outra versão.')))
            self.assertIsNone(matching_review(root,'variante',dict(raw[0],sources=[{'source_id':'Fonte 1','conteudo_chunk':'Outra fonte'}])))
            self.assertIsNone(matching_review(root,'variante',dict(raw[0],pergunta='Outra pergunta')))
            self.assertEqual(matching_review(root,'variante',raw[0])['status_revisao'],'aprovada_por_revisor')


if __name__=='__main__':
    unittest.main()
