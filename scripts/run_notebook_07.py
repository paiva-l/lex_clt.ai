"""Executa as células do 07 e salva saídas reais, sem dependência de um kernel externo."""
import contextlib
import io
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
path = root / 'notebooks/07_integracao_rag_legislacao.ipynb'
nb = json.loads(path.read_text(encoding='utf-8'))
namespace = {'__name__':'__main__'}
namespace['display'] = lambda value: print(value.to_string() if hasattr(value,'to_string') else value)
count = 0
for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    print('Executando:', cell['id'], flush=True)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(''.join(cell['source']), cell['id'], 'exec'), namespace)
    count += 1
    cell['execution_count'] = count
    cell['outputs'] = [{'output_type':'stream', 'name':'stdout',
                        'text':output.getvalue().splitlines(keepends=True)}]
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print(output.getvalue(), flush=True)
