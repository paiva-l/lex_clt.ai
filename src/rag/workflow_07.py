"""Revisões persistentes, correções limitadas e variantes com recuperação real.

Nenhuma decisão humana é inferida a partir de um acerto técnico. As referências
das variantes nunca entram no prompt de recuperação ou de geração independente.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def extract_field(text, label):
    pattern = r'\*\*' + re.escape(label) + r'(?::)?\*\*\s*'
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ''
    following = text[match.end():]
    return re.split(r'\n\s*\*\*[^\n*]+\*\*', following, maxsplit=1)[0].strip()


def review_status(value):
    lower = value.lower()
    if 'reprovad' in lower:
        return 'reprovada'
    if 'aprovad' in lower:
        return 'aprovada_por_revisor'
    return 'pendente_revisao'


def persist_reviews(root):
    """Lê as decisões efetivamente escritas nas células, preservando seu texto."""
    root = Path(root)
    report = root / 'reports/legislacao/integracao_rag'
    notebook = read_json(root / 'notebooks/07_integracao_rag_legislacao.ipynb')
    originals = {item['query_id']:item for item in read_json(report / 'respostas_rag_dev.json')}
    reviews = []
    for cell in notebook['cells']:
        identifier = cell.get('id', '')
        if not identifier.startswith('visualizacao_respostas_q_'):
            continue
        query_id = identifier.removeprefix('visualizacao_respostas_')
        if query_id not in originals:
            raise ValueError('Célula de revisão sem resultado original correspondente.')
        text = ''.join(cell['source'])
        if originals[query_id]['resposta'] not in text:
            raise ValueError(f'A resposta de {query_id} mudou: não transferir sua revisão para outra versão.')
        header = text.split('**Resposta gerada**', 1)[0]
        match = re.search(r'\*\*Revisão jurídica(?: da resposta original)?:\*\*\s*([^\n]+)', header, re.I)
        decision = match.group(1).strip() if match else 'pendente'
        reviewer_match = re.search(r'\bpor\s+([^\.\n]+)', decision, re.I)
        reviewer = reviewer_match.group(1).strip() if reviewer_match else extract_field(header, 'Revisora').strip('.')
        reference = (extract_field(header, 'Resposta de referência para correção') or
                     extract_field(header, 'Resposta correta de referência:'))
        beginning = header.find('**Execução:**')
        review_markdown = header[beginning:] if beginning >= 0 else header
        item = {'query_id':query_id, 'status_revisao':review_status(decision),
            'decisao_original':decision, 'revisor':reviewer or None,
            'data_revisao':None, 'exportado_em_utc':datetime.now(timezone.utc).isoformat(),
            'motivo':extract_field(header, 'Motivo:'),
            'resposta_referencia_revisada':reference, 'acao':extract_field(header, 'Ação:'),
            'resposta_original_sha256':text_hash(originals[query_id]['resposta']),
            'review_markdown':review_markdown, 'celula_markdown_original':text,
            'celula_sha256':text_hash(text), 'origem':'anotacao_manual_no_notebook'}
        history = report / 'revisoes/historico' / f"{query_id}_{item['celula_sha256']}.json"
        if not history.exists():
            write_json(history, item)
        write_json(report / 'revisoes' / f'{query_id}.json', item)
        reviews.append(item)
    if set(originals) != {item['query_id'] for item in reviews}:
        raise ValueError('Alguma resposta original não possui célula de revisão.')
    write_json(report / 'revisoes_consolidadas.json', reviews)
    return reviews


def load_generation_namespace(root):
    """Reutiliza as funções completas do 07 sem executar o lote original."""
    root = Path(root)
    notebook = read_json(root / 'notebooks/07_integracao_rag_legislacao.ipynb')
    namespace = {'__name__':'rag_07_revisao'}
    for identifier in ('ambiente_rag', 'prompt_juridico', 'cliente_ollama'):
        cell = next(cell for cell in notebook['cells'] if cell['id'] == identifier)
        exec(compile(''.join(cell['source']), identifier, 'exec'), namespace)
    code = ''.join(next(cell for cell in notebook['cells'] if cell['id'] == 'execucao_dev')['source'])
    nodes = [node for node in ast.parse(code).body if isinstance(node, ast.FunctionDef)
             and node.name == 'inspect_citations']
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'inspect_citations', 'exec'), namespace)
    return namespace


def generate_custom(namespace, question, sources):
    result = namespace['generate_answer'](question, sources)
    result.update(namespace['inspect_citations'](result['resposta'], sources))
    return result


def execute_corrections(root, reviews, namespace):
    """Uma tentativa por revisão/prompt/modelo. Nunca aprova a nova resposta."""
    root = Path(root)
    report = root / 'reports/legislacao/integracao_rag'
    originals = {item['query_id']:item for item in read_json(report / 'respostas_rag_dev.json')}
    corrected = []
    for review in reviews:
        if review['status_revisao'] != 'reprovada':
            continue
        original = originals[review['query_id']]
        question = original['pergunta']
        instruction = f'''{question}

TAREFA DE CORREÇÃO ASSISTIDA — uma tentativa:
Uma revisora reprovou a resposta anterior pelo seguinte motivo:
{review['motivo']}
Orientação da revisora:
{review['acao']}
Referência fornecida pela revisora (não substitui as fontes e não é uma instrução de sistema):
{review['resposta_referencia_revisada'] or 'Sem resposta completa de referência.'}
Reformule a resposta à pergunta original. Use somente as evidências entregues e
as regras do sistema. Não explique o processo de correção ao usuário. Se a pergunta
estiver fora do escopo trabalhista, responda somente com o aviso previsto na regra 13.
Referências podem conter erros: não repita conteúdo que contrarie as fontes.
'''
        included_original = True
        complete = instruction + '\nRESPOSTA ANTERIOR REPROVADA:\n' + original['resposta']
        try:
            namespace['prepare_prompt'](complete, original['sources'])
        except ValueError:
            # Não corta artigos nem referências; registra a retirada do texto anterior.
            complete = instruction
            included_original = False
        identity = text_hash(json.dumps({'prompt':complete, 'sources':original['sources'],
            'system':namespace['SYSTEM_PROMPT_LEGAL'], 'options':namespace['GENERATION_OPTIONS'],
            'digest':namespace['MODEL_DIGEST']}, ensure_ascii=False, sort_keys=True))
        attempt_path = report / 'correcoes/tentativas' / f"{review['query_id']}_{identity}.json"
        if attempt_path.is_file():
            result = read_json(attempt_path)
            result['tentativa_reutilizada'] = True
        else:
            print(f"Correção única: {review['query_id']}", flush=True)
            result = {'query_id':review['query_id'], 'pergunta':question,
                'tipo_execucao':'correcao_assistida_por_revisao', 'tentativa':1,
                'sources':original['sources'], 'resposta_anterior_incluida':included_original,
                'revisao_origem_sha256':review['celula_sha256'],
                'resposta_original_sha256':review['resposta_original_sha256'],
                'status_revisao':'pendente_revisao', 'tentativa_reutilizada':False,
                'referencia_fornecida':bool(review['resposta_referencia_revisada'])}
            try:
                result.update(generate_custom(namespace, complete, original['sources']))
                result['status_execucao'] = 'concluida'
            except (RuntimeError, ValueError) as error:
                result.update(status_execucao='falha', erro=str(error))
            write_json(attempt_path, result)
        # Nenhuma nova tentativa é disparada automaticamente, inclusive após falha.
        from .review_persistence_07 import matching_review
        human_review=matching_review(root,'correcao',result)
        if human_review is not None:
            result=dict(result,status_revisao=human_review['status_revisao'],
                revisao_juridica=human_review['status_revisao'],escopo_revisao=human_review['escopo_status'])
        corrected.append(result)
        write_json(report / 'correcoes/respostas_corrigidas_dev.json', corrected)
    return corrected


class VariantRetriever:
    """Usa as mesmas definições e parâmetros do 06, sem executar suas métricas."""
    def __init__(self, root):
        import torch
        from sentence_transformers import SentenceTransformer, CrossEncoder
        root = Path(root)
        notebook = read_json(root / 'notebooks/06_experimentos_recuperacao.ipynb')
        cells = {cell['id']:''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type']=='code'}
        ns = {'__name__':'retrieval_variants_07'}
        exec(compile(cells['config_hyde'], '06_config', 'exec'), ns)
        exec(compile(cells['fontes_code'], '06_fontes', 'exec'), ns)
        ns['REPORT_DIR'] = root / 'reports/legislacao/integracao_rag/variantes/recuperacao'
        ns['REPORT_DIR'].mkdir(parents=True, exist_ok=True)
        # Carrega apenas imports, constantes e funções HyDE; não executa lote do 06.
        tree = ast.parse(cells['hyde_code'])
        definitions = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
                definitions.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HYDE_PROMPT' for t in node.targets):
                definitions.append(node)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), '06_hyde_defs', 'exec'), ns)
        ns['HYDE_MODEL_ID'] = ns['configure_ollama_model']()
        torch.set_num_threads(4)
        # CPU para não disputar VRAM com o gerador local. Não codifica o corpus.
        self.encoder = SentenceTransformer(ns['EMBEDDING_MODEL'], local_files_only=True, device='cpu')
        self.encoder.max_seq_length = 8192
        reranker = CrossEncoder(ns['RERANK_MODEL'], max_length=8192, local_files_only=True, device='cpu')
        ns.update(reranker=reranker, rerank_audit=[],
            RERANK_CACHE_DIR=root / 'indexes/legislacao/reranking')
        functions = [node for node in ast.parse(cells['rerank_code']).body if isinstance(node, ast.FunctionDef)]
        exec(compile(ast.Module(body=functions, type_ignores=[]), '06_rerank_defs', 'exec'), ns)
        self.ns = ns
        self.parents = {item['artigo_id']:item for item in read_json(root / 'data/chunks/legislacao/chunks_A_artigo.json')}
        self.children = {item['chunk_id']:item for item in ns['chunks_corpora'][ns['CHUNK_STRATEGY']].to_dict('records')}
        self.positions = {str(item):i for i,item in enumerate(ns['chunks_corpora'][ns['CHUNK_STRATEGY']]['chunk_id'])}
        self.root = root

    def retrieve(self, variant, generation_ns):
        import time
        from src.storage.parent_documents import expand_parent_documents, format_parent_context
        ns = self.ns
        query_id, question = variant['query_id'], variant['pergunta']
        cache_dir = self.root / 'reports/legislacao/integracao_rag/variantes/recuperacao'
        # A chave inclui modelos, corpora, prompt gerador e orçamento completo.
        identity = ns['digest_json']({'question':question, 'query_id':query_id,
            'chunks':ns['chunk_hashes'], 'hyde_model':ns['HYDE_MODEL_ID'],
            'hyde_prompt':ns['HYDE_PROMPT'], 'hyde_config':ns['HYDE_GENERATION_CONFIG'],
            'reranker':ns['RERANK_MODEL'], 'depth':ns['CANDIDATE_DEPTH'],
            'rerank_candidates':ns['RERANK_CANDIDATES'], 'rrf_k':ns['RRF_K'],
            'parent_hash':text_hash(json.dumps(self.parents, ensure_ascii=False, sort_keys=True)),
            'generation_system':generation_ns['SYSTEM_PROMPT_LEGAL'],
            'input_limit':generation_ns['INPUT_LIMIT'], 'top_k':ns['PARENT_TOP_K']})
        cache = cache_dir / f'{query_id}_{identity}.json'
        if cache.is_file():
            result = read_json(cache)
            result['recuperacao_cache_hit'] = True
            return result
        started = time.perf_counter()
        hyde = ns['prepare_hyde_documents'](ns['pd'].DataFrame([{'query_id':query_id,'pergunta':question}]),
            ns['HYDE_CACHE_DIR'], ns['HYDE_MODEL_ID'], ns['generate_hyde_ollama'])[query_id]
        texts = [question, hyde['text']]
        if any(len(self.encoder.tokenizer.encode(text, truncation=False)) > 8192 for text in texts):
            raise ValueError('Consulta da variante excedeu o limite BGE-M3.')
        vectors = self.encoder.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        rankings = []
        for vector in vectors:
            matches = ns['search_chunks'](ns['DATABASE_CONNECTION'], ns['get_sql_dataset'](ns['CHUNK_STRATEGY']),
                vector, top_k=ns['CANDIDATE_DEPTH'])
            rankings.append([(self.positions[item['chunk_id']],float(item['score'])) for item in matches])
        fused = ns['reciprocal_rank_fusion'](rankings)[:ns['RERANK_CANDIDATES']]
        reordered = ns['rerank_candidates'](query_id,question,ns['CHUNK_STRATEGY'],fused)
        corpus = ns['chunks_corpora'][ns['CHUNK_STRATEGY']]
        results = [{'chunk_id':str(corpus.iloc[i]['chunk_id']), 'score':score} for i,score in reordered]
        parents, _ = expand_parent_documents(results, self.children, self.parents, top_k=ns['PARENT_TOP_K'])
        accepted, omitted = [], []
        for parent in parents:
            candidate = accepted + [dict(parent, source_id=f'Fonte {len(accepted)+1}')]
            try:
                generation_ns['prepare_prompt'](question, candidate)
                accepted = candidate
            except ValueError:
                omitted.append({'artigo_id':parent['artigo_id'], 'reason':'orcamento_prompt_completo'})
        generation_ns['prepare_prompt'](question, accepted)
        result = {'query_id':query_id, 'pergunta':question, 'sources':accepted,
            'omitted':omitted, 'context_text':format_parent_context(accepted),
            'ranking_d':results, 'hyde_cache_sha256':hyde['cache_sha256'],
            'hyde_text':hyde['text'], 'hyde_synthetic_not_evidence':True,
            'estrategia':'D_para_A', 'backend':'pgvector', 'recuperacao_cache_hit':False,
            'tempo_recuperacao_ms':(time.perf_counter()-started)*1000,
            'hash_configuracao':identity, 'embedding_corpus_recalculado':False}
        write_json(cache, result)
        return result


def load_variants(root):
    root = Path(root)
    nb = read_json(root / 'notebooks/07_integracao_rag_legislacao.ipynb')
    rows = []
    for group in ('q_dev_03','q_dev_06'):
        rows.extend(read_json(root / f'reports/legislacao/integracao_rag/variantes/{group}_variantes.json'))
    for item in rows:
        cell = next(c for c in nb['cells'] if c.get('id') == f"variantes_{item['grupo_pergunta']}_{item['query_id']}")
        text = ''.join(cell['source'])
        reference = extract_field(text, 'Resposta de referência adaptada da principal')
        item['resposta_referencia'] = reference
        item['revisao_referencia_original'] = extract_field(text, 'Revisão jurídica da referência:')
        item['celula_referencia_sha256'] = text_hash(text)
    return rows


def execute_variants(root, namespace):
    root = Path(root)
    directory = root / 'reports/legislacao/integracao_rag/variantes'
    variants = load_variants(root)
    # Salva uma fotografia antes de gerar; referências não são fornecidas ao modelo.
    write_json(directory / 'referencias_utilizadas_apenas_para_revisao.json', variants)
    retriever = VariantRetriever(root)
    outputs = []
    for item in variants:
        print(f"Variante — nova recuperação e geração: {item['query_id']}", flush=True)
        result = {'query_id':item['query_id'], 'grupo_pergunta':item['grupo_pergunta'],
            'pergunta':item['pergunta'], 'tipo_execucao':'variante_rag_independente',
            'referencia_fornecida_ao_modelo':False, 'status_revisao':'pendente_revisao'}
        try:
            context = retriever.retrieve(item, namespace)
            result.update(context)
            result.update(generate_custom(namespace, item['pergunta'], context['sources']))
            result['status_execucao'] = 'concluida'
        except (RuntimeError, ValueError, OSError) as error:
            result.update(status_execucao='falha', erro=str(error))
        from .review_persistence_07 import matching_review
        human_review=matching_review(root,'variante',result)
        if human_review is not None:
            result.update(status_revisao=human_review['status_revisao'],
                revisao_juridica=human_review['status_revisao'],escopo_revisao=human_review['escopo_status'])
        outputs.append(result)
        write_json(directory / 'respostas_variantes_rag.json', outputs)
    return outputs


def diagnostic(root, reviews, corrections, variants):
    import pandas as pd
    import matplotlib.pyplot as plt
    root = Path(root)
    directory = root / 'reports/legislacao/integracao_rag/diagnostico_revisoes'
    directory.mkdir(parents=True, exist_ok=True)
    originals = read_json(root / 'reports/legislacao/integracao_rag/respostas_rag_dev.json')
    from .review_persistence_07 import matching_review
    rows = []
    for kind, results in [('original', originals), ('correcao_assistida', corrections), ('variante_rag',variants)]:
        for item in results:
            human_review=matching_review(root,kind,item) if kind!='original' else None
            new_status=(human_review['status_revisao'] if human_review else
                'falha_tecnica_sem_resposta' if item['status_execucao']=='falha' else item.get('status_revisao','pendente_revisao'))
            rows.append({'tipo':kind, 'query_id':item['query_id'],
                'concluida':item['status_execucao']=='concluida',
                'alertas_formais':len(item.get('alertas_formais',[])),
                'tokens_entrada':item.get('tokens_entrada'), 'tokens_saida':item.get('tokens_saida'),
                'tempo_geracao_servidor_ms':item.get('tempo_geracao_servidor_ms'),
                'tempo_chamada_ms':item.get('tempo_chamada_ms'), 'cache_hit':item.get('cache_hit'),
                'revisao':next((r['status_revisao'] for r in reviews if r['query_id']==item['query_id']),
                    'pendente_revisao') if kind=='original' else new_status,
                'escopo_revisao':human_review.get('escopo_status') if human_review else 'resposta_original',
                'celula_tem_edicoes_na_resposta':human_review.get('celula_tem_edicoes_na_resposta',False) if human_review else False})
    frame = pd.DataFrame(rows)
    frame.to_csv(directory / 'diagnostico_por_resposta.csv', index=False)
    technical = frame.groupby('tipo',sort=False).agg(
        respostas=('query_id','count'), concluidas=('concluida','sum'),
        tokens_entrada=('tokens_entrada','mean'), tokens_saida=('tokens_saida','mean'),
        tempo_servidor_ms=('tempo_geracao_servidor_ms','mean'),
        alertas_formais=('alertas_formais','sum'))
    technical.to_csv(directory / 'resumo_tecnico.csv')
    review_counts = pd.Series([r['status_revisao'] for r in reviews]).value_counts().reindex(
        ['aprovada_por_revisor','reprovada','pendente_revisao'],fill_value=0)
    new_completed = sum(item['status_execucao']=='concluida' for item in corrections+variants)
    new_failures = len(corrections)+len(variants)-new_completed
    new_frame=frame[frame['tipo'].ne('original')]
    pending=int((new_frame['concluida'] & new_frame['revisao'].isin(['pendente_revisao','sem_anotacao_local'])).sum())
    revised=int(new_frame['revisao'].isin(['aprovada_por_revisor','reprovada']).sum())
    new_counts={kind:group['revisao'].value_counts().to_dict() for kind,group in new_frame.groupby('tipo')}
    edited=int(new_frame['celula_tem_edicoes_na_resposta'].sum())
    curated_path=root/'reports/legislacao/integracao_rag/revisoes_versoes_revisadas.json'
    preserved_decisions=len(read_json(curated_path)) if curated_path.is_file() else revised
    fig, axes = plt.subplots(2,3,figsize=(17,10))
    review_counts.plot.bar(ax=axes[0,0],color=['#228866','#cc5544','#999999'],rot=15)
    axes[0,0].set_title('Revisões humanas — respostas originais')
    technical[['respostas','concluidas']].plot.bar(ax=axes[0,1],rot=15)
    axes[0,1].set_title('Execução técnica — não mede acerto jurídico')
    frame.assign(com_alerta=frame.alertas_formais.gt(0)).groupby('tipo',sort=False).com_alerta.sum().plot.bar(
        ax=axes[0,2],rot=15,color='#cc9944')
    axes[0,2].set_title('Respostas com alertas formais')
    technical[['tokens_entrada','tokens_saida']].plot.bar(ax=axes[1,0],rot=15)
    axes[1,0].set_title('Média de tokens')
    (technical['tempo_servidor_ms']/1000).plot.bar(ax=axes[1,1],rot=15,color='#4477aa')
    axes[1,1].set_title('Geração no servidor — segundos médios')
    axes[1,2].axis('off')
    axes[1,2].text(0,1,
        f"Decisões sobre versões revisadas preservadas: {preserved_decisions}\n"
        f"Últimas saídas com revisão correspondente: {revised}\n"
        f"Outras saídas sem decisão correspondente: {pending}\n"
        f"Falhas técnicas para conferir: {new_failures}\n\n"
        f"Células com acréscimos na resposta: {edited}\n"
        'Suas decisões anteriores continuam válidas.\n'
        'Nova geração não substitui texto revisado.\n'
        'Acréscimos não são atribuídos ao Ollama.\n\n'
        'Correções receberam feedback/referência.\n'
        'Variantes foram geradas sem gabarito.\n'
        'Tempos de cache não são inferência nova.\n'
        'Médias usam telemetria disponível.\n'
        'Alertas não comprovam erro jurídico.\n'
        'Não há comparação controlada de\nmelhora jurídica antes e depois.\n\n'
        'Teste congelado não utilizado.\nEmbeddings do corpus preservados.', va='top',fontsize=11)
    for ax in axes.flat:
        ax.set_xlabel('')
    fig.tight_layout()
    fig.savefig(directory / 'diagnostico_revisoes_correcoes_variantes.png',dpi=150)
    summary = {'revisoes_originais':review_counts.to_dict(),
        'correcoes':len(corrections), 'variantes':len(variants),
        'novas_respostas_pendentes':pending, 'falhas_tecnicas_novas':new_failures,
        'novas_versoes_revisadas':revised, 'revisoes_novas_por_grupo':new_counts,
        'decisoes_versoes_anteriores_preservadas':preserved_decisions,
        'celulas_com_edicoes_na_resposta':edited,
        'novas_execucoes_total':len(corrections)+len(variants),
        'medias_tecnicas':'Somente telemetria disponível; falhas sem contadores não são tratadas como zero.',
        'melhora_juridica_validada':False, 'teste_utilizado':False,
        'gerado_em_utc':datetime.now(timezone.utc).isoformat()}
    write_json(directory / 'manifesto_diagnostico.json', summary)
    return frame, technical, fig, summary


def append_answer_cells(root, corrections, variants):
    """Acrescenta saídas em outras células; não toca nas revisões e referências."""
    root = Path(root)
    path = root / 'notebooks/07_integracao_rag_legislacao.ipynb'
    nb = read_json(path)
    prefix = 'novas_respostas_07_'
    existing = {cell.get('id'):cell for cell in nb['cells']}
    for kind, rows in [('correcao',corrections), ('variante',variants)]:
        for item in rows:
            from .review_persistence_07 import matching_review
            saved_review=matching_review(root,kind,item)
            if saved_review and saved_review.get('celula_ausente') and item['status_execucao']=='falha':
                continue
            sources = '\n'.join(f"- **[{s['source_id']}]** {s['artigo_ref']} — `{s['caminho_relativo']}`."
                for s in item.get('sources',[]))
            text = f"### {'Correção assistida' if kind=='correcao' else 'Variante com nova recuperação'} — `{item['query_id']}`\n\n"
            text += f"**Pergunta:** {item['pergunta']}\n\n"
            text += f"**Execução:** {item['status_execucao']} · **Revisão jurídica desta nova versão:** pendente.\n\n"
            text += '**Nova resposta do modelo**\n\n' + item.get('resposta', item.get('erro','Sem resposta.')) + '\n\n'
            text += f"**Fontes efetivamente entregues nesta execução**\n\n{sources or 'Nenhuma fonte.'}\n\n"
            text += f"**Alertas formais:** {', '.join(item.get('alertas_formais',[])) or 'nenhum detectado'}.\n\n"
            text += f"**Tokens:** {item.get('tokens_entrada','—')} de entrada · {item.get('tokens_saida','—')} de saída.\n\n"
            text += ('Correção com feedback da revisora; não é um acerto independente. Uma tentativa, sem aprovação automática.'
                if kind=='correcao' else 'Busca D → A refeita para esta pergunta; referência não fornecida ao modelo. Sem gabarito individual aprovado, não foi calculada uma métrica de acerto.')
            identifier = prefix+kind+'_'+item['query_id']
            response_digest = text_hash(item.get('resposta',item.get('erro','Sem resposta.')))
            if identifier in existing:
                previous = existing[identifier]
                previous_text = ''.join(previous['source'])
                # Preserva inclusive anotações acrescentadas pelo usuário após a geração.
                if (previous.get('metadata',{}).get('response_sha256') == response_digest or
                        (item.get('resposta') and item['resposta'] in previous_text)):
                    continue
                identifier += '_' + response_digest[:12]
                if identifier in existing:
                    continue
            cell = {'id':identifier, 'cell_type':'markdown',
                'metadata':{'response_sha256':response_digest}, 'source':text.splitlines(keepends=True)}
            nb['cells'].append(cell)
            existing[identifier] = cell
    write_json(path, nb)
