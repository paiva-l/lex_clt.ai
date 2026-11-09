"""Avaliação do teste congelado: execução real e métricas sem gabarito no prompt."""
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def validate_frozen(root, check_ollama=False):
    root = Path(root)
    folder = root / 'reports/legislacao/integracao_rag/configuracao_congelada'
    pointer = read(folder / 'configuracao_ativa.json')
    filename = pointer['arquivo']
    if Path(filename).name != filename:
        raise ValueError('Nome de configuração inválido.')
    frozen = read(folder / filename)
    config = frozen['configuracao']
    identity = sha(json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())
    if identity != frozen['configuracao_sha256'] or identity != pointer['configuracao_sha256']:
        raise ValueError('Identidade da configuração congelada divergente.')
    for name, expected in config['arquivos_sha256'].items():
        if sha((root / name).read_bytes()) != expected:
            raise ValueError(f'Arquivo alterado depois do congelamento: {name}')
    for notebook, expected_cells in [('06_experimentos_recuperacao.ipynb', config['codigo_06']),
            ('07_integracao_rag_legislacao.ipynb', config['codigo_07'])]:
        cells = {c['id']: ''.join(c['source']) for c in read(root / 'notebooks' / notebook)['cells']}
        if any(cells.get(name) != code for name, code in expected_cells.items()):
            raise ValueError(f'Código alterado depois do congelamento: {notebook}')
    budget = read(root / 'reports/legislacao/recuperacao/D_para_A_ollama_hyde_rrf_reranking/orcamento_contexto_llm.json')
    if any(budget.get(k) != value for k, value in config['orcamento'].items()):
        raise ValueError('Orçamento alterado depois do congelamento.')
    strategy = config['recuperacao']['CHUNK_STRATEGY']
    imported = read(root / 'reports/legislacao/pgvector' / strategy / 'resultado_importacao.json')
    if imported['dataset_id'] != config['sql_datasets'][strategy]:
        raise ValueError('Dataset PostgreSQL alterado depois do congelamento.')
    if check_ollama:
        with urlopen('http://127.0.0.1:11434/api/tags', timeout=15) as response:
            installed = {m['name']: m['digest'] for m in json.load(response)['models']}
        for model in (config['modelo_gerador'], config['hyde']):
            name = model.get('nome') or model['modelo']
            if installed.get(name) != model['digest']:
                raise ValueError(f'Modelo Ollama difere da versão congelada: {name}')
    return frozen


def load_test(root):
    """Replica a identidade semântica criada no 05; não altera o conjunto."""
    import pandas as pd
    folder = Path(root) / 'data/evaluation/legislacao'
    question_rows = read(folder / 'eval_dataset_test_aprovado.json')
    ids = {r['query_id'] for r in question_rows}
    reference_rows = [r for r in read(folder / 'referencias_aprovadas.json') if r['query_id'] in ids]
    # Preserva os tipos do JSON; inferência do pandas converteria posições string em números.
    payload = {'perguntas': sorted([{k: v for k, v in r.items()
        if k not in ('resultado_referencia', 'candidatos')} for r in question_rows], key=lambda r: r['query_id']),
        'referencias': sorted(reference_rows, key=lambda r: r['referencia_id'])}
    questions = pd.DataFrame(question_rows)
    references = pd.DataFrame(reference_rows)
    identity = sha(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode())
    if identity != read(folder / 'teste_congelado.json')['sha256']:
        raise ValueError('Teste ou referências divergem do congelamento no 05.')
    if questions.empty or not questions['query_id'].is_unique or not questions['split'].eq('test').all():
        raise ValueError('Conjunto de teste vazio, duplicado ou misturado com desenvolvimento.')
    if not questions['elegivel_metricas'].eq(True).all():
        raise ValueError('Teste contém perguntas não aprovadas.')
    for row in questions.to_dict('records'):
        if row['rotulo_resposta'] == 'respondível' and references[references.query_id.eq(row['query_id'])].empty:
            raise ValueError('Pergunta respondível sem evidência de referência.')
    return questions, references, identity


def output_folder(root, frozen):
    return Path(root) / 'reports/legislacao/avaliacao_final' / frozen['configuracao_sha256']


