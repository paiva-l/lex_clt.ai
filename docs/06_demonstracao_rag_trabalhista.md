# 6 DEMONSTRAÇÃO

Esta seção demonstra o funcionamento do protótipo de RAG trabalhista a partir de uma consulta real registrada no notebook 08. A pergunta percorre o fluxo de recuperação implementado no projeto: busca nos chunks da estratégia D com a pergunta original e com o documento hipotético do HyDE, combinação dos rankings pelo Reciprocal Rank Fusion (RRF), reordenação por um cross-encoder e recuperação dos artigos completos da estratégia A. Esses artigos são enviados ao modelo de linguagem com identificadores de fonte e metadados de origem.

A demonstração utiliza a execução salva de `q_test_01`, sem realizar uma nova geração. O notebook [07 — Integração RAG](../notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb) apresenta a integração e o desenvolvimento do sistema; o notebook [08 — Avaliação final](../notebooks/01_legislacao/08_avaliacao_final_rag_legislacao.ipynb) registra o teste da configuração congelada e a revisão das respostas.

## 6.1 Consulta submetida ao sistema

A pergunta submetida foi:

> Que exigência o art. 60 da CLT estabelece para a prorrogação de jornada em atividades insalubres e que exceção registra?

O identificador `q_test_01` permite relacionar a pergunta à recuperação, à resposta original e à revisão humana. O objetivo desta consulta é verificar se o protótipo localiza o dispositivo solicitado e apresenta sua exigência e sua exceção com apoio no texto recuperado. A demonstração descreve o conteúdo da base utilizada no experimento; não constitui uma análise de aplicabilidade a um caso concreto.

## 6.2 Recuperação dos chunks e documentos mais relevantes

### Busca com a pergunta original e com o HyDE

A busca utiliza a estratégia `D_paragrafo_completo`, composta por chunks de parágrafos completos vinculados aos respectivos artigos. O modelo de embeddings `BAAI/bge-m3` transforma a pergunta original e o texto hipotético do HyDE em vetores densos de 1.024 dimensões, normalizados. Cada vetor é consultado no PostgreSQL com pgvector por similaridade de cosseno, recuperando até 50 candidatos por busca. Os embeddings existentes do corpus são reutilizados.

O HyDE é gerado pelo modelo `qwen3:4b-instruct` e funciona como uma consulta adicional. O texto salvo para esta pergunta começa assim:

> O tema aborda a exigência prevista no artigo 60 da Consolidação das Leis do Trabalho (CLT) sobre a prorrogação da jornada de trabalho em atividades insalubres, bem como a exceção que pode ser aplicada.

Esse é um trecho literal do documento hipotético registrado. O texto completo amplia a consulta com expressões relacionadas ao tema. Ele é sintético e serve exclusivamente à busca: não é uma fonte legislativa e não integra o conjunto de evidências entregue ao modelo como fundamentação.

### Combinação dos rankings e reordenação

Os dois rankings são combinados pelo RRF com parâmetro `k = 60`. A contribuição de cada resultado depende de sua posição em cada lista, conforme a expressão:

```text
RRF(documento) = soma de 1 / (60 + posição no ranking)
```

Após a fusão, até 50 candidatos seguem para o cross-encoder `BAAI/bge-reranker-v2-m3`. Ele avalia os pares formados pela pergunta original e pelo conteúdo dos candidatos e produz a ordenação utilizada na expansão para artigos completos. Nesta implementação, a fusão combina duas buscas vetoriais; não há busca BM25 nesse fluxo.

Os cinco primeiros resultados do ranking reordenado salvo para `q_test_01` foram:

| Posição | Identificador do chunk D | Score do reranker | Artigo associado |
| --- | --- | ---: | --- |
| 1 | `5907dc4ec14e5c91532ac68823c5815d1387a9d00dff1fc6d87800977a41fa4e` | 0,989132 | Art. 60 |
| 2 | `56fa0e767b230ec1455be1174090e1bf96ba59ded136d5f497e2615db45b9355` | 0,867056 | Art. 60 |
| 3 | `605c130c80446bb5d9f3223c78268f55ca06c5553f651989c91e8d7cd28059cd` | 0,711576 | Art. 61 |
| 4 | `42a95bed1d747fe5d29d6ac46c2301d1296e5ebf7e916a2ff89ee6b4715a1d81` | 0,540479 | Art. 61 |
| 5 | `6c1a02eb8d4ebcf6e0da85878e93cfb760d40f2a40af8bcf5cd79079624ba7d9` | 0,414830 | Art. 611-A |

Os scores são valores de ordenação do reranker, não percentuais de correção jurídica. O registro utilizado apresenta o ranking final em `ranking_d`; esta demonstração não atribui posições ou scores às listas anteriores à fusão, que não estão discriminadas nesse registro.

### Recuperação do artigo completo: D → A

A partir dos chunks D reordenados, o sistema identifica os artigos correspondentes na estratégia `A_artigo`. A expansão verifica a correspondência entre filho e pai, incluindo o identificador do artigo, o caminho da fonte, seu hash e o trecho textual. Chunks do mesmo artigo são agrupados, evitando enviar repetidamente o mesmo artigo ao modelo.

Nesta execução, os três artigos completos selecionados e efetivamente entregues foram:

| Identificador no contexto | Documento recuperado | Melhor posição de um chunk filho |
| --- | --- | ---: |
| Fonte 1 | CLT — Art. 60 | 1 |
| Fonte 2 | CLT — Art. 61 | 3 |
| Fonte 3 | CLT — Art. 611-A | 5 |

