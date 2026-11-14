"""Persiste revisões de novas versões sem reescrever saídas brutas do modelo."""
import re
import json
from pathlib import Path
from datetime import datetime, timezone

from .workflow_07 import read_json, write_json, text_hash, review_status


def source_hash(generated):
    return text_hash(json.dumps(generated.get('sources',[]),ensure_ascii=False,sort_keys=True,default=str))


def parse_generated_cell(text, generated, reviewer=None):
    match=re.search(r'\*\*Revisão jurídica desta nova versão:\*\*\s*([^\n]+)',text,re.I)
    declared=match.group(1).strip() if match else 'pendente'
    marker=re.search(r'\*\*Nova resposta do modelo:?\*\*\s*:?[ \t]*',text,re.I)
    body=''
    if marker:
        body=text[marker.end():].split('**Fontes efetivamente entregues nesta execução**',1)[0].strip()
    original=generated.get('resposta','')
    prefix=suffix=''
    if original and original in body:
        prefix,_,suffix=body.partition(original)
        prefix,suffix=prefix.strip(),suffix.strip()
        changed=bool(prefix or suffix)
        original_present=True
    else:
        changed=bool(body and body!=original.strip())
        original_present=False
    explicit_reviewer=re.search(r'\bpor\s+([^\.\n]+)',declared,re.I)
    original_decision=re.search(r'\*\*Revisão da saída original do modelo:\*\*\s*([^\n]+)',text,re.I)
    classification=re.search(r'\*\*Classificação do erro:\*\*\s*([^\n]+)',text,re.I)
    reason=re.search(r'\*\*Motivo da reprovação:\*\*\s*([^\n]+)',text,re.I)
    result={'status_revisao':review_status(declared),'decisao_original':declared,
        'revisor':explicit_reviewer.group(1).strip() if explicit_reviewer else reviewer,
        'origem_revisor':'celula' if explicit_reviewer else 'declaracao_na_sessao' if reviewer else None,
        'resposta_modelo_original':original, 'texto_resposta_na_celula':body,
        'texto_acrescentado_antes_da_resposta':prefix,
        'texto_acrescentado_depois_da_resposta':suffix,
        'texto_substituido_ou_editado':body if changed and not original_present else '',
        'resposta_modelo_original_presente':original_present,
        'celula_tem_edicoes_na_resposta':changed,
        'escopo_status':'versao_exibida_na_celula_com_edicoes' if changed else 'resposta_modelo_sem_edicoes',
        'status_revisao_modelo_original':review_status(declared) if not changed else 'nao_inferido_de_celula_editada',
        'origem_dos_acrescimos':'texto_inserido_na_revisao; autoria_modelo_nao_inferida' if changed else None,
        'resposta_modelo_sha256':text_hash(original), 'texto_exibido_sha256':text_hash(body),
        'celula_markdown_original':text, 'celula_sha256':text_hash(text),
        'data_revisao':None}
    if original_decision:
        result['status_revisao_modelo_original']=review_status(original_decision.group(1))
        result['decisao_explicita_sobre_saida_original']=original_decision.group(1).strip()
        result['escopo_status']='decisao_explicita_sobre_saida_original_modelo'
    if classification:
        result['classificacao_erro']=classification.group(1).strip()
    if reason:
        result['motivo_reprovacao']=reason.group(1).strip()
    if result['status_revisao'] not in ('aprovada_por_revisor','reprovada'):
        result['revisor']=None
        result['origem_revisor']=None
    return result


