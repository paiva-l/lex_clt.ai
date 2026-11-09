# PostgreSQL e pgvector

A importação reutiliza os embeddings BGE-M3 da estratégia A. Não executa inferência, não baixa modelos e não recalcula os vetores.

## Banco local com Docker Desktop

O arquivo `compose.pgvector.yaml` cria PostgreSQL 17 com pgvector 0.8.7, volume persistente e porta acessível somente em `127.0.0.1:15432`.

Com Docker Desktop iniciado, a configuração inicial pode ser feita com:

```powershell
python scripts/configure_local_pgvector.py
docker compose --env-file .env.pgvector.local -f compose.pgvector.yaml up -d
```

O script gera uma senha aleatória, grava a conexão no arquivo ignorado pelo Git e não substitui uma conexão já preenchida. Após a inicialização, basta usar o importador abaixo. Não execute novamente o script para trocar senha de um volume já inicializado: a senha do PostgreSQL precisa ser alterada dentro do banco.

Para iniciar ou parar depois, preservando os dados:

```powershell
docker compose --env-file .env.pgvector.local -f compose.pgvector.yaml start
docker compose --env-file .env.pgvector.local -f compose.pgvector.yaml stop
```

O volume pertence ao Docker, não à pasta OneDrive do projeto. Não remova o volume se quiser preservar o banco. As credenciais locais de inicialização têm privilégios administrativos para criação das tabelas/extensão; uma aplicação publicada deve utilizar uma conta com permissões restritas.

## Conexão

Preencha `DATABASE_URL` em `.env.pgvector.local`, na raiz do projeto. O arquivo é ignorado pelo Git. Use os parâmetros SSL exigidos pelo seu servidor e faça URL encoding de caracteres especiais da senha. Não cole credenciais no notebook ou nos relatórios.

O banco deve existir e disponibilizar a extensão pgvector. A conta precisa de permissão para criar a extensão `vector` (ou ela deve ser habilitada pelo administrador), criar o schema `lex_clt` e inserir/consultar suas tabelas.

## Validação e importação

Execute no Python do mesmo ambiente dos notebooks:

```powershell
python -m pip install "psycopg[binary]" pgvector
python scripts/import_existing_pgvector.py --validate-only
python scripts/import_existing_pgvector.py
```

A chave do cache é reconstruída com a configuração local do BGE-M3 em float32, o hash do JSON dos chunks e o limite original de 8192 tokens. Não se escolhe um arquivo `.npy` apenas pelo número de linhas. A ordem do JSON é a mesma usada no notebook para codificar os textos.

São verificados os hashes dos artefatos e fontes, cobertura dos artigos, IDs únicos, dimensão, normalização, valores finitos e o vínculo entre a linha de cada vetor e seu chunk. O manifesto e a relação ordenada ficam em `reports/legislacao/pgvector/`.

## Tabelas e conferência

- `lex_clt.vector_datasets`: versão do conjunto, modelo, hashes e manifesto.
- `lex_clt.chunk_embeddings`: ID do chunk, posição no cache, artigo, origem, texto, metadados e coluna `vector(1024)`.

A importação é transacional e idempotente. Não remove tabelas nem substitui dados de outras versões. Todos os registros são lidos de volta e comparados, inclusive o hash dos bytes float32 dos vetores, antes do COMMIT. Uma falha reverte a transação. O arquivo `resultado_importacao.json` só é criado após sucesso no banco; validação local não significa importação concluída.

A busca inicial é exata por distância cosseno; não é criado índice aproximado. O resultado pode alimentar o RRF e o cross-encoder existentes. `search_chunks()` recebe um vetor de consulta BGE-M3 e devolve chunks com fontes; não gera embeddings automaticamente.

## Dependência dos notebooks

O notebook 06 continua com sua referência NumPy. A importação não muda os resultados dos experimentos. A integração da busca SQL deve comparar os rankings e usar o `dataset_id` importado explicitamente antes de substituir a referência.

## Fluxo parent-document D → A

O fluxo principal do notebook 06 passou a buscar os filhos D no PostgreSQL e a expandir para artigos A somente depois do cross-encoder. A referência NumPy permanece disponível por configuração, mas `SEARCH_BACKEND` é `pgvector` no fluxo principal.

A e D coexistem como datasets versionados, sem duplicar a identidade de versões. Para importar/revalidar D com o cache existente:

```powershell
python scripts/import_existing_pgvector.py --strategy D_paragrafo_completo
```

Os manifestos de D ficam em `reports/legislacao/pgvector/D_paragrafo_completo/`. A leitura verifica os intervalos e a cobertura de cada artigo. Nenhum vetor é recalculado.

`expand_parent_documents()` preserva a ordem do melhor filho, deduplica os pais por `artigo_id`, verifica origem/hash/texto e entrega o artigo A integral. O limite de tokens permanece sem valor por enquanto; ativá-lo exige o contador do tokenizador real do LLM. Um artigo que exceda o orçamento é omitido e registrado, nunca cortado silenciosamente.

A célula final do notebook 06 exporta `contextos_parent_A_dev.json` em `reports/legislacao/recuperacao/D_para_A_ollama_hyde_rrf_reranking/`. Esse arquivo é uma entrada de contexto para o notebook 07; não contém respostas geradas nem transforma HyDE em evidência.
