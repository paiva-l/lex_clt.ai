import ast
import json
from pathlib import Path
import sys
import hashlib
import re
import math
from numbers import Real
import io
import contextlib
import base64
import numpy as np
import pandas as pd
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from src.storage.parent_documents import expand_parent_documents, format_parent_context
PROJECT_ROOT = root
REPORT_DIR = root / 'reports/legislacao/recuperacao/D_para_A_ollama_hyde_rrf_reranking'
PARENT_TOP_K = 3
df_dev = pd.read_json(root / 'data/evaluation/legislacao/eval_dataset_dev_aprovado.json')
df_refs = pd.read_json(root / 'data/evaluation/legislacao/referencias_aprovadas.json')
articles = pd.read_json(root / 'data/processed/legislacao/legislacao_artigos_completos.json')
article_lookup = articles.set_index('artigo_id').to_dict('index')
df_ranking = pd.read_json(REPORT_DIR / 'rankings_dev.json')
parents_by_article = {item['artigo_id']: item for item in json.loads(
    (root / 'data/chunks/legislacao/chunks_A_artigo.json').read_text(encoding='utf-8'))}
children_by_id = {item['chunk_id']: item for item in json.loads(
    (root / 'data/chunks/legislacao/chunks_D_paragrafo_completo.json').read_text(encoding='utf-8'))}
def display(value):
    print(value.to_string())
def ollama_json(endpoint, payload):
    request = Request('http://127.0.0.1:11434' + endpoint,
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=60) as response:
        return json.load(response)

nb = json.loads((root / 'notebooks/06_experimentos_recuperacao.ipynb').read_text(encoding='utf-8'))
for cell in nb['cells']:
    if cell['id'] == 'config_hyde':
        nodes = [node for node in ast.parse(''.join(cell['source'])).body
                 if isinstance(node, ast.FunctionDef) and node.name == 'numeric_value']
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'numeric_value', 'exec'))
    if cell['id'] == 'avaliacao_code':
        nodes = [node for node in ast.parse(''.join(cell['source'])).body
                 if isinstance(node, ast.FunctionDef) and node.name == 'literal_evidence_coverage']
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'coverage', 'exec'))
import matplotlib
matplotlib.use('Agg')
code = next(''.join(cell['source']) for cell in nb['cells']
            if cell['id'] == 'comparacao_contexto_orcamento_llm')
captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    exec(compile(code, 'comparacao_contexto_orcamento_llm', 'exec'))
assert df_context_comparison.tokens_prompt_llm.max() > 100
assert all(item['prompt_tokens'] <= FINAL_INPUT_LIMIT for item in budget_contexts)
for cell in nb['cells']:
    if cell['id'] == 'comparacao_contexto_orcamento_llm':
        cell['outputs'] = [
            {'output_type': 'stream', 'name': 'stdout', 'text': captured.getvalue().splitlines(keepends=True)},
            {'output_type': 'display_data', 'metadata': {}, 'data': {'image/png': base64.b64encode(
                (REPORT_DIR / 'comparacao_contexto_D_para_A.png').read_bytes()).decode('ascii')}}]
(root / 'notebooks/06_experimentos_recuperacao.ipynb').write_text(
    json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(captured.getvalue())
