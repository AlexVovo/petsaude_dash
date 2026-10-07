# Conferência para apresentação — 07/10/2026

Não constitui certificação integral das bases. Foram conferidos os agregados locais, o código de transformação e a renderização do painel via AppTest. Os microdados SIA, SIH, CNES e RHC não foram localizados no projeto para regeneração independente.

## Ajustes realizados após a conferência

- Após a falha de saúde do Community Cloud (`/healthz: EOF`), a leitura foi otimizada com cópias Parquet validadas coluna por coluna, SHA-256 da fonte e bases compartilhadas somente para leitura. As abas agora executam apenas seu conteúdo aberto. Na medição local de uma inicialização com AppTest, o pico caiu de 1.023.496 KB para 560.848 KB (aproximadamente 45%). Esse resultado não certifica o consumo na hospedagem nem confirma a causa do encerramento remoto. O processo de testes com múltiplos recortes também lê JSONs diretamente para verificar os resultados e não representa uma sessão comum do painel.

- A categoria residual do filtro passou a ser apresentada como “Outros diagnósticos (conforme a base)” e traduzida para o nome usado no SIA/custos. A diferença de escopo está explicada na barra lateral; não se afirma equivalência entre neoplasias malignas e todos os diagnósticos administrativos.
- O RHC passou a responder à região de residência e ganhou filtro próprio de grupo CICI/ICCC-3. O filtro diagnóstico global foi identificado como exclusivo do SIM/SIA/SIH, evitando uma conversão imprecisa entre CID-10 e ICCC-3.
- Região e UF passaram a ter nomes neutros, com explicação do território correspondente em cada fonte.
- O indicador de tempo APAC foi renomeado para registros de início por modalidade. A deduplicação por modalidade, o uso da autorização como chave substituta e a seleção anual por competência estão explicitados. Os metadados e o gerador foram ajustados; não houve nova deduplicação de microdados.
- A taxa bruta passou a mostrar seu período efetivo e a explicar a razão entre somas. O numerador agora exclui registros sem sexo, faixa etária ou UF compatível com o denominador, mantendo-os nas contagens.
- O painel continua exibindo as outras fontes quando o recorte do SIM fica vazio. A participação pediátrica e a distância média de cirurgia tratam denominadores vazios.
- A aba Acesso explicita que 2026 é parcial.
- Testes de regressão em `tests/test_filtros.py` conferem a categoria residual em APAC/custos, o recorte regional e diagnóstico do RHC e a compatibilidade da taxa e dos rótulos APAC.

## Verificações concluídas

- SIM: 5.344.014 óbitos no agregado de 1996–2026, coincidindo com o total dos metadados. Sem chaves de agregação duplicadas, contagens negativas ou ausentes.
- SIM 2024, 2025 e 2026: regeneração dos CSVs nacionais locais com o gerador do projeto. Todos os grupos coincidem com o JSON, sem divergências. Totais: 259.084, 157.298 e 91.830, respectivamente. Os outros anos não foram regenerados nesta conferência.
- IBGE: comparação independente, lendo diretamente o XML da planilha original local e somando por ano, UF, sexo e faixa etária. Os 8.748 denominadores coincidem integralmente com o JSON.
- APAC: soma de 7.782.100 registros mensais, sendo 7.515.921 de quimioterapia e 266.179 de radioterapia. Sem duplicações das chaves do agregado. Isso não comprova ausência de duplicação nos microdados.
- SIH: 282.496 internações com cirurgia oncológica no agregado.
- CNES: 387 estabelecimentos; 338 CACON/UNACON, 211 com radioterapia e 87 com oncologia pediátrica, conforme os registros locais.
- RHC: 37.914 casos, coincidindo com os metadados.
- Valores SIA/SIH: R$ 10.161.774.659,44 no agregado. Representam valores administrativos; não custo econômico integral ou pagamento efetivo.
- AppTest: painel inicial renderiza sem exceções; métricas de contagem coincidem com os agregados.

## Problemas encontrados na versão anterior (ajustados acima)

1. O filtro SIM “Outras neoplasias malignas” é aplicado literalmente a APAC e custos, que usam “Outros diagnósticos oncológicos”. Reproduzido em AppTest: selecioná-lo produz ausência de dados nessas duas bases. As categorias têm escopos distintos e precisam de tratamento explícito.
2. O RHC ignora os filtros de região e tipo de câncer. Reproduzido em AppTest: selecionar região Sul mantém os 37.914 casos nacionais da base. O filtro de tipo também mantém esse total. A classificação ICCC-3 exige correspondência específica com os tipos usados pelo SIM.
3. APAC deduplica por modalidade e identificador, portanto uma pessoa com quimioterapia e radioterapia pode ser contada duas vezes na soma do indicador de tempo. Os 762.812 não podem ser afirmados como pessoas únicas entre modalidades. Na ausência de identificador, o gerador usa a APAC como chave substituta.
4. Os filtros de região/UF são rotulados como residência, mas são aplicados ao território de atendimento em APAC, cirurgias e custos. Comparações territoriais precisam explicitar essa diferença.
5. A taxa de 94,9/100 mil no recorte inicial usa 2000–2024; a contagem de 5.344.014 usa 1996–2026. Os períodos precisam acompanhar os indicadores na apresentação. A taxa usa a razão entre soma de óbitos e soma das populações anuais; não é média aritmética das taxas anuais nem taxa padronizada por idade.

## Cobertura a declarar

- SIM: 2025 preliminar e 2026 primeira prévia, segundo os metadados locais. Não interpretar a queda como redução real da mortalidade. O portal oficial também identifica 2026 como primeira prévia: https://dadosabertos.saude.gov.br/dataset/sim
- APAC, cirurgias e valores administrativos: janeiro de 2025 a junho de 2026. Não comparar o total parcial de 2026 com o ano completo de 2025.
- CNES: retrato da competência julho de 2026.
- RHC pediátrico: 2019–2023, excluindo São Paulo e com 2023 parcial; não representa incidência populacional.
- Periodicidade no cabeçalho significa organização temporal dos registros, não frequência garantida de atualização do painel.

As contagens armazenadas permanecem iguais. Foram ajustados filtros, o numerador das taxas, rótulos e metadados. A validação independente dos microdados SIA/SIH/CNES/RHC permanece pendente.
