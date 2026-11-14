"""Executa apenas as células novas da integração e uma consulta livre real."""
import contextlib
import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from src.rag.workflow_07 import read_json, write_json
import IPython.display as ipdisplay

path=root/'notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb'
namespace={'__name__':'__main__'}
outputs=[]
def capture_display(value):
    if isinstance(value,ipdisplay.Markdown):
        data={'text/markdown':value.data,'text/plain':value.data}
    elif hasattr(value,'to_html') and hasattr(value,'to_string'):
        data={'text/html':value.to_html(index=False),'text/plain':value.to_string(index=False)}
    else:
        data={'text/plain':repr(value)}
    outputs.append({'output_type':'display_data','metadata':{},'data':data})

ipdisplay.display=capture_display
namespace['display']=capture_display
identifiers=['integracao_versoes_07_imports','integracao_versoes_07_inspecao','integracao_versoes_07_responder']

class Tee(io.StringIO):
    def write(self,text):
        sys.__stdout__.write(text)
        sys.__stdout__.flush()
        return super().write(text)

for identifier in identifiers:
    nb=read_json(path)
    cell=next(c for c in nb['cells'] if c['id']==identifier)
    print('Executando integração:',identifier,flush=True)
    outputs.clear()
    stream=Tee()
    with contextlib.redirect_stdout(stream):
        exec(compile(''.join(cell['source']),identifier,'exec'),namespace)
    cell['outputs']=[{'output_type':'stream','name':'stdout','text':stream.getvalue().splitlines(keepends=True)}]+list(outputs)
    cell['execution_count']=None
    current=read_json(path)
    current['cells']=[cell if c['id']==identifier else c for c in current['cells']]
    write_json(path,current)

print('Verificação concluída; nenhuma pergunta adicional executada.')
