"""Congela configuração sem executar modelos nem abrir perguntas de teste."""
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


def freeze_configuration(root):
    root = Path(root)
    def read(relative):
        return json.loads((root / relative).read_text(encoding='utf-8'))
    def digest(data):
        return hashlib.sha256(data).hexdigest()
    def cells(relative):
        return {c['id']: ''.join(c['source']) for c in read(relative)['cells'] if c['cell_type'] == 'code'}
    def literals(source):
        values = {}
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = value
        return values

    nb07 = cells('notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb')
    nb06 = cells('notebooks/01_legislacao/06_experimentos_recuperacao.ipynb')
    config = literals(nb06['config_hyde'])
    prompt = literals(nb07['prompt_juridico'])['SYSTEM_PROMPT_LEGAL']
    hyde_prompt = literals(nb06['hyde_code'])['HYDE_PROMPT']
    report = 'reports/legislacao/recuperacao/D_para_A_ollama_hyde_rrf_reranking/'
    budget = read(report + 'orcamento_contexto_llm.json')
    retrieval = read(report + 'manifesto_recuperacao.json')
    parents = read(report + 'manifesto_parent_document.json')
    # Confirma a identidade instalada; não chama o endpoint de geração.
    with urlopen('http://127.0.0.1:11434/api/tags', timeout=15) as response:
        installed = json.load(response)['models']
    def model_digest(name):
        entry = next((m for m in installed if m.get('name') == name), None)
        if entry is None or not entry.get('digest'):
            raise RuntimeError(f'Modelo não disponível no Ollama: {name}')
        return entry['digest']

    files = ['data/chunks/legislacao/chunks_A_artigo.json',
        'data/chunks/legislacao/chunks_D_paragrafo_completo.json',
        'src/rag/workflow_07.py', 'src/rag/presentation_07.py',
        'src/storage/pgvector_store.py', 'src/storage/parent_documents.py',
        'data/evaluation/legislacao/teste_congelado.json']
    hashes = {p: digest((root / p).read_bytes()) for p in files}
    if hashes[files[0]] != parents['parents_sha256'] or hashes[files[1]] != parents['children_sha256']:
        raise ValueError('Chunks alterados desde a recuperação; não congelar configuração inconsistente.')
    payload = {
        'schema_version': 1,
        'modelo_gerador': {'nome': budget['modelo_ollama'], 'digest': model_digest(budget['modelo_ollama']),
            'options': {'temperature': 0, 'seed': 42, 'num_ctx': budget['num_ctx'], 'num_predict': budget['num_predict']},
            'raw': True, 'stream': False},
        'prompt': {'system': prompt, 'sha256': digest(prompt.encode('utf-8')),
            'codigo_formatacao': nb07['prompt_juridico']},
        'orcamento': {k: budget[k] for k in ('tokenizador', 'num_ctx', 'num_predict', 'margem_tokens', 'limite_entrada')},
        'recuperacao': {k: config[k] for k in ('PIPELINE_VERSION', 'CHUNK_STRATEGY', 'SEARCH_BACKEND',
            'EMBEDDING_MODEL', 'RERANK_MODEL', 'RERANK_MAX_LENGTH', 'RERANK_CANDIDATES',
            'CANDIDATE_DEPTH', 'RRF_K', 'PARENT_TOP_K')},
        'embeddings': {'saida': 'dense', 'dimensao': 1024, 'normalizacao_l2': True,
            'similaridade_pgvector': 'cosine', 'recalcular_corpus': False},
        'hyde': {'modelo': config['OLLAMA_MODEL'], 'digest': model_digest(config['OLLAMA_MODEL']),
            'prompt': hyde_prompt, 'options': {'temperature': config['HYDE_TEMPERATURE'],
                'seed': 42, 'num_ctx': 4096, 'num_predict': 512}, 'evidencia': False},
        'sql_datasets': retrieval['sql_datasets'],
        'arquivos_sha256': hashes,
        'codigo_06': {k: nb06[k] for k in ('config_hyde', 'fontes_code', 'hyde_code', 'rerank_code')},
        'codigo_07': {k: nb07[k] for k in ('ambiente_rag', 'prompt_juridico', 'cliente_ollama')},
        'politica_teste': {'ajustar_prompt_com_teste': False, 'fornecer_gabarito_ao_modelo': False,
            'respostas_corrigidas_sao_referencias_dev': True,
            'instrucao_08': 'Carregar este arquivo e validar hashes e digests antes do teste; interromper se divergirem.'}}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    identity = digest(serialized)
    destination = root / 'reports/legislacao/integracao_rag/configuracao_congelada'
    destination.mkdir(parents=True, exist_ok=True)
    version = destination / f'configuracao_07_{identity}.json'
    if not version.exists():
        version.write_text(json.dumps({'configuracao_sha256': identity,
            'congelado_em_utc': datetime.now(timezone.utc).isoformat(), 'configuracao': payload},
            ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    pointer = destination / 'configuracao_ativa.json'
    if pointer.exists():
        previous = json.loads(pointer.read_text(encoding='utf-8'))
        if previous['configuracao_sha256'] != identity:
            raise RuntimeError('Há configuração ativa diferente. Nova versão arquivada; não substituí o congelamento anterior.')
    pointer.write_text(json.dumps({'arquivo': version.name, 'configuracao_sha256': identity}, indent=2) + '\n', encoding='utf-8')
    return {'arquivo': str(version.relative_to(root)), 'configuracao_sha256': identity,
        'modelo': budget['modelo_ollama'], 'estrategia': 'D → RRF + reranking → A',
        'status': 'Configuração final congelada com sucesso',
        'escopo_deste_registro': 'Somente a célula de congelamento; não representa o histórico de execução do projeto.',
        'avaliacao_final_08': 'Não executada por esta célula; etapa separada no notebook 08.',
        'respostas_existentes': 'Preservadas; esta célula não gera nem substitui respostas.',
        'revisoes_existentes': 'Preservadas; o congelamento não altera decisões de revisão.',
        'embeddings_existentes': 'Preservados para reutilização, sem recálculo nesta célula.'}
