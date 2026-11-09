"""Consulta livre e inspeção por frase do 07 integrado.

Inspeção lexical não decide suporte semântico, correção jurídica ou aprovação.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from functools import lru_cache

from .workflow_07 import (VariantRetriever, load_generation_namespace, read_json,
                          write_json, text_hash, generate_custom)

CITATION = re.compile(r'\[[^\]]*\bFonte\s*\d+[^\]]*\]', re.I)
ADVICE = re.compile(r'\b(voc[eê]\s+(deve|precisa|tem que)|recomend[oa]|aconselh[oa]|'
                   r'sugiro|procure\s+(um|uma)|entre com|aju[ií]ze|recorra|n[aã]o assine)\b', re.I)
SCOPE_NOTICE = 'Essa não é uma pergunta ligada ao Direito do Trabalho'


def split_sentences(text):
    """Heurística: preserva abreviações e liga citação isolada à frase anterior."""
    pieces = []
    protected = '\uFFF0'
    for raw_line in text.splitlines():
        line = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s+', '', raw_line).strip()
        if not line or line.startswith('```') or re.fullmatch(r'[|:\-\s]+', line):
            continue
        if CITATION.fullmatch(line):
            if pieces:
                pieces[-1] += ' ' + line
            else:
                pieces.append(line)
            continue
        masked = re.sub(r'\b(arts?|Dr|Dra|Sr|Sra)\.', lambda m:m.group(0).replace('.',protected), line, flags=re.I)
        masked = re.sub(r'(?<=\d)\.(?=\d)',protected,masked)
        for part in re.split(r'(?<=[.!?])\s+(?!\[Fonte\b)(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])|(?<=\])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])', masked):
            if part.strip():
                pieces.append(part.replace(protected,'.').strip())
    return pieces


def inspect_answer(text, sources):
    """Registra alertas; mesmo sem alertas, revisão jurídica permanece pendente."""
    valid = {source.get('source_id',f'Fonte {i}') for i,source in enumerate(sources,1)}
    refusal_only = text.strip().strip('.! \n') == SCOPE_NOTICE
    rows = []
    for number, sentence in enumerate(split_sentences(text),1):
        cited = {f'Fonte {int(n)}' for block in CITATION.findall(sentence)
                 for n in re.findall(r'Fonte\s*(\d+)',block,re.I)}
        question = sentence.rstrip(' *_').endswith('?')
        heading = sentence.startswith('#') or (sentence.endswith(':') and not cited)
        citation_only = bool(CITATION.fullmatch(sentence))
        possible_assertion = not (question or heading or citation_only or refusal_only)
        rows.append({'ordem':number, 'texto':sentence, 'fontes_citadas':sorted(cited),
            'fontes_inexistentes':sorted(cited-valid), 'pergunta_ao_usuario':question,
            'titulo_heuristico':heading, 'possivel_afirmacao':possible_assertion,
            'sem_citacao':possible_assertion and not cited,
            'termo_que_exige_revisao':bool(ADVICE.search(sentence)),
            'suporte_semantico':'nao_avaliado'})
    alerts = []
    if not text.strip():
        alerts.append('resposta_vazia')
    if any(row['fontes_inexistentes'] for row in rows):
        alerts.append('citacao_de_fonte_inexistente')
    if any(row['sem_citacao'] for row in rows):
        alerts.append('possivel_afirmacao_sem_citacao')
    if any(row['termo_que_exige_revisao'] for row in rows):
        alerts.append('expressao_que_exige_revisao_contextual')
    if SCOPE_NOTICE.lower() in text.lower() and not refusal_only:
        alerts.append('aviso_de_escopo_com_conteudo_adicional_revisar')
    return {'frases':rows, 'alertas_formais_por_frase':alerts,
        'status_formal':'com_alertas' if alerts else 'sem_alertas_detectados',
        'revisao_juridica':'pendente', 'recusa_fora_escopo_sem_conteudo_adicional':refusal_only,
        'sinal_textual_insuficiencia':bool(re.search(r'insuficien|não (há|tenho|consta)|fora do escopo',text,re.I)),
        'limite':'Heurística lexical; não comprova suporte, ausência de alucinação ou acerto jurídico.'}


@lru_cache(maxsize=2)
def article_positions(root):
    return {row['artigo_id']:(row['posicao_inicio'],row['posicao_fim']) for row in
        read_json(Path(root)/'data/processed/legislacao/legislacao_artigos_completos.json')}


def sources_table(sources, root=None):
    import pandas as pd
    positions=article_positions(str(root)) if root is not None else {}
    return pd.DataFrame([{'fonte':source.get('source_id',f'Fonte {i}'),
        'norma_arquivo':source.get('caminho_relativo'), 'dispositivo':source.get('artigo_ref'),
        'artigo_id':source.get('artigo_id'), 'sha256_fonte':source.get('sha256_fonte'),
        'posicao_inicio_na_fonte':positions.get(source.get('artigo_id'),(None,None))[0],
        'posicao_fim_na_fonte':positions.get(source.get('artigo_id'),(None,None))[1],
        'origem':source.get('source'), 'status_declarado':source.get('status_declarado')}
        for i,source in enumerate(sources,1)])


def child_table(root, ranking, limit=10):
    import pandas as pd
    children = {row['chunk_id']:row for row in read_json(Path(root)/'data/chunks/legislacao/chunks_D_paragrafo_completo.json')}
    rows = []
    for rank, hit in enumerate(ranking[:limit],1):
        child = children[hit['chunk_id']]
        rows.append({'posicao':rank, 'score_reranker':hit['score'],
            'dispositivo':child['artigo_ref'], 'arquivo':child['caminho_relativo'],
            'trecho_exibido':re.sub(r'\s+',' ',child['corpo_chunk'])[:220],
            'chunk_id':hit['chunk_id']})
    return pd.DataFrame(rows)


def show_answer(result, root=None):
    """Mostra texto, fontes e inspeção; aprovação humana é um registro separado."""
    import pandas as pd
    from IPython.display import display, Markdown
    display(Markdown('### Pergunta\n\n'+result['pergunta']))
    if result.get('hyde_text'):
        display(Markdown('**Documento hipotético HyDE — somente consulta, nunca evidência**\n\n'+result['hyde_text']))
    if root is not None and result.get('ranking_d'):
        display(Markdown('### Parágrafos D após RRF e reranking\n\nTrechos abreviados apenas para exibição. Os artigos enviados ao modelo permanecem integrais.'))
        display(child_table(root,result['ranking_d']))
    if result.get('status_execucao') == 'falha':
        display(Markdown('**Falha técnica — não há resposta concluída:** '+result.get('erro','sem detalhe')))
        return
    display(Markdown('### Resposta gerada\n\n'+result['resposta']))
    inspection = inspect_answer(result['resposta'],result.get('sources',[]))
    display(Markdown('### Inspeção por frase — heurística, sem aprovação jurídica'))
    display(pd.DataFrame(inspection['frases']))
    display(Markdown('### Fontes efetivamente entregues'))
    display(sources_table(result.get('sources',[]),root))
    display(Markdown('**Verificação formal:** '+inspection['status_formal']+
        '\n\n**Alertas:** '+(', '.join(inspection['alertas_formais_por_frase']) or 'nenhum detectado')+
        '\n\n'+inspection['limite']))
    if result.get('revisao_humana_original'):
        display(Markdown('**Decisão humana sobre esta versão original:** '+result['revisao_humana_original']))
    else:
        display(Markdown('**Revisão jurídica desta versão:** pendente.'))


def inspect_saved_results(root):
    """Analisa as saídas existentes, sem alterar respostas, revisões ou métricas antigas."""
    import pandas as pd
    root=Path(root)
    report=root/'reports/legislacao/integracao_rag'
    groups={'original':read_json(report/'respostas_rag_dev.json'),
        'correcao_assistida':read_json(report/'correcoes/respostas_corrigidas_dev.json'),
        'variante_rag':read_json(report/'variantes/respostas_variantes_rag.json')}
    records, phrases, summary = [], [], []
    for group, items in groups.items():
        for item in items:
            if item['status_execucao'] != 'concluida':
                summary.append({'grupo':group,'query_id':item['query_id'],'status_formal':'falha_tecnica'})
                continue
            inspection=inspect_answer(item['resposta'],item.get('sources',[]))
            records.append({'grupo':group,'query_id':item['query_id'],
                'resposta_sha256':text_hash(item['resposta']),**inspection})
            phrases.extend({'grupo':group,'query_id':item['query_id'],**row} for row in inspection['frases'])
            summary.append({'grupo':group,'query_id':item['query_id'],
                'status_formal':inspection['status_formal'],'frases':len(inspection['frases']),
                'possiveis_afirmacoes_sem_citacao':sum(row['sem_citacao'] for row in inspection['frases']),
                'fontes_inexistentes':sum(bool(row['fontes_inexistentes']) for row in inspection['frases'])})
    directory=report/'validacao_por_frase'
    write_json(directory/'inspecoes.json',records)
    pd.DataFrame(phrases).to_csv(directory/'frases.csv',index=False)
    frame=pd.DataFrame(summary)
    frame.to_csv(directory/'resumo.csv',index=False)
    return frame


class InteractiveRAG:
    """Consulta livre com o mesmo gerador validado e o mesmo motor D → A."""
    def __init__(self, root):
        self.root=Path(root)
        self.namespace=load_generation_namespace(self.root)
        self.retriever=None

    def responder(self, pergunta, mostrar=True):
        if not isinstance(pergunta,str) or not pergunta.strip():
            raise ValueError('Informe uma pergunta não vazia.')
        question=pergunta.strip()
        query_id='livre_'+text_hash(question)[:20]
        if self.retriever is None:
            self.retriever=VariantRetriever(self.root)
        started=time.perf_counter()
        context=self.retriever.retrieve({'query_id':query_id,'pergunta':question},self.namespace)
        result={'tipo_execucao':'consulta_livre_integrada','query_id':query_id,
            'pergunta':question,**context,'status_revisao':'pendente_revisao',
            'modelo':self.namespace['FINAL_MODEL'],'modelo_digest':self.namespace['MODEL_DIGEST'],
            'prompt_sistema_sha256':text_hash(self.namespace['SYSTEM_PROMPT_LEGAL']),
            'opcoes_geracao':self.namespace['GENERATION_OPTIONS']}
        try:
            result.update(generate_custom(self.namespace,question,context['sources']))
            result['status_execucao']='concluida'
            result['inspecao_por_frase']=inspect_answer(result['resposta'],result['sources'])
        except (RuntimeError,ValueError) as error:
            result.update(status_execucao='falha',erro=str(error))
        result['tempo_total_observado_ms']=(time.perf_counter()-started)*1000
        directory=self.root/'reports/legislacao/integracao_rag/consulta_livre'
        identity=text_hash(str((result['hash_configuracao'],result.get('cache_key'),result.get('erro'))))[:20]
        write_json(directory/f'{query_id}_{identity}.json',result)
        if mostrar:
            show_answer(result,self.root)
        return result