def persist_generated_reviews(root, reviewer=None):
    import pandas as pd
    root=Path(root)
    report=root/'reports/legislacao/integracao_rag'
    nb=read_json(root/'notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb')
    groups={'correcao':read_json(report/'correcoes/respostas_corrigidas_dev.json'),
        'variante':read_json(report/'variantes/respostas_variantes_rag.json')}
    history_dir=report/'revisoes/novas/historico'
    historical=[]
    if history_dir.exists():
        for path in sorted(history_dir.glob('*.json')):
            entry=read_json(path)
            body=entry.get('texto_resposta_na_celula','')
            raw=entry.get('resposta_modelo_original','')
            # Descarta vínculos históricos inconsistentes, mas não apaga seus arquivos.
            if raw and raw in body:
                historical.append(entry)
    records, versions=[], []
    for kind, generated_rows in groups.items():
        revised_rows=[]
        for result in generated_rows:
            base='novas_respostas_07_'+kind+'_'+result['query_id']
            candidates=[c for c in nb['cells'] if c.get('id')==base or c.get('id','').startswith(base+'_')]
            per_query=[]
            old_versions=[h for h in historical if h.get('tipo')==kind and h.get('query_id')==result['query_id']]
            for cell in candidates:
                text=''.join(cell['source'])
                parsed_current=parse_generated_cell(text,result,reviewer)
                body=parsed_current['texto_resposta_na_celula']
                old_matches=[h for h in old_versions if h['resposta_modelo_original'] in body]
                exact_old=[h for h in old_matches if h.get('celula_sha256')==text_hash(text)]
                declared_hash=cell.get('metadata',{}).get('response_sha256')
                declared_old=[h for h in old_matches if h.get('resposta_modelo_sha256')==declared_hash]
                current_history=[h for h in old_matches if h.get('resposta_modelo_sha256')==text_hash(result.get('resposta',''))
                    and h.get('contexto_fontes_sha256')==source_hash(result)
                    and h.get('pergunta_sha256')==text_hash(result['pergunta'])]
                previous=(current_history or exact_old or declared_old or sorted(old_matches,key=lambda h:len(h['resposta_modelo_original'])) or [None])[-1]
                current_present=bool(result.get('resposta') and result['resposta'] in body)
                # Uma recusa de escopo pura não contém conclusão jurídica nem usa fontes.
                # A decisão explícita sobre o mesmo texto/pergunta não depende do contexto.
                same_scope_refusal=(current_present and body.strip()==result['resposta'].strip()
                    and body.strip().rstrip('.')=='Essa não é uma pergunta ligada ao Direito do Trabalho'
                    and result['pergunta'] in text)
                # O nome da pergunta sozinho nunca autoriza transferir uma revisão.
                if previous and not same_scope_refusal and (not current_present or
                        (exact_old and previous.get('contexto_fontes_sha256')!=source_hash(result))):
                    historical_result={'resposta':previous['resposta_modelo_original'],
                        'pergunta':previous.get('pergunta',result['pergunta'])}
                    review=parse_generated_cell(text,historical_result,reviewer)
                    context_hash=previous.get('contexto_fontes_sha256')
                    question_hash=previous.get('pergunta_sha256',text_hash(historical_result['pergunta']))
                    review['vinculo_geracao']='historico_confirmado_por_texto'
                elif current_present:
                    review=parsed_current
                    context_hash=source_hash(result)
                    question_hash=text_hash(result['pergunta'])
                    review['vinculo_geracao']='saida_atual_confirmada_por_texto'
                    if same_scope_refusal:
                        review['vinculo_geracao']='recusa_de_escopo_identica_mesma_pergunta_sem_afirmacao_juridica'
                else:
                    review=parse_generated_cell(text,{'resposta':''},reviewer)
                    context_hash=None
                    question_hash=text_hash(result['pergunta'])
                    review['vinculo_geracao']='texto_editado_sem_saida_bruta_identificada'
                    review['status_revisao_modelo_original']='nao_inferido_de_celula_editada'
                review.update(query_id=result['query_id'],tipo=kind,celula_id=cell['id'],celula_ausente=False,
                    pergunta=result['pergunta'],pergunta_sha256=question_hash,contexto_fontes_sha256=context_hash,
                    status_execucao='concluida',exportado_em_utc=datetime.now(timezone.utc).isoformat())
                if review.get('revisor') is None and previous and previous.get('celula_sha256')==review['celula_sha256']:
                    review['revisor']=previous.get('revisor')
                    review['origem_revisor']=previous.get('origem_revisor')
                per_query.append(review)
                versions.append(review)
                version_key=text_hash(str((review['resposta_modelo_sha256'],context_hash,review['celula_sha256'])))
                history=history_dir/f"{kind}_{result['query_id']}_{version_key}.json"
                if not history.exists():
                    write_json(history,review)
            eligible=[review for review in per_query if review['resposta_modelo_sha256']==text_hash(result.get('resposta',''))
                and review['contexto_fontes_sha256']==source_hash(result) and review['pergunta_sha256']==text_hash(result['pergunta'])]
            decided=[review for review in eligible if review['status_revisao'] in ('aprovada_por_revisor','reprovada')]
            if eligible:
                review=dict((decided or eligible)[-1])
            else:
                review={'query_id':result['query_id'],'tipo':kind,
                    'status_revisao':'falha_tecnica_sem_resposta' if result['status_execucao']=='falha' else 'sem_anotacao_local',
                    'celula_ausente':not bool(candidates),'revisor':None,
                    'escopo_status':'sem_resposta_concluida' if result['status_execucao']=='falha' else 'ultima_saida_sem_revisao_correspondente',
                    'resposta_modelo_original':result.get('resposta',''),
                    'resposta_modelo_sha256':text_hash(result.get('resposta','')),
                    'texto_resposta_na_celula':'','celula_tem_edicoes_na_resposta':False,
                    'pergunta':result['pergunta'],'pergunta_sha256':text_hash(result['pergunta']),
                    'contexto_fontes_sha256':source_hash(result)}
            review['status_execucao']=result['status_execucao']
            write_json(report/'revisoes/novas'/f"{kind}_{result['query_id']}.json",review)
            records.append(review)
            revised_rows.append({**result,'status_revisao':review['status_revisao'],
                'revisao_juridica':review['status_revisao'],'revisor':review['revisor'],
                'revisao_local':review,'resposta_exibida_revisada':review['texto_resposta_na_celula']})
        destination=(report/'correcoes/respostas_corrigidas_dev_revisadas.json' if kind=='correcao'
                     else report/'variantes/respostas_variantes_revisadas.json')
        write_json(destination,revised_rows)
    write_json(report/'revisoes_todas_versoes.json',versions)
    curated=[v for v in versions if v['status_revisao'] in ('aprovada_por_revisor','reprovada')]
    write_json(report/'revisoes_versoes_revisadas.json',curated)
    write_json(report/'revisoes_novas_respostas.json',records)
    columns=['tipo','query_id','status_execucao','status_revisao','revisor','escopo_status',
        'celula_tem_edicoes_na_resposta','resposta_modelo_original','texto_resposta_na_celula',
        'texto_acrescentado_antes_da_resposta','texto_acrescentado_depois_da_resposta','resposta_modelo_sha256','celula_sha256']
    pd.DataFrame([{k:r.get(k) for k in columns} for r in records]).to_csv(report/'revisoes_novas_respostas.csv',index=False)
    pd.DataFrame([{k:r.get(k) for k in columns} for r in curated]).to_csv(report/'revisoes_versoes_revisadas.csv',index=False)
    return records


