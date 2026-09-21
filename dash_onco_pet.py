"""Painel de oncologia baseado em dados reais agregados do SIM/DATASUS."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Painel Onco — dados reais", page_icon=":material/monitoring:", layout="wide")
ARQUIVO_SIM = Path(__file__).parent / "dados" / "sim_oncologia_agregado.json"
ARQUIVO_POPULACAO = Path(__file__).parent / "dados" / "populacao_ibge.json"
ARQUIVO_ESTRUTURA = Path(__file__).parent / "dados" / "estrutura_oncologia_cnes.json"
ARQUIVO_APAC = Path(__file__).parent / "dados" / "apac_oncologia.json"
ARQUIVO_CIRURGIAS = Path(__file__).parent / "dados" / "cirurgias_oncologicas_sih.json"
ARQUIVO_RHC_PEDIATRICO = Path(__file__).parent / "dados" / "rhc_pediatrico_iccc.json"
CORES = ["#14532d", "#16a34a", "#4ade80", "#0f766e", "#f59e0b", "#dc2626", "#7c3aed", "#0369a1"]


@st.cache_data(show_spinner=False)
def carregar_sim(caminho: str, modificado_em: float) -> tuple[pd.DataFrame, dict]:
    del modificado_em
    with Path(caminho).open(encoding="utf-8") as arquivo:
        payload = json.load(arquivo)
    dados = pd.DataFrame(payload["dados"])
    dados[["ano", "mes", "obitos"]] = dados[["ano", "mes", "obitos"]].apply(pd.to_numeric)
    return dados, payload["metadados"]


@st.cache_data(show_spinner=False)
def carregar_populacao(caminho: str, modificado_em: float) -> tuple[pd.DataFrame, dict]:
    del modificado_em
    with Path(caminho).open(encoding="utf-8") as arquivo:
        payload = json.load(arquivo)
    dados = pd.DataFrame(payload["dados"])
    dados[["ano", "populacao"]] = dados[["ano", "populacao"]].apply(pd.to_numeric)
    return dados, payload["metadados"]


@st.cache_data(show_spinner=False)
def carregar_estrutura(caminho: str, modificado_em: float) -> tuple[pd.DataFrame, dict]:
    del modificado_em
    with Path(caminho).open(encoding="utf-8") as arquivo:
        payload = json.load(arquivo)
    return pd.DataFrame(payload["dados"]), payload["metadados"]


@st.cache_data(show_spinner=False)
def carregar_apac(caminho: str, modificado_em: float) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    del modificado_em
    with Path(caminho).open(encoding="utf-8") as arquivo:
        payload = json.load(arquivo)
    return pd.DataFrame(payload["producao"]), pd.DataFrame(payload["tempo"]), payload["metadados"]


@st.cache_data(show_spinner=False)
def carregar_cirurgias(caminho: str, modificado_em: float) -> tuple[pd.DataFrame, dict]:
    del modificado_em
    with Path(caminho).open(encoding="utf-8") as arquivo:
        payload = json.load(arquivo)
    return pd.DataFrame(payload["dados"]), payload["metadados"]


@st.cache_data(show_spinner=False)
def carregar_rhc_pediatrico(caminho: str, modificado_em: float) -> tuple[pd.DataFrame, dict]:
    del modificado_em
    with Path(caminho).open(encoding="utf-8") as arquivo:
        payload = json.load(arquivo)
    dados = pd.DataFrame(payload["dados"])
    dados[["ano", "casos"]] = dados[["ano", "casos"]].apply(pd.to_numeric)
    return dados, payload["metadados"]


def soma(df: pd.DataFrame) -> int:
    return int(df["obitos"].sum())


def numero(valor: int | float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def barras(df: pd.DataFrame, categoria: str, titulo: str, chave: str) -> None:
    agregado = df.groupby(categoria, observed=True)["obitos"].sum().sort_values().reset_index()
    fig = px.bar(agregado, x="obitos", y=categoria, orientation="h", color="obitos",
                 color_continuous_scale="Greens", labels={"obitos": "Óbitos", categoria: ""}, title=titulo)
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, key=chave)


def pendencia(titulo: str, texto: str, fonte: str) -> None:
    with st.container(border=True):
        st.markdown(f"**:material/database: {titulo}**")
        st.write(texto)
        st.caption(f"Fonte necessária: {fonte}")


def calcular_taxas(obitos: pd.DataFrame, denominadores: pd.DataFrame, grupos: list[str]) -> pd.DataFrame:
    numerador = obitos.groupby(grupos, observed=True)["obitos"].sum().reset_index()
    denominador = denominadores.groupby(grupos, observed=True)["populacao"].sum().reset_index()
    resultado = numerador.merge(denominador, on=grupos, how="inner")
    resultado["taxa_100mil"] = resultado["obitos"] / resultado["populacao"] * 100_000
    return resultado


if any(not arquivo.exists() for arquivo in [ARQUIVO_SIM, ARQUIVO_POPULACAO, ARQUIVO_ESTRUTURA, ARQUIVO_APAC, ARQUIVO_CIRURGIAS, ARQUIVO_RHC_PEDIATRICO]):
    st.error("Os agregados do SIM, IBGE, CNES, SIA/APAC, SIH/AIH e RHC precisam ser criados antes de executar o painel.")
    st.code(".venv/bin/python gerar_json_sim.py '/home/alex/CSV_SIM/CSV'\n"
            ".venv/bin/python gerar_populacao_ibge.py dados/projecoes_2024_tab1_idade_simples.xlsx\n"
            ".venv/bin/python gerar_estrutura_cnes.py\n"
            ".venv/bin/python gerar_apac_oncologia.py\n"
            ".venv/bin/python gerar_cirurgias_sih.py\n"
            ".venv/bin/python gerar_rhc_pediatrico.py PACOTE_RHC.zip dados/ICCC-2017.xlsx", language="bash")
    st.stop()

sim, metadados = carregar_sim(str(ARQUIVO_SIM), ARQUIVO_SIM.stat().st_mtime)
populacao, metadados_pop = carregar_populacao(str(ARQUIVO_POPULACAO), ARQUIVO_POPULACAO.stat().st_mtime)
estrutura, metadados_estrutura = carregar_estrutura(str(ARQUIVO_ESTRUTURA), ARQUIVO_ESTRUTURA.stat().st_mtime)
apac, tempo_apac, metadados_apac = carregar_apac(str(ARQUIVO_APAC), ARQUIVO_APAC.stat().st_mtime)
cirurgias, metadados_cirurgias = carregar_cirurgias(str(ARQUIVO_CIRURGIAS), ARQUIVO_CIRURGIAS.stat().st_mtime)
rhc_ped, metadados_rhc = carregar_rhc_pediatrico(str(ARQUIVO_RHC_PEDIATRICO), ARQUIVO_RHC_PEDIATRICO.stat().st_mtime)
anos_provisorios = {int(ano): situacao for ano, situacao in metadados.get("periodos_provisorios", {}).items()}
with st.sidebar:
    st.header("Filtros")
    anos = sorted(sim.ano.unique())
    periodo = st.slider("Período do óbito", int(min(anos)), int(max(anos)), (int(min(anos)), int(max(anos))))
    tipos = st.multiselect("Tipo de câncer", sorted(sim.tipo_cancer.unique()), placeholder="Todos")
    regioes = st.multiselect("Região de residência", sorted(sim.regiao.unique()), placeholder="Todas")
    base_uf = sim[sim.regiao.isin(regioes)] if regioes else sim
    ufs = st.multiselect("UF de residência", sorted(base_uf.uf.unique()), placeholder="Todas")
    sexos = st.multiselect("Sexo", sorted(sim.sexo.unique()), placeholder="Todos")
    faixas = st.multiselect("Faixa etária", sorted(sim.faixa_etaria.unique()), placeholder="Todas")
    segmentos = st.multiselect("Segmento", sorted(sim.segmento.unique()), placeholder="Todos")
    st.caption("Filtros vazios incluem todas as categorias.")

filtro = sim[sim.ano.between(*periodo)].copy()
for coluna, valores in [("tipo_cancer", tipos), ("regiao", regioes), ("uf", ufs), ("sexo", sexos),
                        ("faixa_etaria", faixas), ("segmento", segmentos)]:
    if valores:
        filtro = filtro[filtro[coluna].isin(valores)]

estrutura_filtro = estrutura.copy()
if regioes:
    estrutura_filtro = estrutura_filtro[estrutura_filtro.regiao.isin(regioes)]
if ufs:
    estrutura_filtro = estrutura_filtro[estrutura_filtro.uf.isin(ufs)]

apac_filtro = apac[apac.ano.between(*periodo)].copy()
tempo_apac_filtro = tempo_apac[tempo_apac.ano.between(*periodo)].copy()
for coluna_apac, valores in [
    ("tipo_cancer", tipos), ("regiao_atendimento", regioes), ("uf_atendimento", ufs),
    ("sexo", sexos), ("faixa_etaria", faixas),
]:
    if valores:
        apac_filtro = apac_filtro[apac_filtro[coluna_apac].isin(valores)]
        tempo_apac_filtro = tempo_apac_filtro[tempo_apac_filtro[coluna_apac].isin(valores)]
if segmentos:
    faixas_segmento = set()
    if "Pediátrico" in segmentos: faixas_segmento.update(["0–14", "15–19"])
    if "Adulto" in segmentos: faixas_segmento.update(["20–39", "40–59", "60–79", "80+"])
    apac_filtro = apac_filtro[apac_filtro.faixa_etaria.isin(faixas_segmento)]
    tempo_apac_filtro = tempo_apac_filtro[tempo_apac_filtro.faixa_etaria.isin(faixas_segmento)]

cirurgias_filtro = cirurgias[cirurgias.ano.between(*periodo)].copy()
for coluna_cirurgia, valores in [
    ("tipo_cancer", tipos), ("regiao_atendimento", regioes), ("uf_atendimento", ufs),
    ("sexo", sexos), ("faixa_etaria", faixas),
]:
    if valores:
        cirurgias_filtro = cirurgias_filtro[cirurgias_filtro[coluna_cirurgia].isin(valores)]
if segmentos:
    cirurgias_filtro = cirurgias_filtro[cirurgias_filtro.faixa_etaria.isin(faixas_segmento)]

rhc_ped_filtro = rhc_ped[rhc_ped.ano.between(*periodo)].copy()
if ufs:
    rhc_ped_filtro = rhc_ped_filtro[rhc_ped_filtro.uf_residencia.isin(ufs)]
if sexos:
    rhc_ped_filtro = rhc_ped_filtro[rhc_ped_filtro.sexo.isin(sexos)]
if faixas:
    faixas_rhc = {"0–14": {"0–4", "5–9", "10–14"}, "15–19": {"15–19"}}
    permitidas_rhc = set().union(*(faixas_rhc.get(faixa, set()) for faixa in faixas))
    rhc_ped_filtro = rhc_ped_filtro[rhc_ped_filtro.faixa_etaria.isin(permitidas_rhc)]
if segmentos and "Pediátrico" not in segmentos:
    rhc_ped_filtro = rhc_ped_filtro.iloc[0:0]

# Denominadores compatíveis com os filtros. A revisão 2024 do IBGE começa em 2000.
ufs_taxa = ufs or [uf for uf in base_uf.uf.unique() if uf != "Ignorada"]
sexos_taxa = [sexo for sexo in (sexos or ["Masculino", "Feminino"]) if sexo in {"Masculino", "Feminino"}]
faixas_taxa = set(faixas or populacao.faixa_etaria.unique())
if segmentos:
    permitidas = set()
    if "Pediátrico" in segmentos: permitidas.update(["0–14", "15–19"])
    if "Adulto" in segmentos: permitidas.update(["20–39", "40–59", "60–79", "80+"])
    faixas_taxa &= permitidas
anos_taxa = [
    ano for ano in range(max(2000, periodo[0]), min(int(populacao.ano.max()), periodo[1]) + 1)
    if ano not in anos_provisorios
]
pop_filtro = populacao[
    populacao.ano.isin(anos_taxa) & populacao.uf.isin(ufs_taxa)
    & populacao.sexo.isin(sexos_taxa) & populacao.faixa_etaria.isin(faixas_taxa)
].copy()
obitos_taxa = filtro[filtro.ano.isin(anos_taxa)].copy()
taxa_disponivel = bool(anos_taxa and not pop_filtro.empty and sexos_taxa and faixas_taxa)
taxa_periodo = soma(obitos_taxa) / pop_filtro.populacao.sum() * 100_000 if taxa_disponivel else None

st.title(":material/monitoring: Painel integrado de oncologia")
st.caption("Mortalidade por neoplasias malignas com dados reais do SIM/DATASUS")
st.info("O painel integra **SIM, IBGE, CNES, SIA/APAC, SIH/AIH e RHC**. Ele responde perguntas sobre mortalidade, "
        "estrutura, tratamentos e deslocamento municipal sem usar valores simulados.")
provisorios_no_recorte = {ano: situacao for ano, situacao in anos_provisorios.items() if periodo[0] <= ano <= periodo[1]}
if provisorios_no_recorte:
    descricao = "; ".join(f"{ano}: {situacao}" for ano, situacao in sorted(provisorios_no_recorte.items()))
    st.warning(f"O recorte inclui dados ainda incompletos ({descricao}). Eles entram nas contagens, mas foram excluídos das taxas para evitar denominadores anuais incompatíveis.")
if filtro.empty:
    st.warning("Nenhum óbito corresponde aos filtros selecionados.")
    st.stop()

abas = st.tabs(["Visão geral", "Mortalidade", "Perfil", "Incidência", "Estrutura", "Acesso",
                "Desfechos", "Pediatria e suporte", "Perguntas e fontes", "Metodologia"])

with abas[0]:
    serie_anual = filtro.groupby("ano")["obitos"].sum().reset_index()
    with st.container(horizontal=True):
        st.metric("Óbitos por câncer", numero(soma(filtro)), border=True, chart_data=serie_anual.obitos.tolist())
        st.metric("Taxa bruta média anual", f"{taxa_periodo:.1f} / 100 mil" if taxa_disponivel else "Indisponível", border=True)
        st.metric("Período", f"{periodo[0]}–{periodo[1]}", border=True)
        st.metric("Tipo com mais registros", filtro.groupby("tipo_cancer").obitos.sum().idxmax(), border=True)
        st.metric("UF com mais registros", filtro.groupby("uf").obitos.sum().idxmax(), border=True)
    esquerda, direita = st.columns([1.5, 1])
    serie = filtro.groupby(["ano", "tipo_cancer"], observed=True).obitos.sum().reset_index()
    esquerda.plotly_chart(px.line(serie, x="ano", y="obitos", color="tipo_cancer", markers=True,
        labels={"ano": "Ano", "obitos": "Óbitos", "tipo_cancer": "Tipo de câncer"},
        title="Evolução anual dos óbitos", color_discrete_sequence=CORES), key="geral_serie")
    with direita:
        barras(filtro, "tipo_cancer", "Óbitos por tipo de câncer", "geral_tipo")

with abas[1]:
    st.subheader("Mortalidade registrada no SIM")
    st.caption("Causa básica C00–C97. Taxas calculadas com as Projeções da População do IBGE — Revisão 2024.")
    medida = st.segmented_control("Medida", ["Taxa por 100 mil", "Contagem"], default="Taxa por 100 mil")
    periodicidade = st.segmented_control("Periodicidade", ["Ano", "Mês"], default="Ano")
    if medida == "Taxa por 100 mil" and periodicidade == "Mês":
        st.info("Taxas mensais não são exibidas: o denominador do IBGE é anual. Mostrando contagens mensais.")
    mostrar_taxa = medida == "Taxa por 100 mil" and periodicidade == "Ano" and taxa_disponivel
    if mostrar_taxa:
        serie = calcular_taxas(obitos_taxa, pop_filtro, ["ano"])
        tipos_ano = obitos_taxa.groupby(["ano", "tipo_cancer"], observed=True).obitos.sum().reset_index()
        serie = tipos_ano.merge(serie[["ano", "populacao"]], on="ano", how="inner")
        serie["taxa_100mil"] = serie.obitos / serie.populacao * 100_000
        eixo, valor, rotulo = "ano", "taxa_100mil", "Taxa por 100 mil habitantes"
    elif periodicidade == "Ano":
        serie = filtro.groupby(["ano", "tipo_cancer"], observed=True).obitos.sum().reset_index()
        eixo, valor, rotulo = "ano", "obitos", "Óbitos"
    else:
        serie = filtro.groupby(["ano", "mes", "tipo_cancer"], observed=True).obitos.sum().reset_index()
        serie["periodo"] = pd.to_datetime(dict(year=serie.ano, month=serie.mes, day=1))
        eixo, valor, rotulo = "periodo", "obitos", "Óbitos"
    st.plotly_chart(px.line(serie, x=eixo, y=valor, color="tipo_cancer", markers=periodicidade == "Ano",
        labels={eixo: "Período", valor: rotulo, "tipo_cancer": "Tipo de câncer"},
        color_discrete_sequence=CORES), key="mortalidade_tempo")
    if mostrar_taxa:
        territorio = calcular_taxas(obitos_taxa[obitos_taxa.uf != "Ignorada"], pop_filtro, ["uf"])
        mapa_regiao = sim[["uf", "regiao"]].drop_duplicates()
        territorio = territorio.merge(mapa_regiao, on="uf", how="left")
        valor_territorio, titulo_territorio = "taxa_100mil", "Taxa bruta média anual por UF"
    else:
        territorio = filtro.groupby(["regiao", "uf"], observed=True).obitos.sum().reset_index()
        valor_territorio, titulo_territorio = "obitos", "Distribuição territorial dos óbitos"
    st.plotly_chart(px.bar(territorio, x="uf", y=valor_territorio, color="regiao",
        labels={"uf": "UF de residência", valor_territorio: rotulo, "regiao": "Região"},
        title=titulo_territorio, color_discrete_sequence=CORES), key="mortalidade_territorio")
    if periodo[0] < 2000:
        st.warning("As taxas usam apenas 2000 em diante, limite inicial da Projeção IBGE — Revisão 2024. As contagens mantêm 1996–1999.")
    if provisorios_no_recorte:
        st.caption("As séries de contagem incluem 2025/2026 como disponibilizadas pelo SIM; as taxas terminam no último ano consolidado.")
    st.info("As taxas são brutas. A próxima melhoria metodológica será a padronização por idade para comparações territoriais.")

with abas[2]:
    st.subheader("Diferenças por idade, sexo e residência")
    perfil_medida = st.segmented_control("Exibir perfil como", ["Taxa por 100 mil", "Contagem"], default="Taxa por 100 mil")
    perfil_taxa = perfil_medida == "Taxa por 100 mil" and taxa_disponivel
    if perfil_taxa:
        perfil = calcular_taxas(obitos_taxa, pop_filtro, ["faixa_etaria", "sexo"])
        valor_perfil, titulo_perfil = "taxa_100mil", "Taxa específica por idade e sexo"
    else:
        perfil = filtro.groupby(["faixa_etaria", "sexo"], observed=True).obitos.sum().reset_index()
        valor_perfil, titulo_perfil = "obitos", "Óbitos por idade e sexo"
    st.plotly_chart(px.bar(perfil, x="faixa_etaria", y=valor_perfil, color="sexo", barmode="group",
        labels={"faixa_etaria": "Faixa etária", valor_perfil: "Taxa por 100 mil" if perfil_taxa else "Óbitos", "sexo": "Sexo"},
        title=titulo_perfil, color_discrete_sequence=CORES), key="perfil_idade_sexo")
    comparar = st.selectbox("Comparar tipos de câncer por", ["faixa_etaria", "sexo", "regiao", "uf"])
    if perfil_taxa:
        pop_cruzamento = pop_filtro.copy()
        if comparar == "regiao":
            pop_cruzamento = pop_cruzamento.merge(sim[["uf", "regiao"]].drop_duplicates(), on="uf", how="left")
        denominador = pop_cruzamento.groupby(comparar, observed=True).populacao.sum().reset_index()
        cruzamento = obitos_taxa.groupby([comparar, "tipo_cancer"], observed=True).obitos.sum().reset_index()
        cruzamento = cruzamento.merge(denominador, on=comparar, how="inner")
        cruzamento["taxa_100mil"] = cruzamento.obitos / cruzamento.populacao * 100_000
        valor_cruzamento = "taxa_100mil"
    else:
        cruzamento = filtro.groupby([comparar, "tipo_cancer"], observed=True).obitos.sum().reset_index()
        valor_cruzamento = "obitos"
    st.plotly_chart(px.bar(cruzamento, x=comparar, y=valor_cruzamento, color="tipo_cancer", barmode="group",
        labels={comparar: comparar.replace("_", " ").title(), valor_cruzamento: "Taxa por 100 mil" if perfil_taxa else "Óbitos", "tipo_cancer": "Tipo de câncer"},
        color_discrete_sequence=CORES), key="perfil_comparacao")

with abas[3]:
    st.subheader("Incidência do câncer")
    pendencia("Incidência por tipo, tempo e perfil", "O SIM registra mortes, não casos novos. Não é válido "
              "usar óbitos como incidência. A pergunta exige casos novos, território coberto e população do mesmo período.",
              "RCBP/INCA + população IBGE")

with abas[4]:
    st.subheader("Estrutura assistencial")
    competencia = metadados_estrutura["competencia"]
    st.caption(f"Habilitações ativas no CNES — competência {competencia[4:6]}/{competencia[:4]}. Os filtros de região e UF da barra lateral também se aplicam aqui.")
    if estrutura_filtro.empty:
        st.warning("Nenhum estabelecimento corresponde ao recorte territorial.")
    else:
        with st.container(horizontal=True):
            st.metric("Estabelecimentos habilitados", numero(len(estrutura_filtro)), border=True)
            st.metric("CACON ou UNACON", numero(estrutura_filtro.cacon_unacon.sum()), border=True)
            st.metric("Com radioterapia", numero(estrutura_filtro.radioterapia.sum()), border=True)
            st.metric("Com oncologia pediátrica", numero(estrutura_filtro.pediatria.sum()), border=True)
        esquerda, direita = st.columns(2)
        por_uf = estrutura_filtro.groupby(["regiao", "uf"], observed=True).size().reset_index(name="estabelecimentos")
        esquerda.plotly_chart(px.bar(por_uf, x="uf", y="estabelecimentos", color="regiao",
            labels={"uf": "UF", "estabelecimentos": "Estabelecimentos", "regiao": "Região"},
            title="Estabelecimentos por UF", color_discrete_sequence=CORES), key="estrutura_uf")
        por_tipo = estrutura_filtro.groupby("tipo_principal", observed=True).size().sort_values().reset_index(name="estabelecimentos")
        direita.plotly_chart(px.bar(por_tipo, x="estabelecimentos", y="tipo_principal", orientation="h",
            labels={"estabelecimentos": "Estabelecimentos", "tipo_principal": ""},
            title="Habilitação principal", color="estabelecimentos", color_continuous_scale="Greens"), key="estrutura_tipo")
        por_natureza = estrutura_filtro.groupby("natureza_juridica", observed=True).size().reset_index(name="estabelecimentos")
        st.plotly_chart(px.bar(por_natureza, x="natureza_juridica", y="estabelecimentos", color="natureza_juridica",
            labels={"natureza_juridica": "Natureza jurídica", "estabelecimentos": "Estabelecimentos"},
            title="Distribuição por natureza jurídica", color_discrete_sequence=CORES), key="estrutura_natureza")
        busca = st.text_input("Buscar estabelecimento, município ou CNES", key="busca_estrutura")
        tabela = estrutura_filtro.copy()
        if busca:
            alvo = (tabela.estabelecimento + " " + tabela.municipio + " " + tabela.cnes).str.contains(busca, case=False, na=False)
            tabela = tabela[alvo]
        exibicao = tabela[["cnes", "estabelecimento", "municipio", "uf", "tipo_principal", "gestao", "natureza_juridica"]].rename(columns={
            "cnes": "CNES", "estabelecimento": "Estabelecimento", "municipio": "Município", "uf": "UF",
            "tipo_principal": "Habilitação principal", "gestao": "Gestão", "natureza_juridica": "Natureza jurídica",
        })
        st.dataframe(exibicao, hide_index=True)
        st.download_button("Baixar estrutura filtrada (CSV)", exibicao.to_csv(index=False).encode("utf-8-sig"),
                           "estrutura_oncologica_cnes.csv", "text/csv", icon=":material/download:")
    pendencia("Uso ou ocupação", "Exige produção e um denominador validado de capacidade.", "CNES + SIA/SIH + capacidade")

with abas[5]:
    st.subheader("Acesso ao diagnóstico e tratamento")
    competencia_apac = metadados_apac["ultima_competencia"]
    st.caption(f"SIA/APAC de 01/2025 a {competencia_apac[4:6]}/{competencia_apac[:4]}. Território corresponde ao local de atendimento.")
    if apac_filtro.empty:
        st.warning("Não há APACs no recorte selecionado. A base disponível começa em 2025.")
    else:
        total_apacs = int(apac_filtro.apacs.sum())
        quimio = int(apac_filtro.loc[apac_filtro.modalidade == "Quimioterapia", "apacs"].sum())
        radio = int(apac_filtro.loc[apac_filtro.modalidade == "Radioterapia", "apacs"].sum())
        total_tempos = int(tempo_apac_filtro.pacientes.sum())
        ate_60 = int(tempo_apac_filtro.loc[tempo_apac_filtro.faixa_tempo.isin(["Até 30 dias", "31–60 dias"]), "pacientes"].sum())
        with st.container(horizontal=True):
            st.metric("Registros mensais de APAC", numero(total_apacs), border=True)
            st.metric("Quimioterapia", numero(quimio), border=True)
            st.metric("Radioterapia", numero(radio), border=True)
            st.metric("Início em até 60 dias", f"{ate_60 / total_tempos:.1%}" if total_tempos else "Indisponível", border=True)
            st.metric("Pessoas no indicador de tempo", numero(total_tempos), border=True)
        serie_apac = apac_filtro.groupby(["ano", "mes", "modalidade"], observed=True).apacs.sum().reset_index()
        serie_apac["competencia"] = pd.to_datetime(dict(year=serie_apac.ano, month=serie_apac.mes, day=1))
        st.plotly_chart(px.line(serie_apac, x="competencia", y="apacs", color="modalidade", markers=True,
            labels={"competencia": "Competência", "apacs": "Registros mensais de APAC", "modalidade": "Modalidade"},
            title="Produção ambulatorial oncológica", color_discrete_sequence=CORES), key="acesso_serie_apac")
        esquerda, direita = st.columns(2)
        espera = tempo_apac_filtro.groupby(["faixa_tempo", "modalidade"], observed=True).pacientes.sum().reset_index()
        esquerda.plotly_chart(px.bar(espera, x="faixa_tempo", y="pacientes", color="modalidade", barmode="group",
            labels={"faixa_tempo": "Intervalo", "pacientes": "Pessoas", "modalidade": "Modalidade"},
            title="Intervalo entre diagnóstico e tratamento", color_discrete_sequence=CORES), key="acesso_tempo")
        territorio_apac = apac_filtro.groupby(["regiao_atendimento", "uf_atendimento", "modalidade"], observed=True).apacs.sum().reset_index()
        direita.plotly_chart(px.bar(territorio_apac, x="uf_atendimento", y="apacs", color="modalidade", barmode="group",
            labels={"uf_atendimento": "UF do atendimento", "apacs": "Registros mensais de APAC", "modalidade": "Modalidade"},
            title="Produção por UF de atendimento", color_discrete_sequence=CORES), key="acesso_uf")
        por_cancer_apac = apac_filtro.groupby(["tipo_cancer", "modalidade"], observed=True).apacs.sum().reset_index()
        st.dataframe(por_cancer_apac.rename(columns={"tipo_cancer": "Tipo de câncer", "modalidade": "Modalidade", "apacs": "Registros de APAC"}), hide_index=True)
        st.info("Cada linha de produção representa um registro mensal de APAC, não uma pessoa ou sessão. O indicador de tempo deduplica pessoas, exige início do tratamento dentro do recorte e usa as datas registradas na APAC.")
    st.divider()
    st.subheader("Cirurgias oncológicas e deslocamento")
    if cirurgias_filtro.empty:
        st.warning("Não há cirurgias do SIH no recorte selecionado. A base disponível começa em 2025.")
    else:
        total_cirurgias = int(cirurgias_filtro.internacoes.sum())
        fora_cirurgia = int(cirurgias_filtro.loc[cirurgias_filtro.fora_municipio, "internacoes"].sum())
        dist_validas_cirurgia = int(cirurgias_filtro.distancias_validas.sum())
        distancia_media_cirurgia = cirurgias_filtro.soma_distancia_km.sum() / dist_validas_cirurgia
        total_apac_dist = int(apac_filtro.apacs.sum()) if not apac_filtro.empty else 0
        fora_apac = int(apac_filtro.loc[apac_filtro.fora_municipio, "apacs"].sum()) if total_apac_dist else 0
        dist_validas_apac = int(apac_filtro.distancias_validas.sum()) if total_apac_dist else 0
        distancia_media_apac = apac_filtro.soma_distancia_km.sum() / dist_validas_apac if dist_validas_apac else None
        with st.container(horizontal=True):
            st.metric("Internações com cirurgia oncológica", numero(total_cirurgias), border=True)
            st.metric("Cirurgias fora do município", f"{fora_cirurgia / total_cirurgias:.1%}", border=True)
            st.metric("Distância média — cirurgia", f"{distancia_media_cirurgia:.1f} km", border=True)
            st.metric("APACs fora do município", f"{fora_apac / total_apac_dist:.1%}" if total_apac_dist else "Indisponível", border=True)
            st.metric("Distância média — APAC", f"{distancia_media_apac:.1f} km" if distancia_media_apac is not None else "Indisponível", border=True)
        serie_cirurgia = cirurgias_filtro.groupby(["ano", "mes"], observed=True).internacoes.sum().reset_index()
        serie_cirurgia["competencia"] = pd.to_datetime(dict(year=serie_cirurgia.ano, month=serie_cirurgia.mes, day=1))
        st.plotly_chart(px.line(serie_cirurgia, x="competencia", y="internacoes", markers=True,
            labels={"competencia": "Competência", "internacoes": "Internações"}, title="Cirurgias oncológicas no SIH"), key="acesso_cirurgias")
        col_dist1, col_dist2 = st.columns(2)
        dist_cirurgia = cirurgias_filtro.groupby("faixa_distancia", observed=True).internacoes.sum().reset_index()
        col_dist1.plotly_chart(px.bar(dist_cirurgia, x="faixa_distancia", y="internacoes",
            labels={"faixa_distancia": "Distância estimada", "internacoes": "Internações"},
            title="Deslocamento para cirurgia", color="internacoes", color_continuous_scale="Greens"), key="dist_cirurgia")
        dist_apac = apac_filtro.groupby(["faixa_distancia", "modalidade"], observed=True).apacs.sum().reset_index() if not apac_filtro.empty else pd.DataFrame()
        if not dist_apac.empty:
            col_dist2.plotly_chart(px.bar(dist_apac, x="faixa_distancia", y="apacs", color="modalidade", barmode="group",
                labels={"faixa_distancia": "Distância estimada", "apacs": "Registros de APAC", "modalidade": "Modalidade"},
                title="Deslocamento para quimio/radioterapia", color_discrete_sequence=CORES), key="dist_apac")
        st.info("Distância em linha reta entre as coordenadas das sedes dos municípios de residência e atendimento. Não representa endereço do paciente nem trajeto rodoviário.")
    pendencia("Diagnosticados versus tratados", "Exige identificação de caso e início do tratamento.", "Painel Oncológico/RHC")
    pendencia("Fila APS → regulador → prestador", "Exige timestamps dos eventos locais de regulação.", "Regulador municipal")

with abas[6]:
    st.subheader("Desfechos")
    st.success("Disponível: óbitos por tipo de câncer, período, idade, sexo e residência.")
    pendencia("Cura, recorrência e resposta", "Esses eventos não são registrados no SIM.", "RHC/prontuário")
    pendencia("Sobrevida global e livre de doença", "Exige coorte, data inicial, seguimento, óbito vinculado e censura.", "RHC/prontuário + SIM")
    pendencia("Tratamento e desfecho", "A análise precisa controlar estágio, gravidade e seleção do paciente.", "Base clínica longitudinal")

with abas[7]:
    st.subheader("Câncer pediátrico")
    ped = filtro[filtro.segmento == "Pediátrico"]
    with st.container(horizontal=True):
        st.metric("Óbitos de 0 a 19 anos", numero(soma(ped)), border=True)
        st.metric("Participação nos óbitos filtrados", f"{soma(ped) / soma(filtro):.1%}", border=True)
    if not ped.empty:
        barras(ped, "tipo_cancer", "Mortalidade pediátrica por grupo derivado da CID-10", "ped_tipo")
    st.divider()
    st.subheader("Casos hospitalares por CICI/ICCC-3")
    st.caption("Integrador RHC/INCA, 2019–2023. Classificação derivada de topografia, morfologia e comportamento CID-O-3.")
    st.warning("A base pública usada exclui São Paulo e 2023 está parcial. RHC descreve casos atendidos pelos hospitais participantes e não mede incidência populacional.")
    if rhc_ped_filtro.empty:
        st.info("Não há casos do RHC pediátrico no período ou recorte territorial selecionado.")
    else:
        total_rhc = int(rhc_ped_filtro.casos.sum())
        classificados = int(rhc_ped_filtro.loc[rhc_ped_filtro.recode_iccc != "999", "casos"].sum())
        com_tratamento = int(rhc_ped_filtro.loc[rhc_ped_filtro.tratamento_com_data, "casos"].sum())
        tempos_validos = rhc_ped_filtro[~rhc_ped_filtro.faixa_tempo.isin([
            "Sem intervalo calculável", "Tratamento anterior ao diagnóstico informado"
        ])]
        total_tempo = int(tempos_validos.casos.sum())
        ate_60 = int(tempos_validos.loc[tempos_validos.faixa_tempo.isin(["Até 30 dias", "31–60 dias"]), "casos"].sum())
        with st.container(horizontal=True):
            st.metric("Casos registrados no RHC", numero(total_rhc), border=True)
            st.metric("Classificados na ICCC-3", f"{classificados / total_rhc:.1%}", border=True)
            st.metric("Com data de tratamento", f"{com_tratamento / total_rhc:.1%}", border=True)
            st.metric("Tratamento em até 60 dias", f"{ate_60 / total_tempo:.1%}" if total_tempo else "Indisponível", border=True)
        grupos_rhc = rhc_ped_filtro.groupby("grupo_iccc", observed=True).casos.sum().sort_values().reset_index()
        st.plotly_chart(px.bar(grupos_rhc, x="casos", y="grupo_iccc", orientation="h", color="casos",
            labels={"casos": "Casos registrados", "grupo_iccc": ""}, title="Casos por grupo CICI/ICCC-3",
            color_continuous_scale="Greens"), key="ped_iccc_grupos")
        grupos_classificados = rhc_ped_filtro.loc[rhc_ped_filtro.recode_iccc != "999"].groupby(
            "grupo_iccc", observed=True).casos.sum().sort_values(ascending=False)
        if not grupos_classificados.empty:
            grupo_detalhado = st.selectbox("Grupo CICI/ICCC-3 para detalhar", grupos_classificados.index.tolist())
            subgrupos_rhc = rhc_ped_filtro[
                rhc_ped_filtro.grupo_iccc == grupo_detalhado
            ].groupby("subgrupo_iccc", observed=True).casos.sum().sort_values().reset_index()
            st.plotly_chart(px.bar(subgrupos_rhc, x="casos", y="subgrupo_iccc", orientation="h", color="casos",
                labels={"casos": "Casos registrados", "subgrupo_iccc": ""},
                title=f"Subgrupos de {grupo_detalhado}", color_continuous_scale="Greens"), key="ped_iccc_subgrupos")
        esquerda_rhc, direita_rhc = st.columns(2)
        serie_rhc = rhc_ped_filtro.groupby("ano", observed=True).casos.sum().reset_index()
        esquerda_rhc.plotly_chart(px.line(serie_rhc, x="ano", y="casos", markers=True,
            labels={"ano": "Ano da primeira consulta", "casos": "Casos registrados"},
            title="Casos pediátricos registrados por ano"), key="ped_iccc_serie")
        tempos_rhc = rhc_ped_filtro.groupby("faixa_tempo", observed=True).casos.sum().reset_index()
        direita_rhc.plotly_chart(px.bar(tempos_rhc, x="faixa_tempo", y="casos", color="casos",
            labels={"faixa_tempo": "Intervalo registrado", "casos": "Casos"},
            title="Intervalo entre diagnóstico e início do tratamento", color_continuous_scale="Greens"), key="ped_iccc_tempo")
        st.info("O indicador de tratamento usa a presença de data de início no RHC. Casos sem data e datas anteriores ao diagnóstico informado não entram no percentual de até 60 dias.")
        st.subheader("Primeiro tratamento no hospital")
        tratamentos_rhc = rhc_ped_filtro.groupby("primeiro_tratamento", observed=True).casos.sum().sort_values().reset_index()
        st.plotly_chart(px.bar(tratamentos_rhc, x="casos", y="primeiro_tratamento", orientation="h", color="casos",
            labels={"casos": "Casos registrados", "primeiro_tratamento": ""},
            title="Modalidade ou combinação registrada como primeiro tratamento", color_continuous_scale="Greens"),
            key="ped_iccc_tratamento")
        sem_tratamento = rhc_ped_filtro[rhc_ped_filtro.primeiro_tratamento == "Nenhum tratamento no hospital"]
        if not sem_tratamento.empty:
            razoes_rhc = sem_tratamento.groupby("razao_nao_tratamento", observed=True).casos.sum().sort_values().reset_index()
            st.plotly_chart(px.bar(razoes_rhc, x="casos", y="razao_nao_tratamento", orientation="h", color="casos",
                labels={"casos": "Casos", "razao_nao_tratamento": ""},
                title="Razão registrada para ausência de tratamento no hospital", color_continuous_scale="Greens"),
                key="ped_iccc_razao")
        with st.expander("Qualidade e completude dos registros"):
            sem_classificacao = total_rhc - classificados
            sem_data = int(rhc_ped_filtro.loc[rhc_ped_filtro.faixa_tempo == "Sem intervalo calculável", "casos"].sum())
            data_inconsistente = int(rhc_ped_filtro.loc[
                rhc_ped_filtro.faixa_tempo == "Tratamento anterior ao diagnóstico informado", "casos"].sum())
            uf_ignorada = int(rhc_ped_filtro.loc[
                rhc_ped_filtro.uf_residencia.isin(["", "Ignorada", "99"]), "casos"].sum())
            tratamento_ignorado = int(rhc_ped_filtro.loc[
                rhc_ped_filtro.primeiro_tratamento == "Sem informação", "casos"].sum())
            qualidade_rhc = pd.DataFrame([
                ["Sem classificação ICCC-3", sem_classificacao, sem_classificacao / total_rhc],
                ["Sem intervalo diagnóstico–tratamento calculável", sem_data, sem_data / total_rhc],
                ["Data de tratamento anterior ao diagnóstico informado", data_inconsistente, data_inconsistente / total_rhc],
                ["UF de residência ignorada", uf_ignorada, uf_ignorada / total_rhc],
                ["Primeiro tratamento sem informação", tratamento_ignorado, tratamento_ignorado / total_rhc],
            ], columns=["Indicador", "Casos", "Percentual"])
            st.dataframe(qualidade_rhc, hide_index=True, column_config={
                "Percentual": st.column_config.NumberColumn("Percentual", format="percent")
            })
    pendencia("Casas de apoio", "Exige cadastro georreferenciado e vínculo com centros pediátricos.", "Cadastro local + CNES")
    pendencia("Qualidade de vida, escola e doenças secundárias", "Não são inferíveis de registros de mortalidade.", "Prontuário + pesquisa primária")

with abas[8]:
    st.subheader("Cobertura das perguntas do documento")
    cobertura = pd.DataFrame([
        ["Incidência por tipo, tempo e perfil", "Aguardando fonte", "RCBP + IBGE"],
        ["Hospitais, natureza jurídica e serviços habilitados", "Disponível", "CNES/SAES"],
        ["Uso e ocupação da estrutura", "Aguardando produção/capacidade", "CNES + SIA/SIH"],
        ["Tempo entre diagnóstico e tratamento entre APACs", "Disponível", "SIA/APAC"],
        ["Proporção diagnosticada que foi tratada", "Aguardando coorte de casos", "Painel Oncológico/RHC"],
        ["Quimioterapia e radioterapia ambulatoriais", "Disponível", "SIA/APAC"],
        ["Cirurgias oncológicas", "Disponível", "SIH/AIH"],
        ["Distância municipal residência–tratamento", "Disponível (estimativa)", "SIA/SIH + coordenadas municipais"],
        ["Mortalidade por tipo, tempo, idade, sexo e local", "Disponível", "SIM"],
        ["Taxa populacional de mortalidade", "Disponível (bruta/específica)", "SIM + IBGE"],
        ["Cura, recorrência e sobrevida", "Aguardando fonte", "Coorte clínica + SIM"],
        ["Fila de regulação", "Aguardando fonte", "Regulador municipal"],
        ["ICCC-3", "Disponível para casos pediátricos hospitalares", "RHC com CID-O-3"],
        ["Acolhimento, vida social/escolar e efeitos tardios", "Aguardando fonte", "Cadastros/prontuário/pesquisa"],
    ], columns=["Pergunta", "Situação", "Fonte mínima"])
    st.dataframe(cobertura, hide_index=True)
    st.caption("Perguntas de custo foram excluídas desta versão, conforme solicitado.")

with abas[9]:
    st.subheader("Fonte e interpretação")
    st.table({"Fonte": metadados["fonte"], "Critério": metadados["criterio"],
        "Período do arquivo": f"{metadados['periodo'][0]}–{metadados['periodo'][1]}",
        "Arquivos nacionais processados": str(metadados["arquivos"]),
        "Total de óbitos oncológicos": numero(metadados["total_obitos"])}, border="horizontal", width="content")
    if anos_provisorios:
        st.table({f"SIM {ano}": situacao for ano, situacao in sorted(anos_provisorios.items())},
                 border="horizontal", width="content")
    st.table({"Denominador": metadados_pop["fonte"], "Referência": metadados_pop["referencia"],
        "Período populacional usado": f"{metadados_pop['periodo'][0]}–{min(metadados_pop['periodo'][1], int(sim.ano.max()))}"},
        border="horizontal", width="content")
    st.table({"Estrutura": metadados_estrutura["fonte"], "Competência": metadados_estrutura["competencia"],
        "Critério": metadados_estrutura["criterio"], "Identificação nominal": metadados_estrutura["nomes_fonte"]},
        border="horizontal", width="content")
    st.table({"Tratamento ambulatorial": metadados_apac["fonte"], "Período": f"{metadados_apac['periodo'][0]}–{metadados_apac['periodo'][1]}",
        "Última competência": metadados_apac["ultima_competencia"], "Limite": metadados_apac["limite"]},
        border="horizontal", width="content")
    st.table({"Cirurgias": metadados_cirurgias["fonte"], "Critério": metadados_cirurgias["criterio"],
        "Última competência": metadados_cirurgias["ultima_competencia"], "Distância": metadados_cirurgias["distancia"]},
        border="horizontal", width="content")
    st.table({"Oncologia pediátrica": metadados_rhc["fonte"],
        "Período": f"{metadados_rhc['periodo'][0]}–{metadados_rhc['periodo'][1]}",
        "Cobertura": metadados_rhc["cobertura_geografica"], "Classificação": metadados_rhc["classificacao"],
        "Unidade de análise": metadados_rhc["unidade"]}, border="horizontal", width="content")
    st.markdown("- Foram usados os arquivos nacionais `DOBR`; os estaduais não foram somados novamente.\n"
                "- Tipo de câncer é derivado da causa básica CID-10.\n"
                "- Contagem de óbitos não é incidência nem letalidade.\n"
                "- Os dados preliminares/prévios entram nas contagens, mas não nas taxas anuais.\n"
                "- As taxas usam pessoa-anos projetadas pelo IBGE e ainda não são padronizadas por idade.\n"
                "- A projeção IBGE — Revisão 2024 cobre 2000 em diante; 1996–1999 permanecem apenas em contagens.\n"
                "- Habilitação no CNES indica autorização cadastrada; não mede produção, capacidade ou ocupação.")
    st.download_button("Baixar recorte agregado (CSV)", filtro.to_csv(index=False).encode("utf-8-sig"),
                       "sim_oncologia_filtrado.csv", "text/csv", icon=":material/download:")
