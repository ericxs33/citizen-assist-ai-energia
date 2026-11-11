# Citizen Assist AI - Energia

Global Solution · **Soluções em Energias Renováveis e Sustentáveis** · FIAP · Ciência da Computação (1CC)

Assistente de terminal, em Python, que orienta moradores sobre o gasto de energia do **chuveiro elétrico**, compara alternativas de economia e de fonte renovável e explica as premissas e limitações de cada estimativa.

## Integrantes

| Nome completo | RM |

| Eric dos Santos Mendes da Silva | 569528 |
| Tom Stringaci Albuquerque Coelho Morais | 568844 |
| Rafael Côrtes Lins | 570588 |

## Contribuição desta disciplina

Este repositório contém a contribuição de **Soluções em Energias Renováveis e Sustentáveis** ao Citizen Assist AI: análise de consumo, comparação de alternativas (incluindo fonte renovável) e a integração desses resultados às respostas do assistente.

## Público e problema

- **Público:** moradores de residências atendidos pelo Citizen Assist AI, sem conhecimento técnico de energia.
- **Necessidade:** entender quanto o chuveiro elétrico gasta, quanto isso custa e se vale a pena reduzir o tempo de banho ou instalar um aquecedor solar.
- **Como ajuda:** o usuário informa seus dados (pessoas, minutos de banho, tarifa, potência) e recebe números calculados, a recomendação e as fontes, em linguagem simples.

## Funcionalidades de energia

| Opção no menu | O que faz |
|---|---|
| 1 | Consumo do chuveiro em kWh por mês (E = P × t) |
| 2 | Custo do banho na conta de luz, por mês e por ano |
| 3 | Economia com banho mais curto |
| 4 | Aquecedor solar: funcionamento, economia e retorno (payback) |
| 5 | Comparação das 4 alternativas, com custo acumulado em 10 anos e recomendação |
| 6 | Impacto ambiental (kg de CO2) |
| 7 | Fontes e premissas usadas |
| C | Configuração da IA de apoio (opcional) |
| Pergunta livre | O assistente entende texto, como "somos 3 pessoas, banho de 15 min, vale a pena o solar?" |

As respostas são **calculadas na hora** com os dados do usuário (módulo `calculos.py`), não copiadas de texto fixo. O usuário pode trocar a tarifa e a potência pelos valores da própria conta e do próprio chuveiro.

## Como executar

Requisito: Python 3.8 ou superior. Não é preciso instalar bibliotecas.

```powershell
cd citizen_assist_energia
python main.py
```

Testes automáticos:

```powershell
python -m unittest discover -s tests -v
```

Dica: no menu, digite `5` para ver a comparação completa ou `ajuda` para ver exemplos de perguntas.

## Dados e premissas

Os dados ficam em `data/premissas.json`, cada um com tipo (**real** ou **estimado**), fonte e data de consulta.

| Premissa | Valor | Tipo | Fonte | Consulta |
|---|---|---|---|---|
| Potência do chuveiro elétrico | 5.500 W | estimado | Valor típico de chuveiros elétricos; conferir na etiqueta do modelo | 06/11/2026 |
| Tarifa residencial B1 da Enel SP, sem impostos, bandeira verde | 0,78938 R$/kWh | real | ANEEL, REH nº 3.596/2026 (Enel SP, vigência 04/07/2026 a 03/07/2027) | 06/11/2026 |
| Fator médio de emissão do Sistema Interligado Nacional, média anual de 2023 | 0,0385 kg CO2/kWh | real | MCTI/SIRENE: 38,5 kg CO2/MWh em 2023 | 06/11/2026 |
| Fração da energia do banho suprida pelo aquecedor solar | 0,7 fração (0 a 1) | estimado | ABNT NBR 15569 (dimensiona com 70% de fração solar); estudo em Viçosa-MG com redução média de 70% na energia de aquecimento de água | 06/11/2026 |
| Investimento no aquecedor solar de 300 L para cerca de 4 pessoas | 7.000 R$ | estimado | Ponto médio da faixa de R$ 5.000 a R$ 9.000 (Monitor do Mercado, 2026); kit de 200 L sem instalação: R$ 3.240 (SINAPI 05/2026) | 06/11/2026 |

## Cálculos e comparação das alternativas

**Mesma necessidade** (aquecer a água do banho) e **mesmo período** (30 dias, com custo acumulado em 10 anos).

- Energia: `E (kWh) = P (kW) × t (h) × pessoas × dias`
- Custo: `kWh × tarifa` · CO2: `kWh × fator de emissão`
- Aquecedor solar: `kWh_solar = kWh_atual × (1 − fração solar)`
- Payback: `investimento ÷ (economia mensal × 12)`
- Custo acumulado: `investimento + custo mensal × 12 × 10 anos`

Exemplo: 4 pessoas, banho de 10 min, meta de 5 min, chuveiro de 5.500 W.

| Alternativa | kWh/mês | R$/mês | kg CO2/mês | R$ acumulado em 10 anos |
|---|---|---|---|---|
| Chuveiro elétrico (atual) | 110,0 | 86,83 | 4,24 | 10.420 |
| Banho mais curto | 55,0 | 43,42 | 2,12 | 5.210 |
| Aquecedor solar | 33,0 | 26,05 | 1,27 | 10.126 |
| Banho curto + solar | 16,5 | 13,02 | 0,64 | 8.563 |

