"""Busca em filhos D e expansão íntegra para pais A, sem usar textos HyDE como fontes."""
from __future__ import annotations


def expand_parent_documents(ranked_children, children_by_id, parents_by_article,
                            top_k=3, token_budget=None, count_tokens=None):
    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError('top_k deve ser inteiro positivo.')
    if token_budget is not None and (token_budget < 1 or count_tokens is None):
        raise ValueError('Um orçamento exige limite positivo e contador do tokenizador do LLM.')
    grouped = {}
    for rank, result in enumerate(ranked_children, 1):
        chunk_id = result['chunk_id']
        if chunk_id not in children_by_id:
            raise ValueError(f'Filho desconhecido: {chunk_id}')
        child = children_by_id[chunk_id]
        article_id = child['artigo_id']
        if child.get('estrategia') != 'D_paragrafo_completo' or article_id not in parents_by_article:
            raise ValueError('Filho D ou artigo pai A não encontrado.')
        parent = parents_by_article[article_id]
        start, end = int(child['inicio_no_artigo']), int(child['fim_no_artigo'])
        if (parent.get('estrategia') != 'A_artigo' or
                child['caminho_relativo'] != parent['caminho_relativo'] or
                child['sha256_fonte'] != parent['sha256_fonte'] or
                not 0 <= start < end <= len(parent['corpo_chunk']) or
                child['corpo_chunk'] != parent['corpo_chunk'][start:end]):
            raise ValueError('Filho e pai não correspondem à mesma fonte ou ao mesmo texto.')
        group = grouped.setdefault(article_id, {'best_rank': rank, 'matches': []})
        if not any(item['chunk_id'] == chunk_id for item in group['matches']):
            group['matches'].append({'chunk_id': chunk_id, 'rank': rank, 'score': result.get('score')})

    sources = []
    omitted = []
    # A ordem de inserção corresponde ao melhor filho de cada artigo.
    for article_id, group in grouped.items():
        parent = parents_by_article[article_id]
        if len(sources) >= top_k:
            omitted.append({'artigo_id': article_id, 'reason': 'limite_de_artigos'})
            continue
        source = dict(parent)
        source.update({'retrieval_strategy': 'D_para_A', 'retrieval_matches': group['matches'],
                       'best_child_rank': group['best_rank'], 'source_id': f'Fonte {len(sources)+1}'})
        candidate = sources + [source]
        if token_budget is not None and count_tokens(format_parent_context(candidate)) > token_budget:
            omitted.append({'artigo_id': article_id, 'reason': 'orcamento_contexto_artigo_integral'})
            continue
        sources.append(source)
    return sources, omitted


def format_parent_context(sources):
    """Mede o contexto entregue, com identificadores e artigos completos."""
    return '\n\n'.join(f"[{source['source_id']}]\n{source['conteudo_chunk']}" for source in sources)
