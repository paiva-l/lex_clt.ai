# lex_clt.ai
Aplicação com inteligência artificial para analisar processos trabalhistas, informar direitos e auxiliar trabalhadores na compreensão de sua situação, com respostas fundamentadas na legislação, na jurisprudência e normas.

> 🚧 Projeto em desenvolvimento. As funcionalidades descritas representam o escopo planejado e serão implementadas e avaliadas progressivamente.

## Sobre o projeto

A disponibilidade de informações processuais nem sempre significa que elas sejam compreensíveis para quem precisa utilizá-las. Documentos técnicos, termos jurídicos e decisões complexas podem dificultar o acompanhamento de um processo trabalhista.

Este projeto propõe uma aplicação que utiliza Inteligência Artificial para transformar essas informações em explicações claras, contextualizadas e rastreáveis.

A solução pretende auxiliar trabalhadores na leitura de documentos, na compreensão das decisões e na identificação de possíveis próximas etapas, distinguindo o conteúdo dos documentos, as informações das fontes jurídicas e as incertezas da análise.

## Objetivo

Ampliar o acesso à compreensão dos direitos e processos trabalhistas, oferecendo informações em linguagem simples e favorecendo a autonomia dos trabalhadores.

A aplicação terá caráter informativo e de apoio à compreensão. Seu uso não substituirá a análise e a orientação de um profissional jurídico.

## Público-alvo

- Trabalhadores que desejam compreender seus direitos e documentos.
- Pessoas com dificuldade para acompanhar informações de processos trabalhistas.
- Advogados interessados em facilitar a comunicação com seus clientes.

## Funcionalidades planejadas

| Funcionalidade | Descrição |
|---|---|
| Envio de documentos | Receber documentos em PDF ou imagem. |
| Extração de texto | Extrair conteúdo textual e utilizar OCR quando necessário. |
| Identificação de documentos | Reconhecer tipos de documentos processuais. |
| Contextualização processual | Apresentar indícios da fase do processo com base nos documentos disponíveis. |
| Resumos acessíveis | Explicar o conteúdo em linguagem simples. |
| Explicação de decisões | Apresentar os fundamentos expressamente registrados nas decisões. |
| Perguntas e respostas | Esclarecer dúvidas sobre os documentos e termos jurídicos. |
| Consulta a direitos | Recuperar informações pertinentes na legislação e na jurisprudência selecionadas. |
| Próximas etapas possíveis | Explicar caminhos processuais possíveis, indicando limitações e informações ausentes. |
| Organização documental | Apontar documentos mencionados ou potencialmente relevantes para revisão profissional. |
| Referências verificáveis | Relacionar as explicações aos documentos e às fontes utilizadas. |

A identificação da fase processual dependerá da abrangência e da atualidade dos documentos fornecidos. Um documento isolado pode não representar a situação atual do processo.

## Arquitetura proposta

> A arquitetura implementada, a base de conhecimento, as estratégias de chunking e embeddings, o banco vetorial e o roteiro da demonstração estão descritos em [docs/semana2_base_conhecimento_e_rag.md](docs/semana2_base_conhecimento_e_rag.md).

O sistema será organizado em dois fluxos principais.

### Preparação das bases jurídicas

1. Coleta ou importação de legislação e jurisprudência.
2. Auditoria das fontes, dos arquivos e das versões.
3. Análise exploratória e avaliação da qualidade.
4. Limpeza e estruturação dos documentos.
5. Divisão em trechos com preservação do contexto.
6. Criação dos índices de recuperação.

Legislação e jurisprudência terão identificação própria, metadados e critérios de atualização.

### Análise e resposta ao usuário

1. Recebimento dos documentos e da pergunta.
2. Extração do texto, com OCR quando necessário.
3. Organização do conteúdo e de suas referências.
4. Recuperação de trechos pertinentes nos documentos e nas bases jurídicas.
5. Reordenação dos candidatos com um cross-encoder.
6. Geração de uma explicação com uma LLM.
7. Apresentação das fontes, limitações e informações ausentes.

### Componentes de Inteligência Artificial

| Componente | Papel no sistema |
|---|---|
| OCR | Reconhecer texto em imagens e documentos digitalizados. |
| Embeddings | Representar textos para recuperação por similaridade semântica. |
| Busca lexical | Recuperar termos exatos, expressões e referências a dispositivos. |
| Recuperação híbrida | Combinar resultados da busca lexical e da busca vetorial. |
| Cross-encoder | Reordenar os trechos recuperados conforme sua relevância para a pergunta. |
| LLM | Elaborar explicações a partir do contexto selecionado. |
| Classificador, se necessário | Auxiliar na identificação de tipos documentais, conforme os resultados dos experimentos. |

O RAG integra a recuperação de informações à geração das respostas. O cross-encoder atua na seleção dos trechos mais relevantes.

Na primeira versão, poderão ser utilizados modelos pré-treinados. A necessidade de treinamento ou fine-tuning será avaliada a partir dos resultados dos experimentos.

## Organização prevista do repositório

