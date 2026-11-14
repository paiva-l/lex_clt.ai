"""Salva avaliações escritas nas células Markdown do teste, por versão de resposta."""
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from .evaluation_08 import read, write, sha, output_folder, validate_frozen

FIELDS = {
    'decisao': 'Decisão', 'suporte_fontes': 'Suporte nas fontes',
    'citacoes_corretas': 'Citações corretas', 'conduta_adequada': 'Conduta adequada',
    'recusa_adequada_se_aplicavel': 'Recusa adequada, quando aplicável',
    'motivo': 'Justificativa e observações', 'resposta_corrigida_revisora': 'Resposta corrigida pela revisora',
    'revisor': 'Revisor(a)'}


def parse_review(text):
    review = re.split(r'<!-- INICIO_AVALIACAO_(?:HUMANA_)?08 -->', text, maxsplit=1)[-1]
    values = {}
    for key, label in FIELDS.items():
        pattern = r'^\*\*' + re.escape(label) + r':\*\*[ \t]*(.*?)(?=\n\*\*(?:' + '|'.join(
            re.escape(v) for v in FIELDS.values()) + r'):\*\*|\Z)'
        match = re.search(pattern, review, flags=re.M | re.S)
        values[key] = match.group(1).strip() if match else ''
    decision = values['decisao'].strip().casefold().rstrip('.')
    if decision in ('aprovada', 'aprovado'):
        values['decisao'] = 'aprovada'
    elif decision in ('reprovada', 'reprovado'):
        values['decisao'] = 'reprovada'
    elif decision:
        raise ValueError('Use aprovada ou reprovada no campo Decisão.')
    return values


def save_notebook_reviews(root):
    root = Path(root)
    frozen = validate_frozen(root)
    folder = output_folder(root, frozen)
    results = {r['query_id']: r for r in read(folder / 'respostas_teste.json')}
    notebook_path = root / 'notebooks/01_legislacao/08_avaliacao_final_rag_legislacao.ipynb'
    raw = notebook_path.read_bytes()
    notebook = read(notebook_path)
    path = folder / 'revisao_juridica_teste.csv'
    previous = {}
    if path.exists():
        with path.open(encoding='utf-8', newline='') as stream:
            previous = {r['query_id']: r for r in csv.DictReader(stream)}
    rows = []
    for cell in notebook['cells']:
        if not cell.get('id', '').startswith('avaliacao_humana_08_') or cell['cell_type'] != 'markdown':
            continue
        query_id = cell['metadata']['query_id']
        result = results[query_id]
        text = ''.join(cell['source'])
        response = text.split('<!-- INICIO_RESPOSTA_ORIGINAL_08 -->\n', 1)[1].split('\n<!-- FIM_RESPOSTA_ORIGINAL_08 -->', 1)[0]
        if (sha(response.encode()) != result['resposta_sha256'] or
                cell['metadata']['configuracao_sha256'] != frozen['configuracao_sha256']):
            raise ValueError(f'{query_id}: preserve a resposta original; escreva ajustes no campo Resposta corrigida pela revisora.')
        values = parse_review(text)
        old = previous.get(query_id, {})
        same_version = (old.get('resposta_sha256') == result['resposta_sha256'] and
            old.get('configuracao_sha256') == frozen['configuracao_sha256'])
        merged = {key: value or (old.get(key, '') if same_version else '') for key, value in values.items()}
        if merged['decisao'] and not merged['revisor']:
            raise ValueError(f'{query_id}: preencha Revisor(a) para registrar a decisão.')
        rows.append({'query_id': query_id, 'resposta_sha256': result['resposta_sha256'],
            'configuracao_sha256': frozen['configuracao_sha256'],
            'escopo_decisao': 'resposta_original_do_modelo', **merged})
    if not rows:
        raise ValueError('Nenhuma célula de avaliação encontrada.')
    # Não apaga decisões do CSV que não tenham uma célula correspondente.
    present = {r['query_id'] for r in rows}
    rows.extend(r for q, r in previous.items() if q not in present)
    history = folder / 'revisoes_historico'
    history.mkdir(parents=True, exist_ok=True)
    snapshot = history / ('08_revisado_' + sha(raw) + '.ipynb')
    if not snapshot.exists():
        snapshot.write_bytes(raw)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
    write(folder / 'revisoes_humanas_teste.json', {'salvo_em_utc': datetime.now(timezone.utc).isoformat(),
        'configuracao_sha256': frozen['configuracao_sha256'], 'revisoes': rows,
        'correcoes_aplicadas_ao_modelo': False})
    return rows
