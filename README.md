# Painel Integrado de Oncologia

Painel em Python/Streamlit criado a partir das perguntas do documento **Perguntas Painel Onco**. A versão atual integra dados reais agregados do SIM, IBGE, CNES, SIA/APAC, SIH/AIH e Integrador RHC/INCA, sem dados sintéticos. Perguntas de custos foram retiradas desta etapa.

## Executar

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
streamlit run dash_onco_pet.py
```

## Gerar o agregado do SIM

Com os CSVs nacionais e estaduais na pasta informada, execute:

```bash
.venv/bin/python gerar_json_sim.py "/home/alex/CSV_SIM/CSV"
```

O gerador usa somente os arquivos nacionais `DOBR<ano>.csv`, evitando dupla contagem com os arquivos estaduais, filtra causa básica CID-10 C00–C97 e cria `dados/sim_oncologia_agregado.json`. O resultado é agregado por ano, mês, UF/região de residência, tipo de câncer, sexo, faixa etária e segmento.

Para gerar os denominadores populacionais, baixe do IBGE a planilha **População por sexo e idade simples** da Revisão 2024 e execute:

```bash
.venv/bin/python gerar_populacao_ibge.py dados/projecoes_2024_tab1_idade_simples.xlsx
```

O arquivo `dados/populacao_ibge.json` permite calcular taxas anuais, do período, territoriais e específicas por sexo e idade para 2000 em diante. As taxas ainda são brutas ou específicas; a padronização por idade será uma etapa posterior.

## Gerar o agregado pediátrico do RHC

Baixe no Integrador RHC/INCA o pacote de **Todos os Estados, exceto SP**, selecione os anos desejados e use a tabela de conversão `dados/ICCC-2017.xlsx`:

```bash
.venv/bin/python gerar_rhc_pediatrico.py download_tabwin.zip dados/ICCC-2017.xlsx
```

O gerador seleciona casos de 0 a 19 anos, aplica os grupos e subgrupos da CICI/ICCC-3 (atualização IARC 2017) a partir de topografia, morfologia e comportamento CID-O-3 e agrega primeiro tratamento, motivo de não tratamento e intervalo diagnóstico–tratamento em `dados/rhc_pediatrico_iccc.json`. A base atual cobre 2019–2023, exclui São Paulo e tem 2023 parcial.

## Outras bases

O dashboard identifica explicitamente as perguntas que ainda dependem de RCBP/INCA, IBGE, CNES/SAES, Painel Oncológico, RHC, SIA/SIH, regulação municipal ou bases clínicas longitudinais. O SIM não deve ser usado para inferir incidência, cura, recorrência ou acesso ao tratamento.

## Escopo e limitações

- RHC/INCA descreve assistência hospitalar, não incidência populacional.
- Taxas populacionais requerem RCBP/SIM e denominadores do IBGE.
- Habilitação no CNES não é sinônimo de capacidade ou ocupação.
- ICCC-3 é derivada de topografia, morfologia e comportamento CID-O-3; os casos não enquadrados permanecem explicitamente como não classificados.
- O app trabalha com dados agregados e não envia arquivos para serviços externos.