```text
.
├── README.md
├── .gitignore
├── .env.example
├── requirements.txt
│
├── configs/                 # Configurações dos pipelines
├── docs/                    # Requisitos, arquitetura e decisões
│
├── data/
│   ├── raw/                 # Fontes originais
│   ├── interim/             # Extrações intermediárias
│   ├── processed/           # Documentos estruturados
│   ├── chunks/              # Trechos para recuperação
│   └── evaluation/          # Perguntas e referências de avaliação
│
├── notebooks/               # Auditoria, EDA e experimentos
├── reports/                 # Relatórios e gráficos
├── indexes/                 # Índices gerados
│
├── src/
│   ├── ingestion/           # Leitura de fontes
│   ├── processing/          # Limpeza, metadados e chunking
│   ├── retrieval/           # Indexação e recuperação
│   ├── reranking/           # Cross-encoder
│   ├── generation/          # Integração com a LLM
│   ├── classification/      # Classificação documental
│   └── evaluation/          # Avaliação dos componentes
│
├── backend/                 # API e serviços da aplicação
├── frontend/                # Interface do usuário
└── tests/                   # Testes dos componentes
```

Essa estrutura será criada conforme o desenvolvimento dos módulos.

Documentos reais de usuários, credenciais, arquivos de ambiente e índices contendo dados pessoais não deverão ser versionados no repositório.

## Ciência de Dados

Os experimentos serão organizados nos seguintes notebooks:

| Notebook | Objetivo |
|---|---|
| `01_auditoria_clt.ipynb` | Inventariar arquivos e verificar fontes, formatos, duplicações e problemas de extração. |
| `02_eda_clt.ipynb` | Explorar a composição e a estrutura textual do corpus. |
| `03_limpeza_estruturacao_clt.ipynb` | Preparar documentos e metadados preservando o significado jurídico. |
| `04_experimentos_chunking.ipynb` | Comparar estratégias de divisão dos textos. |
| `05_construcao_base_avaliacao.ipynb` | Organizar perguntas e referências esperadas. |
| `06_experimentos_recuperacao.ipynb` | Comparar busca lexical, vetorial e híbrida. |
| `07_integracao_rag_legislacao.ipynb` | Gerar respostas fundamentadas com citação de fontes e validar as citações. |
| `08_avaliacao_rag_llm.ipynb` | Avaliar respostas, citações, limitações e erros do sistema. |

A jurisprudência e a análise de documentos processuais poderão receber notebooks específicos nas etapas seguintes.

## Avaliação

O projeto avaliará tanto o desempenho técnico quanto a utilidade das explicações.

- **Extração:** preservação do conteúdo e identificação de falhas.
- **Recuperação:** Recall@k, MRR e nDCG@k.
- **Reranking:** ganho de relevância e impacto na latência.
- **Respostas:** correção, cobertura da pergunta e suporte nas fontes.
- **Classificação documental:** precisão, recall e F1 por classe, quando implementada.
- **Compreensão:** entendimento dos usuários antes e depois do uso.
- **Usabilidade:** facilidade para realizar as tarefas propostas.
- **Privacidade:** verificação dos controles e do tratamento dos dados.

As metas quantitativas serão definidas após a criação de uma linha de base. A avaliação jurídica das explicações deverá contar com revisão especializada.

## Privacidade e segurança

Documentos processuais podem conter dados pessoais e sensíveis. O desenvolvimento deverá considerar:

- Minimização dos dados coletados.
- Controle de acesso e isolamento entre usuários.
- Proteção dos arquivos armazenados e transmitidos.
- Regras de retenção e exclusão.
- Redução de dados pessoais em logs.
- Avaliação dos provedores utilizados para OCR e modelos.
- Tratamento dos documentos como conteúdo não confiável, incluindo proteção contra instruções maliciosas inseridas nos arquivos.
- Uso de exemplos sintéticos ou devidamente anonimizados em demonstrações públicas.

A adequação à LGPD é um requisito do projeto e dependerá da implementação e da avaliação dos procedimentos adotados.

## Limitações

A aplicação poderá produzir interpretações incorretas, recuperar fontes inadequadas ou deixar de identificar informações relevantes.

As respostas deverão indicar quando:

- Os documentos forem insuficientes ou ilegíveis.
- A atualização das fontes não estiver confirmada.
- Houver divergência entre informações.
- Não existir suporte suficiente para uma conclusão.

Estimativas de resultado, cálculos de prazos e recomendações de estratégia jurídica não fazem parte do MVP inicial.

## Roadmap

- [ ] Definir o escopo inicial e os requisitos.
- [ ] Auditar o repositório de legislação.
- [ ] Realizar a análise exploratória.
- [ ] Estruturar documentos e metadados.
- [ ] Construir a base de avaliação.
- [ ] Implementar e avaliar a recuperação.
- [ ] Integrar e avaliar o cross-encoder.
- [ ] Integrar a LLM com referências verificáveis.
- [ ] Implementar a leitura de documentos enviados.
- [ ] Desenvolver a API e a interface.
- [ ] Realizar revisão jurídica e testes com usuários.

## Como executar

As instruções de instalação e execução serão adicionadas conforme os componentes forem implementados e validados.

## Contribuições

Sugestões de melhoria, relatos de problemas e contribuições técnicas ou de acessibilidade são bem-vindos por meio de issues.

Não inclua dados pessoais, documentos processuais reais ou credenciais nas issues e nos pull requests.

## Licença

A licença do código será definida pelos responsáveis pelo projeto.

As fontes de dados e os modelos utilizados possuem condições próprias de uso, que deverão ser documentadas.
