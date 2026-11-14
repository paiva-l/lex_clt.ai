"""Acrescenta e executa somente o congelamento da configuração final."""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from src.rag.frozen_config_07 import freeze_configuration

path = root / 'notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb'
raw = path.read_bytes()
nb = json.loads(raw)
backup = root / 'reports/legislacao/integracao_rag/historico' / ('07_antes_congelamento_' + hashlib.sha256(raw).hexdigest() + '.ipynb')
backup.parent.mkdir(parents=True, exist_ok=True)
if not backup.exists():
    backup.write_bytes(raw)
result = freeze_configuration(root)
code = '''from pathlib import Path
import importlib
import json
import sys

FREEZE_ROOT = next((base for base in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
    if (base / 'src/rag/frozen_config_07.py').is_file()), None)
if FREEZE_ROOT is None:
    raise FileNotFoundError('Módulo de congelamento não encontrado na raiz do projeto.')
if str(FREEZE_ROOT) not in sys.path:
    sys.path.insert(0, str(FREEZE_ROOT))
import src.rag.frozen_config_07 as freeze_module
importlib.reload(freeze_module)

frozen_configuration_07 = freeze_module.freeze_configuration(FREEZE_ROOT)
print(json.dumps(frozen_configuration_07, ensure_ascii=False, indent=2))
print('O 08 deverá carregar a configuração congelada e validar suas identidades antes de executar o teste.')
print('Sem geração, recuperação, recálculo de embeddings ou leitura das perguntas de teste nesta célula.')
'''
compile(code, 'congelamento_final_07', 'exec')
ids = {'congelamento_final_07_md', 'congelamento_final_07'}
existing = [c for c in nb['cells'] if c.get('id') not in ids]
nb['cells'] = existing + [
    {'id': 'congelamento_final_07_md', 'cell_type': 'markdown', 'metadata': {},
     'source': ['## Configuração final congelada para avaliação no 08\n', '\n',
         'Registra o modelo instalado (digest), prompt completo, HyDE, recuperação D → A, parâmetros, orçamento e hashes dos arquivos. A versão é identificada por SHA-256 e não substitui silenciosamente uma configuração ativa diferente. As respostas revisadas permanecem referências de desenvolvimento, sem fornecer gabaritos ao modelo no teste. Este registro não representa aprovação jurídica das respostas.\n']},
    {'id': 'congelamento_final_07', 'cell_type': 'code', 'metadata': {},
     'source': code.splitlines(keepends=True), 'execution_count': None,
     'outputs': [{'output_type': 'stream', 'name': 'stdout', 'text': [json.dumps(result, ensure_ascii=False, indent=2) + '\n',
         'Configuração congelada. Nenhuma geração, busca ou pergunta de teste executada.\n']}]}]
assert nb['cells'][:-2] == existing
path.write_text(json.dumps(nb, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
