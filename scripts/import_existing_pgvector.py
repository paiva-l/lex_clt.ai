"""Valida/importa vetores existentes. Nunca recalcula embeddings."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.storage.pgvector_store import prepare_import, load_database_url, import_and_verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--strategy', choices=['A_artigo', 'D_paragrafo_completo'], default='A_artigo')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env.pgvector.local')
    args = parser.parse_args()
    report_dir = ROOT / 'reports/legislacao/pgvector'
    if args.strategy != 'A_artigo':
        report_dir = report_dir / args.strategy
    report_dir.mkdir(parents=True, exist_ok=True)
    chunks, vectors, mapping, manifest = prepare_import(ROOT, strategy=args.strategy)
    (report_dir / 'manifesto_importacao.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    with (report_dir / 'correspondencia_vetor_chunk.jsonl').open('w', encoding='utf-8') as handle:
        for item in mapping:
            handle.write(json.dumps(item, ensure_ascii=False) + '\n')
    result = {'status': 'validado_localmente', 'records_verified_locally': len(chunks),
              'embeddings_recomputed': False, 'dataset_id': manifest['dataset_id'],
              'checked_at': datetime.now(timezone.utc).isoformat()}
    (report_dir / 'validacao_local.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✅ Validação local: {len(chunks)} chunks ↔ {vectors.shape[0]} vetores de {vectors.shape[1]} dimensões.')
    if args.validate_only:
        print('• Somente validação local. Nenhuma conexão ou gravação no banco foi executada.')
        return
    url = load_database_url(args.env_file)
    result = import_and_verify(url, chunks, vectors, mapping, manifest)
    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    (report_dir / 'resultado_importacao.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Não imprime DSN, senha ou traceback que possa conter dados de conexão.
        if error.__class__.__module__.startswith('psycopg'):
            print(f'Falha PostgreSQL ({error.__class__.__name__}, SQLSTATE {getattr(error,"sqlstate",None)}). '
                  'Confira conexão, permissões e disponibilidade da extensão vector.', file=sys.stderr)
        else:
            print(str(error), file=sys.stderr)
        sys.exit(1)
