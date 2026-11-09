# Execução e reprodução do RAG

## Preparar o ambiente

Use Python 3.14 (versão declarada nos notebooks). Crie e ative um ambiente virtual e instale as dependências:

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
```

Instale Docker Desktop e Ollama separadamente. A configuração congelada identifica os modelos, opções, digests e hashes usados no experimento; nomes iguais de modelos não garantem digests iguais. Os modelos BGE-M3, reranker e o tokenizador Qwen devem estar disponíveis no cache local: o fluxo não os baixa implicitamente.

## Banco e dados

Siga [PostgreSQL e pgvector](pgvector.md) para preparar as credenciais locais, iniciar o PostgreSQL e importar os embeddings existentes. O banco e os pesos dos modelos não estão no Git. Os JSON de artigos e chunks necessários à configuração congelada foram preservados com seus bytes originais. Os demais dados podem ser reconstruídos pelos notebooks 01 a 06 a partir da origem descrita em [data/README.md](../data/README.md).

O importador reutiliza caches .npy, que não são distribuídos aqui. Quem não possui esses caches precisa executar a preparação de embeddings no notebook 06, com os modelos e a base corretos, antes da importação. Os manifestos publicados são evidências da execução original; não comprovam a existência do banco na máquina de quem clonou o projeto.

## Notebooks e avaliação

Execute os notebooks na ordem 01 a 08 para reconstruir o fluxo. O notebook 07 integra o RAG e registra revisões; o 08 verifica a configuração congelada e avalia o teste. No 08, RUN_FINAL_TEST = True pode executar geração real. Para consultar resultados salvos sem gerar novas respostas, use RUN_FINAL_TEST = False na célula de configuração.

Os arquivos em reports/legislacao/integracao_rag/configuracao_congelada/ e reports/legislacao/avaliacao_final/ registram configuração, respostas, métricas e revisão. Não altere hashes para contornar incompatibilidades: identifique a versão divergente. Ajustes após a avaliação exigem uma nova versão; se utilizarem o teste ou suas correções, a nova avaliação precisa de um conjunto independente.

## Verificação

```powershell
python -m unittest discover -s tests -v
```

Os testes locais não substituem a execução com PostgreSQL, modelos e Ollama configurados. Não versione .env.pgvector.local, senhas, .venv, caches, pesos ou volumes do banco.