def run_test(root, frozen, questions):
    """Somente id e pergunta atravessam a fronteira de geração."""
    from .workflow_07 import load_generation_namespace, VariantRetriever, generate_custom
    from .presentation_07 import inspect_answer
    validate_frozen(root, check_ollama=True)
    folder = output_folder(root, frozen)
    destination = folder / 'respostas_teste.json'
    existing = read(destination) if destination.exists() else []
    expected_questions = {r['query_id']: r['pergunta'] for r in questions.to_dict('records')}
    if any(r['configuracao_sha256'] != frozen['configuracao_sha256'] or
            expected_questions.get(r['query_id']) != r['pergunta'] for r in existing):
        raise ValueError('Resultados existentes pertencem a outra configuração ou pergunta.')
    if len({r['query_id'] for r in existing}) != len(existing):
        raise ValueError('Resultados existentes duplicados.')
    namespace = None
    retriever = None
    rows = {r['query_id']: r for r in existing}
    for question in questions[['query_id', 'pergunta']].to_dict('records'):
        query_id = question['query_id']
        if query_id in rows:
            print(f'{query_id}: resultado existente preservado ({rows[query_id]["status_execucao"]}).', flush=True)
            continue
        if namespace is None:
            try:
                namespace = load_generation_namespace(root)
                retriever = VariantRetriever(root)
            except Exception as error:
                write(folder / 'falha_inicializacao.json', {
                    'configuracao_sha256': frozen['configuracao_sha256'],
                    'registrado_em_utc': datetime.now(timezone.utc).isoformat(),
                    'tipo_erro': type(error).__name__,
                    'status': 'Não iniciou a avaliação; falha ao preparar os modelos ou serviços.',
                    'perguntas_marcadas_como_avaliadas': False})
                raise RuntimeError('Não foi possível inicializar o pipeline. Confira memória, modelos locais, Ollama e PostgreSQL.') from error
            config = frozen['configuracao']
            if (namespace['SYSTEM_PROMPT_LEGAL'] != config['prompt']['system'] or
                    namespace['GENERATION_OPTIONS'] != config['modelo_gerador']['options'] or
                    namespace['MODEL_DIGEST'] != config['modelo_gerador']['digest']):
                raise ValueError('Gerador efetivo difere da configuração congelada.')
            if retriever.ns['HYDE_MODEL_ID'].split(':')[-1] != config['hyde']['digest']:
                raise ValueError('Identidade HyDE efetiva divergente.')
        started = time.perf_counter()
        row = {**question, 'configuracao_sha256': frozen['configuracao_sha256'],
            'status_revisao': 'sem_avaliacao_humana_desta_resposta', 'sources': []}
        print(f'{query_id}: recuperacao D para A e geracao real...', flush=True)
        try:
            row.update(retriever.retrieve(question, namespace))
            row.update(generate_custom(namespace, question['pergunta'], row['sources']))
            row['status_execucao'] = 'concluida'
            row['resposta_sha256'] = sha(row['resposta'].encode())
            row['inspecao_por_frase'] = inspect_answer(row['resposta'], row['sources'])
        except Exception as error:
            # Não expõe mensagens de conexão que possam conter credenciais.
            row.update(status_execucao='falha', tipo_erro=type(error).__name__,
                erro='Execução interrompida; conferir dependências, serviço local, banco e orçamento. Não foi simulada resposta.')
        row['tempo_total_observado_ms'] = (time.perf_counter() - started) * 1000
        rows[query_id] = row
        write(destination, list(rows.values()))
    validate_frozen(root, check_ollama=True)
    write(folder / 'manifesto_execucao.json', {'configuracao_sha256': frozen['configuracao_sha256'],
        'gerado_em_utc': datetime.now(timezone.utc).isoformat(), 'respostas_registradas': len(rows),
        'teste_sha256': load_test(root)[2], 'gabarito_fornecido_ao_modelo': False,
        'correcao_com_feedback_no_teste': False, 'embeddings_corpus_recalculados': False,
        'avaliador_sha256': sha(Path(__file__).read_bytes()),
        'notebook_08_sha256': sha((Path(root) / 'notebooks/08_avaliacao_final_rag_legislacao.ipynb').read_bytes())})
    return list(rows.values())


