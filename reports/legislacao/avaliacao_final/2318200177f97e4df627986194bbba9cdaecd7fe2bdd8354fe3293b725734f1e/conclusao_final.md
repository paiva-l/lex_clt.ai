### Análise e conclusão final

O pipeline concluiu **9 de 9 respostas**, com **0 falhas técnicas**.
Nas **7 perguntas respondíveis**, o Recall@3 foi **100.0%**,
o MRR@3 foi **1.000**, o nDCG@3 foi **1.000**
e a cobertura literal das evidências foi **100.0%**.
Essas medidas dizem respeito às fontes efetivamente entregues, depois da deduplicação e do orçamento de contexto.
Os **2 casos sem resposta** não recebem acerto artificial de recuperação.

A revisora aprovou **6 respostas originais (66.7%)** e reprovou
**3 (33.3%)**: **q_test_03, q_test_05, q_test_neg_02**.
As nove avaliações estão registradas; reprovação é uma decisão concluída, não ausência de revisão.
As observações e respostas finais da revisora foram preservadas separadamente das saídas originais.

O contraste entre a recuperação e a aprovação humana mostra que localizar o dispositivo esperado
não garante uma explicação correta ou uma conduta adequada. As revisões registraram problemas de
referências aos dispositivos, afirmações sem suporte, repetições, limitações genéricas e classificação
indevida de perguntas como fora do escopo. São achados qualitativos das fichas; não uma contagem
automática de erros por categoria. Alertas de citação também não comprovam alucinação.

**Limitações:** este é um piloto com apenas 9 perguntas, uma configuração e revisão humana
com ressalvas documentadas. A cobertura literal pode ser favorecida pelo envio de artigos completos.
A aprovação humana não é certificação jurídica independente. Os tempos refletem o equipamento e o uso
de cache observado. Não houve anotação específica suficiente para informar uma taxa de alucinação
ou de recusa correta; esses indicadores não são presumidos como zero.

**Melhorias futuras:** serão feitas melhorias na formulação, diversidade e clareza das perguntas,
assim como na precisão, fundamentação, concisão e adequação das respostas geradas. O trabalho incluirá
curadoria das correções propostas, revisão das remissões legais, tratamento de informações insuficientes
e distinção entre tema fora do escopo e ausência de evidência. Ajustes de prompt ou do modelo serão
versionados e avaliados separadamente. O feedback salvo é insumo para essa curadoria, sem treinamento
automático nem alteração dos resultados originais.

Se estas perguntas ou correções forem utilizadas para melhorar o sistema, será necessário **um novo
conjunto de teste independente** para avaliar a nova versão. O diagnóstico atual permanece como
registro da versão congelada e das decisões efetivamente realizadas.
