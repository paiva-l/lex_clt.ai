"""Importa caches existentes e verifica o vínculo de cada vetor com seu chunk.

Este módulo não gera embeddings e não usa SentenceTransformer.encode().
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

MODEL = 'BAAI/bge-m3'
STRATEGY = 'A_artigo'
DIMENSIONS = 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def vector_hash(vector) -> str:
    if hasattr(vector, 'to_numpy'):
        vector = vector.to_numpy()
    return hashlib.sha256(np.ascontiguousarray(vector, dtype='<f4').tobytes()).hexdigest()


def prepare_import(root: Path, strategy: str = STRATEGY):
    """Valida o cache pela mesma chave usada no notebook, preservando a ordem."""
    if strategy not in {'A_artigo', 'D_paragrafo_completo'}:
        raise ValueError('Apenas as estratégias A e D são suportadas nesta importação.')
    chunk_path = root / 'data/chunks/legislacao' / f'chunks_{strategy}.json'
    chunk_sha = sha256_file(chunk_path)
    chunk_manifest_path = root / 'reports/legislacao/chunking/manifesto_chunking.json'
    chunk_manifest = json.loads(chunk_manifest_path.read_text(encoding='utf-8'))
    if strategy not in chunk_manifest['estrategias']:
        raise ValueError('Estratégia ausente no manifesto de chunking.')
    for name, expected in chunk_manifest['artefatos_entrada'].items():
        if sha256_file(root / 'data/processed/legislacao' / name) != expected:
            raise ValueError(f'Artefato estruturado alterado: {name}')

    # AutoConfig lê somente configuração local, sem baixar/carregar pesos.
    from transformers import AutoConfig
    model_config = AutoConfig.from_pretrained(MODEL, local_files_only=True).to_dict()
    model_config['dtype'] = 'float32'  # Configuração efetiva dos vetores originais.
    model_config['use_cache'] = False  # BGE-M3 como encoder no SentenceTransformer original.
    notebook_key = {'modelo': MODEL, 'config': model_config,
                    'max_seq_length': 8192, 'dados': chunk_sha}
    cache_key = hashlib.sha256(json.dumps(notebook_key, sort_keys=True, default=str).encode()).hexdigest()
    cache_path = root / 'indexes/legislacao/embeddings' / f'{cache_key}.npy'
    if not cache_path.is_file():
        raise FileNotFoundError('Cache BGE-M3 compatível não encontrado. Nenhum vetor foi recalculado. '
                                f'Chave esperada: {cache_key}')
    vectors = np.load(cache_path, mmap_mode='r', allow_pickle=False)
    chunks = json.loads(chunk_path.read_text(encoding='utf-8'))
    if not chunks or vectors.shape != (len(chunks), DIMENSIONS) or vectors.dtype != np.dtype('float32'):
        raise ValueError('Quantidade, dimensão ou dtype dos vetores incompatível com os chunks.')
    if not np.isfinite(vectors).all():
        raise ValueError('Vetores com NaN ou infinito.')
    if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-3):
        raise ValueError('Vetores não normalizados como esperado pelo notebook 06.')
    ids = [chunk['chunk_id'] for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError('IDs de chunks duplicados.')
    articles = json.loads((root / 'data/processed/legislacao/legislacao_artigos_completos.json').read_text(encoding='utf-8'))
    article_map = {article['artigo_id']: article for article in articles}
    if len(article_map) != len(articles) or set(c['artigo_id'] for c in chunks) != set(article_map):
        raise ValueError('A estratégia não cobre exatamente os artigos estruturados.')
    checked_sources = {}
    mapping = []
    for index, chunk in enumerate(chunks):
        if chunk.get('estrategia') != strategy or not isinstance(chunk.get('conteudo_chunk'), str):
            raise ValueError('Chunk sem texto ou com estratégia divergente.')
        relative = Path(chunk['caminho_relativo'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Caminho de origem inválido.')
        if str(relative) not in checked_sources:
            checked_sources[str(relative)] = sha256_file(root / 'data/raw/legislacao' / relative)
        if checked_sources[str(relative)] != chunk['sha256_fonte']:
            raise ValueError(f'Fonte bruta alterada: {relative}')
        article = article_map[chunk['artigo_id']]
        start, end = int(chunk['inicio_no_artigo']), int(chunk['fim_no_artigo'])
        if (chunk['caminho_relativo'] != article['caminho_relativo'] or
                not 0 <= start < end <= len(article['texto_artigo_completo']) or
                chunk['corpo_chunk'] != article['texto_artigo_completo'][start:end]):
            raise ValueError(f'Chunk não corresponde ao intervalo do artigo: {chunk["chunk_id"]}')
        if strategy == 'A_artigo' and (start != 0 or end != len(article['texto_artigo_completo'])):
            raise ValueError('Chunk A não contém o artigo completo.')
        mapping.append({'row_index': index, 'chunk_id': chunk['chunk_id'],
                        'article_id': chunk['artigo_id'],
                        'text_sha256': hashlib.sha256(chunk['conteudo_chunk'].encode()).hexdigest(),
                        'vector_sha256': vector_hash(vectors[index])})
    if strategy == 'D_paragrafo_completo':
        by_article = {}
        for chunk in chunks:
            by_article.setdefault(chunk['artigo_id'], []).append(chunk)
        for article_id, children in by_article.items():
            cursor = 0
            for child in sorted(children, key=lambda item: item['inicio_no_artigo']):
                if child['inicio_no_artigo'] != cursor:
                    raise ValueError('Lacuna ou sobreposição nos chunks D.')
                cursor = child['fim_no_artigo']
            if cursor != len(article_map[article_id]['texto_artigo_completo']):
                raise ValueError('Artigo incompleto na estratégia D.')
    manifest = {'model': MODEL, 'strategy': strategy, 'dimensions': DIMENSIONS,
                'chunk_count': len(chunks), 'cache_key': cache_key,
                'chunks_sha256': chunk_sha, 'vectors_sha256': sha256_file(cache_path),
                'ordered_mapping_sha256': json_hash(mapping),
                'model_config_sha256': json_hash(model_config),
                'correspondence': 'row i do cache corresponde ao chunk i do JSON cuja SHA-256 compõe a chave original',
                'embeddings_recomputed': False}
    manifest['dataset_id'] = json_hash(manifest)
    return chunks, vectors, mapping, manifest


def load_database_url(env_file: Path) -> str:
    """Lê apenas DATABASE_URL; não executa o arquivo nem expõe a credencial."""
    if os.environ.get('DATABASE_URL', '').strip():
        return os.environ['DATABASE_URL'].strip()
    if env_file.is_file():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            key, separator, value = line.strip().partition('=')
            if separator and key.strip() == 'DATABASE_URL':
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                if value:
                    return value
    raise ValueError('Preencha DATABASE_URL em .env.pgvector.local antes de importar. Não envie senhas no chat.')


DDL = '''
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS lex_clt;
CREATE TABLE IF NOT EXISTS lex_clt.vector_datasets (
    dataset_id text PRIMARY KEY,
    model text NOT NULL,
    strategy text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions = 1024),
    chunk_count integer NOT NULL,
    manifest jsonb NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lex_clt.chunk_embeddings (
    dataset_id text NOT NULL REFERENCES lex_clt.vector_datasets(dataset_id),
    chunk_id text NOT NULL,
    row_index integer NOT NULL CHECK (row_index >= 0),
    article_id text NOT NULL,
    source_path text NOT NULL,
    text_content text NOT NULL,
    text_sha256 text NOT NULL,
    vector_sha256 text NOT NULL,
    metadata jsonb NOT NULL,
    embedding vector(1024) NOT NULL,
    PRIMARY KEY (dataset_id, chunk_id),
    UNIQUE (dataset_id, row_index)
);
CREATE INDEX IF NOT EXISTS chunk_embeddings_article_idx
    ON lex_clt.chunk_embeddings(dataset_id, article_id);
'''


def verify_stored_row(stored, expected_index, chunks, mapping):
    """Rejeita troca de IDs, textos, metadados ou vetores na leitura do banco."""
    index, chunk_id, article_id, source_path, text, text_sha, vec_sha, metadata, vector = stored
    if index != expected_index or index >= len(chunks):
        raise ValueError('Ordem ou quantidade divergente na leitura do banco.')
    chunk, identity = chunks[index], mapping[index]
    expected_metadata = {key: value for key, value in chunk.items()
                         if key not in {'conteudo_chunk', 'corpo_chunk'}}
    if (chunk_id != chunk['chunk_id'] or article_id != chunk['artigo_id'] or
            source_path != chunk['caminho_relativo'] or text != chunk['conteudo_chunk'] or
            text_sha != identity['text_sha256'] or vec_sha != identity['vector_sha256'] or
            vector_hash(vector) != identity['vector_sha256'] or metadata != expected_metadata):
        raise ValueError(f'Correspondência vetor/chunk inválida no registro {index}. Transação revertida.')


def import_and_verify(database_url, chunks, vectors, mapping, manifest):
    """Importação idempotente e verificação integral, dentro da mesma transação."""
    import psycopg
    from psycopg.types.json import Jsonb
    from pgvector.psycopg import register_vector

    dataset_id = manifest['dataset_id']
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        with connection.cursor() as setup_cursor:
            setup_cursor.execute(DDL)
        # O cursor deve ser criado depois do registro dos adaptadores da conexão.
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (dataset_id,))
            cursor.execute('''INSERT INTO lex_clt.vector_datasets
                (dataset_id, model, strategy, dimensions, chunk_count, manifest)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (dataset_id) DO NOTHING''',
                (dataset_id, MODEL, manifest['strategy'], DIMENSIONS, len(chunks), Jsonb(manifest)))
            insert_sql = '''INSERT INTO lex_clt.chunk_embeddings
                (dataset_id, chunk_id, row_index, article_id, source_path, text_content,
                 text_sha256, vector_sha256, metadata, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (dataset_id, chunk_id) DO NOTHING'''
            for start in range(0, len(chunks), 256):
                rows = []
                for index in range(start, min(start + 256, len(chunks))):
                    chunk, identity = chunks[index], mapping[index]
                    metadata = {key: value for key, value in chunk.items()
                                if key not in {'conteudo_chunk', 'corpo_chunk'}}
                    rows.append((dataset_id, chunk['chunk_id'], index, chunk['artigo_id'],
                                 chunk['caminho_relativo'], chunk['conteudo_chunk'],
                                 identity['text_sha256'], identity['vector_sha256'],
                                 Jsonb(metadata), np.asarray(vectors[index], dtype=np.float32)))
                cursor.executemany(insert_sql, rows)
                print(f'• Importação: {min(start+256,len(chunks))}/{len(chunks)} registros', flush=True)

            cursor.execute('''SELECT row_index, chunk_id, article_id, source_path, text_content,
                text_sha256, vector_sha256, metadata, embedding
                FROM lex_clt.chunk_embeddings WHERE dataset_id=%s ORDER BY row_index''', (dataset_id,))
            verified = 0
            while batch := cursor.fetchmany(256):
                for stored in batch:
                    verify_stored_row(stored, verified, chunks, mapping)
                    verified += 1
            if verified != len(chunks):
                raise ValueError('Quantidade de registros importados divergente.')
            # Confere também a identidade do dataset preexistente, se houver.
            cursor.execute('SELECT manifest FROM lex_clt.vector_datasets WHERE dataset_id=%s', (dataset_id,))
            if cursor.fetchone()[0] != manifest:
                raise ValueError('Manifesto do banco diverge do conjunto local.')
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
            extension_version = cursor.fetchone()[0]
            # Consulta exata, sem índice aproximado. Compara scores com a referência NumPy.
            reference = np.asarray(vectors[0], dtype=np.float32)
            cursor.execute('''SELECT row_index, 1-(embedding <=> %s) AS score
                FROM lex_clt.chunk_embeddings WHERE dataset_id=%s
                ORDER BY embedding <=> %s, row_index LIMIT 5''', (reference, dataset_id, reference))
            matches = cursor.fetchall()
            for index, score in matches:
                expected_score = float(np.dot(vectors[index], reference) /
                                       (np.linalg.norm(vectors[index]) * np.linalg.norm(reference)))
                if not np.isclose(score, expected_score, atol=1e-5):
                    raise ValueError('Similaridade PostgreSQL diverge da referência NumPy.')
    # O contexto acima faz COMMIT somente após todas as verificações.
    return {'status': 'importado_e_verificado', 'dataset_id': dataset_id,
            'records_verified': verified, 'dimensions': DIMENSIONS,
            'pgvector_version': extension_version, 'embeddings_recomputed': False,
            'verification': 'Todos os IDs, textos, metadados e vetores float32 conferidos após leitura do banco.'}


def search_chunks(database_url, dataset_id, query_vector, top_k=50):
    """Busca exata por cosseno; consulta deve vir do mesmo modelo BGE-M3."""
    import psycopg
    from pgvector.psycopg import register_vector
    vector = np.asarray(query_vector, dtype=np.float32)
    if vector.shape != (DIMENSIONS,) or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
        raise ValueError('Vetor de consulta inválido.')
    if not isinstance(top_k, int) or not 1 <= top_k <= 1000:
        raise ValueError('top_k deve estar entre 1 e 1000.')
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.execute('SELECT model FROM lex_clt.vector_datasets WHERE dataset_id=%s', (dataset_id,))
            dataset = cursor.fetchone()
            if dataset is None or dataset[0] != MODEL:
                raise ValueError('Dataset BGE-M3 não encontrado.')
            cursor.execute('''SELECT chunk_id, text_content, metadata, 1-(embedding <=> %s) AS score
                FROM lex_clt.chunk_embeddings WHERE dataset_id=%s
                ORDER BY embedding <=> %s, row_index LIMIT %s''', (vector, dataset_id, vector, top_k))
            return [{'chunk_id': row[0], 'conteudo_chunk': row[1], 'metadata': row[2], 'score': row[3]}
                    for row in cursor.fetchall()]