def reference_key(row):
    # Os chunks A preservam a posição da fonte sob este nome específico.
    position = row.get('posicao_inicio', row.get('posicao_inicio_original'))
    if position is None:
        raise ValueError('Dispositivo sem posição rastreável no arquivo de origem.')
    return (row.get('norma') or row.get('caminho_relativo'), int(position))


def retrieval_metrics(sources, references, k=3):
    """Relevância binária por norma + posição exata; deduplicação por artigo."""
    expected = {reference_key(r) for r in references}
    if not expected:
        return {'hit': None, 'recall': None, 'mrr': None, 'ndcg': None, 'cobertura_evidencias': None}
    unique, seen = [], set()
    for source in sources:
        key = reference_key(source)
        if key not in seen:
            unique.append(source)
            seen.add(key)
    top = unique[:k]
    gains = [int(reference_key(s) in expected) for s in top]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(expected), k)))
    texts = [s.get('conteudo_chunk') or s.get('conteudo') or s.get('texto_estruturado') or '' for s in top]
    covered = [bool(r.get('trecho_evidencia_selecionado')) and any(
        reference_key(s) == reference_key(r) and r['trecho_evidencia_selecionado'] in text
        for s, text in zip(top, texts)) for r in references]
    return {'hit': int(any(gains)), 'recall': sum(gains) / len(expected),
        'mrr': next((1 / (i + 1) for i, gain in enumerate(gains) if gain), 0),
        'ndcg': dcg / ideal, 'cobertura_evidencias': sum(covered) / len(covered)}


