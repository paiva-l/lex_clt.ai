"""Gera credenciais locais para o Compose, sem imprimir senhas."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
env_path = root / '.env.pgvector.local'
existing = env_path.read_text(encoding='utf-8-sig') if env_path.is_file() else ''
for line in existing.splitlines():
    key, separator, value = line.strip().partition('=')
    if separator and key == 'DATABASE_URL' and value.strip().strip('"\''):
        raise SystemExit('Conexão já preenchida; nenhuma credencial foi substituída.')

password = secrets.token_urlsafe(32)
content = (
    '# Configuração privada local. Não versionar nem compartilhar este arquivo.\n'
    'POSTGRES_DB=lex_clt\n'
    'POSTGRES_USER=lex_clt\n'
    f'POSTGRES_PASSWORD={password}\n'
    'PGVECTOR_PORT=15432\n'
    f'DATABASE_URL=postgresql://lex_clt:{password}@127.0.0.1:15432/lex_clt?sslmode=disable\n'
)
env_path.write_text(content, encoding='utf-8')
print('Credenciais locais configuradas em .env.pgvector.local. Senha não exibida.')
