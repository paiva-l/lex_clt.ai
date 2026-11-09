import unittest

from src.rag.presentation_07 import inspect_answer, split_sentences


class PresentationTests(unittest.TestCase):
    def test_citation_on_next_line_attaches_to_claim(self):
        rows=inspect_answer('A regra consta no art. 483 da CLT.\n[Fonte 3]',[{'source_id':'Fonte 3'}])['frases']
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]['sem_citacao'])

    def test_unknown_source_is_flagged(self):
        value=inspect_answer('Uma afirmação [Fonte 9].',[{'source_id':'Fonte 1'}])
        self.assertIn('citacao_de_fonte_inexistente',value['alertas_formais_por_frase'])

    def test_existing_citation_does_not_approve_semantics(self):
        value=inspect_answer('Uma afirmação [Fonte 1].',[{'source_id':'Fonte 1'}])
        self.assertEqual(value['status_formal'],'sem_alertas_detectados')
        self.assertEqual(value['revisao_juridica'],'pendente')
        self.assertEqual(value['frases'][0]['suporte_semantico'],'nao_avaliado')

    def test_scope_refusal_does_not_require_citation(self):
        value=inspect_answer('Essa não é uma pergunta ligada ao Direito do Trabalho.',[])
        self.assertFalse(any(row['sem_citacao'] for row in value['frases']))

    def test_question_is_not_uncited_assertion(self):
        value=inspect_answer('Você precisa informar a data de admissão?',[])
        self.assertTrue(value['frases'][0]['pergunta_ao_usuario'])
        self.assertFalse(value['frases'][0]['sem_citacao'])
        self.assertEqual(value['revisao_juridica'],'pendente')

    def test_abbreviations_and_decimals_preserved(self):
        rows=split_sentences('Art. 483 da CLT: valor de 1.234. Outra frase.')
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[0].startswith('Art. 483'))

    def test_extended_label_is_recognized(self):
        value=inspect_answer('Uma afirmação [Fonte 1 – Art. 59].',[{'source_id':'Fonte 1'}])
        self.assertEqual(value['frases'][0]['fontes_citadas'],['Fonte 1'])

    def test_scope_notice_plus_answer_is_flagged(self):
        value=inspect_answer('Essa não é uma pergunta ligada ao Direito do Trabalho. Contudo, o divórcio...',[])
        self.assertIn('aviso_de_escopo_com_conteudo_adicional_revisar',value['alertas_formais_por_frase'])


if __name__=='__main__':
    unittest.main()
