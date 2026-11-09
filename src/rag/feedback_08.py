"""Exporta saídas reais e feedback humano, preservando o histórico do teste."""
import json
from pathlib import Path
from .evaluation_08 import read, write, sha, output_folder, validate_frozen
from .review_08 import save_notebook_reviews


def export_feedback(root):
    root = Path(root)
    frozen = validate_frozen(root)
    folder = output_folder(root, frozen)
    reviews = save_notebook_reviews(root)
    results = read(folder / 'respostas_teste.json')
    by_id = {r['query_id']: r for r in reviews}
    records = []
    for result in results:
        if result['status_execucao'] != 'concluida':
            continue
        review = by_id[result['query_id']]
        if review['resposta_sha256'] != sha(result['resposta'].encode()):
            raise ValueError('A revisão não pertence à resposta real salva.')
        if not review['decisao'] or not review['revisor']:
            raise ValueError('Exporte o feedback depois de registrar decisão e revisor para todas as respostas.')
        correction = review['resposta_corrigida_revisora']
        flags = []
        if any(word in correction.casefold() for word in ('conferir', 'de memória', 'confirme', 'preciso que você confira')):
            flags.append('Texto da revisora contém pedidos de conferência; não tratar como gabarito validado.')
        if result['query_id'] == 'q_test_03' and '25%' in correction:
            flags.append('Conferência anterior identificou divergência na atribuição de 25% ao art. 73, § 3º; preservar como anotação da revisora.')
        if result['query_id'] == 'q_test_07' and 'de função' in correction:
            flags.append('Conferir a redação temporal do art. 457, § 1º; não misturar redações históricas.')
        records.append({'query_id': result['query_id'], 'split_origem': 'test',
            'configuracao_sha256': frozen['configuracao_sha256'],
            'pergunta': result['pergunta'], 'resposta_real_modelo': result['resposta'],
            'resposta_real_sha256': result['resposta_sha256'], 'fontes_entregues': result['sources'],
            'decisao_sobre_resposta_original': review['decisao'], 'revisor': review['revisor'],
            'avaliacao_humana_integral': review,
            'texto_final_informado_pela_revisora': correction,
            'texto_revisora_sha256': sha(correction.encode()),
            'natureza_texto_revisora': 'feedback e/ou proposta de resposta; não atribuído ao modelo',
            'alertas_curadoria': flags, 'destino': 'arquivo de feedback pós-teste',
            'elegivel_treinamento_automatico': False,
            'restricao': 'Se usado para ajustar o modelo, este conjunto deixa de ser teste cego para a nova versão.'})
    approved = sum(r['decisao_sobre_resposta_original'] == 'aprovada' for r in records)
    rejected = sum(r['decisao_sobre_resposta_original'] == 'reprovada' for r in records)
    serialized = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in records)
    identity = sha(serialized.encode())
    destination = root / 'data/evaluation/legislacao/feedback_pos_teste' / identity
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / 'respostas_reais_e_feedback.jsonl'
    if path.exists() and path.read_text(encoding='utf-8') != serialized:
        raise ValueError('Arquivo versionado de feedback divergiu.')
    if not path.exists():
        path.write_text(serialized, encoding='utf-8')
    summary = {'respostas_reais_salvas': len(records), 'revisoes_registradas': len(records),
        'aprovadas_pela_revisora': approved, 'reprovadas_pela_revisora': rejected,
        'proporcao_aprovada_pela_revisora': approved / len(records) if records else None,
        'interpretacao': 'Proporção das saídas originais aprovadas pela revisora; não certificação jurídica independente.',
        'textos_revisora_preservados': len(records),
        'casos_com_alerta_de_curadoria': [r['query_id'] for r in records if r['alertas_curadoria']],
        'modelo_treinado': False, 'respostas_regeneradas': False,
        'feedback_arquivo': str(path.relative_to(root)), 'feedback_sha256': identity}
    write(destination / 'manifesto_feedback.json', summary)
    write(folder / 'diagnostico_revisao_humana.json', summary)
    write(root / 'data/evaluation/legislacao/feedback_pos_teste/feedback_ativo.json', summary)
    return records, summary
