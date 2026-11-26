# 05 · Base de precedentes do TST

Terceira base do LexIA. Ela reúne súmulas, orientações jurisprudenciais (OJs) e temas de recursos repetitivos do TST, e fica separada das bases de legislação e de jurisprudência. O motivo está em `00_introducao_precedentes.ipynb`: anexados aos 20 mil acórdãos, os precedentes ficariam entre a 8ª e a 3.370ª posição e nunca chegariam ao modelo.

## Notebooks

| Notebook | Conteúdo | Situação |
|---|---|---|
| `00_introducao_precedentes.ipynb` | Por que criar a terceira base, os três tipos de documento, os documentos recebidos, as respostas sem precedente e o teste de posição | pronto |
| `01_auditoria_precedentes.ipynb` | Inventário com hash, papel de cada documento, extração bruta, numeração completa e vigência | pronto |
| `02_eda_precedentes.ipynb` | Volume, tokens, ruído do texto bruto, cor do título x tese, normas citadas e cobertura das 25 respostas | pronto |
| `03_limpeza_estruturacao_precedentes.ipynb` | Campos, vigência, quarentena e o JSONL único | pronto |
| `04_chunking_precedentes.ipynb` | Um trecho por enunciado ou por item, com cabeçalho e caput repetido; limite de 220 tokens (1.268 trechos) | pronto |
| `05_embeddings_indexacao_precedentes.ipynb` | BGE-M3 (mesma revisão), schema `lex_precedentes` validado, índice de palavras com texto normalizado e sem stopwords (peso IDF), testes de funcionamento | pronto |
| `06_avaliacao_recuperacao_precedentes.ipynb` | Hit@1 e Hit@3 com o precedente esperado | a fazer |

## Dados

| Etapa | Arquivo | No Git? |
|---|---|---|
| Documentos recebidos (10 arquivos, 8 distintos + 2 cópias idênticas) | `data/raw/precedentes/*.pdf` | não (o maior tem 238 MB); o hash fica no inventário |
| Blocos brutos (01) | `data/interim/precedentes/verbetes_brutos.jsonl` | não |
| **JSONL único (03)** | `data/processed/precedentes/precedentes_tst.jsonl` | não; o hash fica em `reports/precedentes/estruturacao/manifesto_estruturacao.json` |
| Relatórios | `reports/precedentes/{auditoria,eda,estruturacao}/` | sim (só identificadores, contagens e hashes) |

O código fica em `src/precedentes/`:
- `documentos.py`: catálogo e inventário;
- `extracao.py`: leitura dos PDFs;
- `estruturacao.py`: limpeza, vigência e JSONL.

Os notebooks são gerados por `scripts/criar_notebook_precedentes_00.py` e `scripts/criar_notebooks_precedentes_01_03.py`. Para executar:

```
python scripts/executar_notebook_integracao.py notebooks/05_docs_precedentes/<notebook>.ipynb
```

## Fontes e decisões

- **Súmulas e OJs:** coletânea do TRT-3 com a jurisprudência consolidada do TST, atualizada até **28/06/2024**, páginas 65-256.
- **Temas:** índice de IRR do TST de **19/11/2026**, parte temática nas páginas 12-121.
- **Vigência:**
  - a situação oficial vem da coletânea;
  - a notícia de cancelamento, que não é fonte oficial, vira alerta;
  - os cancelamentos integrais noticiados ficam fora da busca até a resolução oficial ser conferida (quarentena).
- **Fora desta base:**
  - STF (índice de repercussão geral), que fica para uma etapa posterior;
  - acórdão 168, que contém dados pessoais;
  - coletânea do TRT-2 de 2021, mais antiga e redundante;
  - EC 141/2026, já aplicada à **base de legislação** na versão `ec141_2026`, com o art. 7º atualizado, a nota de vigência e os 10 artigos da emenda (`scripts/atualizar_legislacao_ec141.py`);
  - cópias "(1)" da coletânea do TRT-3 e do índice de repercussão geral, com o mesmo hash dos originais, registradas como duplicata.

## Pendências

1. Livro oficial de súmulas e OJs do TST atualizado em 2026, ou a resolução dos cancelamentos.
2. Lei 605/1949 e LC 150/2015 na base de legislação: ainda trazem a regra anterior à EC 141, com repouso de 24 horas e jornada de 44 horas para domésticos.
