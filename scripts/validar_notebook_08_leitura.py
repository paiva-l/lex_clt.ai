"""Executa células do 08 em modo de leitura, sem geração."""
import hashlib
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import matplotlib
matplotlib.use('Agg')
import IPython.display
import matplotlib.pyplot as plt

path = root / 'notebooks/08_avaliacao_final_rag_legislacao.ipynb'
nb = json.loads(path.read_text(encoding='utf-8'))
protected = [root / 'notebooks/07_integracao_rag_legislacao.ipynb',
    root / 'data/evaluation/legislacao/eval_dataset_test_aprovado.json']
hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
namespace = {'__name__': '__main__'}
original_display = IPython.display.display
original_show = plt.show
try:
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        source = ''.join(cell['source'])
        if cell['id'] == 'configuracao_08':
            # Apenas esta execução usa leitura; preserva a opção salva pelo usuário.
            source = source.replace('RUN_FINAL_TEST = True', 'RUN_FINAL_TEST = False')
            if 'RUN_FINAL_TEST = False' not in source:
                raise RuntimeError('Validação exige modo de leitura explícito.')
        outputs = []
        def capture(value):
            if hasattr(value, 'savefig'):
                import base64
                from io import BytesIO
                buffer = BytesIO()
                value.savefig(buffer, format='png', dpi=150)
                data = {'image/png': base64.b64encode(buffer.getvalue()).decode()}
            elif hasattr(value, 'to_html'):
                data = {'text/html': value.to_html(), 'text/plain': value.to_string()}
            elif hasattr(value, 'data'):
                data = {'text/markdown': value.data, 'text/plain': value.data}
            else:
                data = {'text/plain': str(value)}
            outputs.append({'output_type': 'display_data', 'metadata': {}, 'data': data})
        IPython.display.display = capture
        plt.show = lambda: capture(plt.gcf())
        namespace['display'] = capture
        stream = StringIO()
        with redirect_stdout(stream):
            exec(compile(source, cell['id'], 'exec'), namespace)
        if stream.getvalue():
            outputs.append({'output_type': 'stream', 'name': 'stdout', 'text': stream.getvalue().splitlines(keepends=True)})
        cell['outputs'] = outputs
        cell['execution_count'] = None
finally:
    IPython.display.display = original_display
    plt.show = original_show
for p, expected in hashes.items():
    assert hashlib.sha256(p.read_bytes()).hexdigest() == expected
path.write_text(json.dumps(nb, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Todas as células do 08 executaram em modo de leitura. Nenhuma geração; 07 e teste preservados.')