def matching_review(root, kind, result):
    path=Path(root)/'reports/legislacao/integracao_rag/revisoes_novas_respostas.json'
    if not path.is_file():
        return None
    kind={'correcao_assistida':'correcao','variante_rag':'variante'}.get(kind,kind)
    return next((review for review in read_json(path) if review['tipo']==kind and
        review['query_id']==result['query_id'] and
        review['resposta_modelo_sha256']==text_hash(result.get('resposta','')) and
        review.get('pergunta_sha256')==text_hash(result['pergunta']) and
        review.get('contexto_fontes_sha256')==source_hash(result)),None)


def version_status_table(root):
    import pandas as pd
    report=Path(root)/'reports/legislacao/integracao_rag'
    curated=read_json(report/'revisoes_versoes_revisadas.json')
    current=read_json(report/'revisoes_novas_respostas.json')
    rows=[]
    for latest in current:
        previous=[r for r in curated if r['query_id']==latest['query_id'] and r['tipo']==latest['tipo']]
        rows.append({'tipo':latest['tipo'],'query_id':latest['query_id'],
            'decisao_preservada_da_versao_revisada':'; '.join(dict.fromkeys(r['status_revisao'] for r in previous)) or 'sem revisão anterior',
            'status_da_ultima_execucao':latest['status_revisao'],
            'mesmo_texto_e_fontes_de_versao_revisada':any(r['resposta_modelo_sha256']==latest['resposta_modelo_sha256']
                and r.get('contexto_fontes_sha256')==latest.get('contexto_fontes_sha256') for r in previous)})
    return pd.DataFrame(rows)