def evaluate(root, frozen, questions, references, results):
    import pandas as pd
    folder = output_folder(root, frozen)
    result_by_id = {r['query_id']: r for r in results}
    base_path = Path(root) / 'data/processed/legislacao/legislacao_artigos_completos.json'
    base_hash = sha(base_path.read_bytes())
    if not questions['base_sha256_anotacao'].eq(base_hash).all():
        raise ValueError('Base estruturada diverge daquela usada na anotação do teste.')
    articles = {a['artigo_id']: a for a in read(base_path)}
    rows = []
    for q in questions.to_dict('records'):
        result = result_by_id.get(q['query_id'])
        refs = references[references.query_id.eq(q['query_id'])].to_dict('records')
        if result and (result.get('configuracao_sha256') != frozen['configuracao_sha256'] or result['pergunta'] != q['pergunta']):
            raise ValueError('Resposta não corresponde ao teste/configuração atual.')
        metric_sources = []
        for source in result.get('sources', []) if result else []:
            article = articles.get(source['artigo_id'])
            if article is None or any(source[k] != article[k] for k in ('caminho_relativo', 'sha256_fonte')):
                raise ValueError('Artigo recuperado não corresponde à base anotada.')
            if not source.get('corpo_chunk') or not any(source['corpo_chunk'] in article[k]
                    for k in ('texto_original', 'texto_artigo_completo')):
                raise ValueError('Texto recuperado diverge do artigo anotado.')
            # Algumas exportações A têm posição nula. Resolve pelo artigo_id,
            # conferindo fonte e texto antes de usar a posição da base estruturada.
            metric_sources.append({**source, 'posicao_inicio': article['posicao_inicio']})
        metrics = retrieval_metrics(metric_sources, refs)
        row = {'query_id': q['query_id'], 'rotulo_resposta': q['rotulo_resposta'],
            'status_execucao': result['status_execucao'] if result else 'nao_executada',
            'fontes_entregues': len(result.get('sources', [])) if result else 0,
            'caracteres_contexto': sum(len(s.get('conteudo_chunk', '')) for s in result.get('sources', [])) if result else 0,
            **metrics}
        for field in ('tokens_entrada', 'tokens_saida', 'tempo_total_observado_ms', 'tempo_geracao_servidor_ms', 'cache_hit', 'recuperacao_cache_hit'):
            row[field] = result.get(field) if result else None
        row['alertas_formais'] = len(result.get('alertas_formais', [])) if result and result['status_execucao'] == 'concluida' else None
        rows.append(row)
    frame = pd.DataFrame(rows)
    # Não calcula resultado final parcial como se o teste tivesse terminado.
    complete = frame.status_execucao.ne('nao_executada').all()
    positive = frame[frame.rotulo_resposta.eq('respondível')]
    summary = {key: float(positive[key].mean()) if complete and not positive.empty else None
        for key in ('hit', 'recall', 'mrr', 'ndcg', 'cobertura_evidencias')}
    summary.update(total=len(frame), concluidas=int(frame.status_execucao.eq('concluida').sum()),
        perguntas_respondiveis=len(positive), casos_sem_resposta=int(frame.rotulo_resposta.eq('sem_resposta').sum()),
        falhas=int(frame.status_execucao.eq('falha').sum()), nao_executadas=int(frame.status_execucao.eq('nao_executada').sum()),
        contexto_k=3, agregacao='Macro por pergunta respondível; casos sem referência não entram nas métricas de recuperação.',
        qualidade_juridica='Exige revisão humana; não inferida de citações ou métricas de recuperação.',
        acuracia_juridica=None, taxa_alucinacao=None, teste_completo=bool(complete))
    review_path = folder / 'revisao_juridica_teste.csv'
    reviewed = []
    if review_path.exists():
        for review in pd.read_csv(review_path, keep_default_na=False).to_dict('records'):
            result = result_by_id.get(review['query_id'])
            if (result and review.get('configuracao_sha256') == frozen['configuracao_sha256']
                    and review.get('resposta_sha256') == result.get('resposta_sha256')
                    and review.get('decisao') in ('aprovada', 'reprovada') and review.get('revisor')):
                reviewed.append(review)
    summary['revisoes_humanas_registradas'] = len(reviewed)
    summary['aprovadas_pela_revisora'] = sum(r['decisao'] == 'aprovada' for r in reviewed)
    summary['reprovadas_pela_revisora'] = sum(r['decisao'] == 'reprovada' for r in reviewed)
    summary['proporcao_aprovada_pela_revisora'] = (
        summary['aprovadas_pela_revisora'] / len(frame) if len(reviewed) == len(frame) else None)
    if len(reviewed) == len(frame):
        summary['qualidade_juridica'] = 'Revisão humana registrada para todas as saídas originais; observações e correções preservadas. Não representa certificação independente.'
    folder.mkdir(parents=True, exist_ok=True)
    frame.to_csv(folder / 'metricas_por_pergunta.csv', index=False)
    write(folder / 'resumo_metricas.json', summary)
    result_file = folder / 'respostas_teste.json'
    write(folder / 'manifesto_avaliacao.json', {
        'configuracao_sha256': frozen['configuracao_sha256'],
        'avaliado_em_utc': datetime.now(timezone.utc).isoformat(),
        'avaliador_sha256': sha(Path(__file__).read_bytes()),
        'respostas_sha256': sha(result_file.read_bytes()) if result_file.exists() else None,
        'dispositivo_exato': 'norma e posição da base estruturada, com artigo_id, texto e fonte conferidos',
        'qualidade_juridica_automatica': False})
    return frame, summary


def export_review_template(root, frozen, questions, results):
    import pandas as pd
    folder = output_folder(root, frozen)
    path = folder / 'revisao_juridica_teste.csv'
    previous = pd.read_csv(path, keep_default_na=False).to_dict('records') if path.exists() else []
    rows = []
    for result in results:
        if result['status_execucao'] != 'concluida':
            continue
        base = {'query_id': result['query_id'], 'resposta_sha256': result['resposta_sha256'],
            'configuracao_sha256': frozen['configuracao_sha256'], 'decisao': '', 'suporte_fontes': '',
            'citacoes_corretas': '', 'conduta_adequada': '', 'recusa_adequada_se_aplicavel': '',
            'motivo': '', 'revisor': ''}
        old = next((r for r in previous if all(r.get(k) == base[k] for k in
            ('query_id', 'resposta_sha256', 'configuracao_sha256'))), None)
        rows.append(old or base)
    # Template só é criado quando existem respostas reais; preserva anotações.
    if rows:
        pd.DataFrame(rows).to_csv(path, index=False)
    return path