A configuração permite até três artigos. O orçamento é conferido com o prompt completo, incluindo instruções, pergunta e fontes. O limite de entrada é de 5.888 tokens, em uma janela de 8.192 tokens, com reserva de 2.048 para a saída e margem de 256 tokens. Artigos que excederiam o orçamento são omitidos integralmente, sem truncamento. Para esta consulta, a lista `omitted` está vazia: nenhum dos três artigos selecionados foi omitido por orçamento.

## 6.3 Resposta fundamentada no conteúdo recuperado

O modelo `qwen3:4b-instruct`, executado via Ollama, recebe a pergunta e os artigos completos identificados como fontes. O prompt orienta a responder com base nas evidências fornecidas, indicar os dispositivos e associar as afirmações aos identificadores presentes no contexto. Também orienta a explicitar a insuficiência de evidências quando necessário.

A resposta original salva contém o seguinte trecho de fundamentação:

> A exigência de licença prévia para prorrogação de jornada em atividades insalubres é prevista no **Art. 60 da CLT**, que diz: *"Nas atividades insalubres... quaisquer prorrogações só poderão ser acordadas mediante licença prévia das autoridades competentes em matéria de higiene do trabalho..."* [Fonte 1].

Ao apresentar a exceção, a mesma resposta registra:

> A exceção mencionada é expressa no **Parágrafo Único do Art. 60**, que afirma: *"Excetuam-se da exigência de licença prévia as jornadas de doze horas de trabalho por trinta e seis horas ininterruptas de descanso"* [Fonte 1].

Os trechos acima são reproduções da saída do modelo, não uma resposta reconstruída para esta documentação. Eles mostram a associação entre a explicação gerada e o artigo efetivamente recebido. A saída integral, incluindo as observações e limitações formuladas pelo modelo, permanece no notebook 08 e no arquivo de respostas do teste.

O registro indica execução `concluida`, 3.838 tokens de entrada e 686 tokens de saída, com `cache_hit = false` para a geração. A revisão humana registrada para a resposta original tem decisão `aprovada`. Essa decisão se refere a esta resposta no experimento e não certifica automaticamente a correção de outras respostas do sistema.

## 6.4 Evidência das fontes utilizadas na resposta

É possível distinguir os documentos entregues ao modelo daqueles explicitamente citados na saída. Os artigos 60, 61 e 611-A foram entregues como contexto, mas as citações dos trechos demonstrados apontam para a **Fonte 1 — Art. 60 da CLT**. A presença dos demais artigos no contexto não significa que todos tenham sido utilizados expressamente na fundamentação.

O texto recuperado da Fonte 1 contém tanto a exigência de licença prévia no caput quanto a exceção para a jornada de doze horas de trabalho por trinta e seis horas ininterruptas de descanso no parágrafo único. Assim, os dois pontos solicitados na pergunta podem ser conferidos diretamente no documento enviado ao modelo.

Os metadados preservados para essa fonte incluem:

| Campo | Valor registrado |
| --- | --- |
| Norma e dispositivo | CLT — Art. 60 |
| Identificador no prompt | `Fonte 1` |
| Arquivo no corpus | `codigos/consolidacao-das-leis-do-trabalho-clt-del-5452-1943.md` |
| Origem declarada | https://www.planalto.gov.br/ccivil_03/Decreto-Lei/Del5452compilado.htm |
| Integridade | Hash SHA-256 da fonte, identificador do artigo e identificadores dos chunks associados |

A URL é a origem declarada nos metadados da base utilizada; esta documentação não registra uma nova consulta à página nem uma atualização do texto legal. O vínculo entre chunks, artigo completo e fonte permite auditar a recuperação e confrontar a resposta com o contexto recebido.

## 6.5 Registros que sustentam a demonstração

A demonstração foi elaborada a partir dos seguintes arquivos do projeto:

- [Notebook 07 — Integração RAG](../notebooks/01_legislacao/07_integracao_rag_legislacao.ipynb).
- [Notebook 08 — Avaliação final e revisão humana](../notebooks/01_legislacao/08_avaliacao_final_rag_legislacao.ipynb).
- [Implementação da recuperação e integração](../src/rag/workflow_07.py), especialmente `VariantRetriever.retrieve`.
- [Expansão de chunks D para artigos A](../src/storage/parent_documents.py), pelas funções `expand_parent_documents` e `format_parent_context`.
- [Respostas reais do teste](../reports/legislacao/avaliacao_final/2318200177f97e4df627986194bbba9cdaecd7fe2bdd8354fe3293b725734f1e/respostas_teste.json), registro `q_test_01`.
- [Revisão jurídica registrada](../reports/legislacao/avaliacao_final/2318200177f97e4df627986194bbba9cdaecd7fe2bdd8354fe3293b725734f1e/revisao_juridica_teste.csv).
- [Configuração congelada do experimento](../reports/legislacao/integracao_rag/configuracao_congelada/configuracao_07_2318200177f97e4df627986194bbba9cdaecd7fe2bdd8354fe3293b725734f1e.json).

Os links para código e relatórios dependem da presença desses arquivos na cópia consultada do repositório; os principais dados do exemplo estão transcritos nesta seção para permitir sua leitura independente. A demonstração evidencia o percurso de uma consulta, a recuperação de documentos, a geração apoiada no contexto e a rastreabilidade das fontes. A qualidade geral do protótipo deve ser examinada no conjunto da avaliação do notebook 08, incluindo respostas reprovadas e limitações registradas.