- Banho mais curto: economia de **R$ 43,42 por mês**, sem investimento.
- Aquecedor solar: economia de **R$ 60,78 por mês**, com payback de cerca de **9,6 anos**.
- Para quem já encurta o banho, o solar demora mais para se pagar: cerca de 19,2 anos.

## Justificativas das recomendações

- **Custo:** o banho mais curto tem custo zero e economia imediata; o solar exige investimento alto e retorno de longo prazo.
- **Viabilidade:** o solar depende de telhado com insolação, instalação adequada e apoio elétrico em dias nublados; compensa mais em casas com muitos banhos.
- **Impacto ambiental:** como a matriz elétrica brasileira já é bastante renovável, o CO2 evitado é pequeno em kg; o ganho mais claro é a economia na conta.
- **Recomendação do assistente:** adotar primeiro o banho mais curto e avaliar o solar com orçamentos reais.

## IA de apoio (uso criterioso)

Quando o assistente não sabe responder, ou o usuário marca que a resposta não ajudou, uma IA de apoio pode assumir. Ela é **opcional**: sem chave, o projeto funciona inteiro.

- Recebe as premissas e os cálculos do projeto como contexto e é instruída a **não inventar números** nem fontes.
- Toda resposta de IA vem identificada e com aviso para conferir os números.
- Dados pessoais (CPF, telefone, e-mail) são bloqueados antes de qualquer envio.
- Os números principais continuam vindo dos cálculos e das fontes verificadas pela equipe.
- A chave fica em `config_ia.json`, **fora do GitHub** (`.gitignore`). Veja `config_ia.exemplo.json`.

## Testes com usuários

Cada resposta e cada sessão são registradas, sem dados pessoais:

- `data/atendimentos.csv`: pergunta, origem da resposta (`regras` ou `ia`), dados usados e se ajudou.
- `data/avaliacoes.csv`: nota de facilidade (1 a 5) e comentário de cada sessão.

Situações testadas, comentários recebidos e ajustes feitos: [PREENCHER após as rodadas de teste].

## Limitações

- Os valores são **estimativas, não resultados garantidos**.
- O consumo real varia com o modelo do chuveiro, a temperatura da água e os hábitos da casa.
- A tarifa padrão é a da Enel SP **sem impostos**; o usuário pode informar a da sua conta.
- O fator de emissão é a média anual de 2023.
- O solar depende de insolação, instalação e apoio elétrico; o investimento é uma estimativa.

## Referências

- **ANEEL.** Resolução Homologatória nº 3.596, de 30 de junho de 2026. Homologa as tarifas de fornecimento de energia elétrica da Enel Distribuição São Paulo, vigentes a partir de 04 de julho de 2026. Tarifa residencial convencional B1: TUSD de R$ 472,42/MWh e TE de R$ 316,96/MWh, totalizando R$ 0,78938/kWh, sem impostos. Consulta em 06 nov. 2026.
- **MCTI.** Ministério da Ciência, Tecnologia e Inovação. Sistema de Registro Nacional de Emissões (SIRENE). Fator médio anual de emissão de CO₂ pela geração de energia elétrica no Sistema Interligado Nacional (SIN), ano-base 2023: 0,0385 tCO₂/MWh. Brasília, 2024. Consulta em 06 nov. 2026.
- **ABNT.** Associação Brasileira de Normas Técnicas. ABNT NBR 15569:2020/Emenda 1:2021. Sistema de aquecimento solar de água em circuito direto — Requisitos de projeto e instalação. Rio de Janeiro: ABNT, 2021.
- **ALTOÉ, Leandra; OLIVEIRA FILHO, Delly; CARLO, Joyce Correna.** Análise energética de sistemas solares térmicos para diferentes demandas de água em uma residência unifamiliar. Ambiente Construído, Porto Alegre, v. 12, n. 3, p. 75–87, 2012. DOI: https://doi.org/10.1590/S1678-86212012000300006. Estudo realizado por simulação nas condições climáticas de Viçosa-MG, que identificou redução média de 70% no consumo de eletricidade destinado ao aquecimento de água com sistema solar e apoio elétrico.
- **MONITOR DO MERCADO.** Quanto custa instalar aquecimento solar de água para 4 pessoas em 2026? O boiler é apenas uma parte do projeto. 30 ago. 2026. Referência de custos para sistemas residenciais de aproximadamente 300 litros, com instalação estimada entre R$ 5.000 e R$ 9.000 em residências preparadas. Consulta em 06 nov. 2026.
- **CAIXA ECONÔMICA FEDERAL; IBGE.** Sistema Nacional de Pesquisa de Custos e Índices da Construção Civil (SINAPI). Relatório de Insumos e Composições, São Paulo, maio de 2026. Insumo 34472: aquecedor solar de instalação externa, kit compacto com reservatório térmico de 200 litros, placa coletora de 2,0 m² e acessórios. Preço de referência do insumo: R$ 3.240,00, sem instalação. Consulta em 06 nov. 2026.

## Estrutura do projeto

```
citizen_assist_energia/
├── main.py           (menu e conversa no terminal)
├── assistente.py     (interpreta a pergunta e monta a resposta)
├── calculos.py       (consumo, custo, CO2, payback)
├── premissas.py      (carrega e valida os dados)
├── ia.py             (IA de apoio, vários provedores)
├── config_ia.py      (chaves locais, fora do GitHub)
├── registros.py      (registro dos testes com usuários)
├── data/             (premissas.json e registros dos testes)
└── tests/            (testes automáticos)
```
