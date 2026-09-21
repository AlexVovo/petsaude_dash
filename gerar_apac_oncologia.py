"""Baixa e agrega APACs de quimioterapia e radioterapia do SIA/DATASUS."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]
URL_COORDENADAS = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"
REGIOES = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Centro-Oeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
}


def tipo_cancer(cid: pd.Series) -> pd.Series:
    numero = pd.to_numeric(cid.astype("string").str.extract(r"^C(\d{2})", expand=False), errors="coerce")
    condicoes = [
        cond.fillna(False).to_numpy(dtype=bool) for cond in [
            numero.eq(50), numero.eq(61), numero.between(18, 21), numero.between(33, 34),
            numero.eq(53), numero.between(91, 95), numero.between(70, 72), numero.between(81, 86),
        ]
    ]
    rotulos = ["Mama", "Próstata", "Colorretal", "Pulmão", "Colo do útero", "Leucemias", "SNC", "Linfomas"]
    return pd.Series(np.select(condicoes, rotulos, default="Outros diagnósticos oncológicos"), index=cid.index)


def idade_anos(unidade: pd.Series, quantidade: pd.Series) -> pd.Series:
    unidade = pd.to_numeric(unidade, errors="coerce")
    quantidade = pd.to_numeric(quantidade, errors="coerce")
    return pd.Series(np.where(unidade.eq(4), quantidade, np.where(unidade.isin([1, 2, 3]), 0, np.nan)), index=unidade.index)


def caminho_real(cache: Path, caminho: object) -> Path:
    arquivo = Path(str(caminho))
    return arquivo if arquivo.exists() else cache / "downloads" / "ducklake" / "sia" / arquivo.name


def carregar_coordenadas(caminho: Path) -> pd.DataFrame:
    if not caminho.exists():
        from urllib.request import urlopen
        with urlopen(URL_COORDENADAS, timeout=90) as resposta:
            caminho.write_bytes(resposta.read())
    dados = pd.read_csv(caminho, dtype={"codigo_ibge": "string"})
    dados["codigo_municipio"] = dados.codigo_ibge.str[:6]
    return dados[["codigo_municipio", "latitude", "longitude"]].drop_duplicates("codigo_municipio")


def haversine(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def baixar_com_retentativa(sia, uf: str, ano: int, meses: list[int], grupo: str):
    erro = None
    for tentativa in range(1, 4):
        try:
            return sia(uf, ano, meses, group=grupo)
        except Exception as atual:
            erro = atual
            print(f"Tentativa {tentativa}/3 falhou para {grupo}/{uf}/{ano}; retomando em instantes.", flush=True)
            time.sleep(2 * tentativa)
    raise RuntimeError(f"Falha ao baixar {grupo}/{uf}/{ano}") from erro


def gerar(saida: Path, cache: Path, coordenadas: Path, inicio: int, fim: int, mes_final: int) -> None:
    os.environ["PYSUS_CACHEPATH"] = str(cache.resolve())
    from pysus.ftp import sia

    quadros = []
    for uf in UFS:
        for grupo, modalidade in [("AQ", "Quimioterapia"), ("AR", "Radioterapia")]:
            caminhos = []
            for ano in range(inicio, fim + 1):
                meses = list(range(1, mes_final + 1)) if ano == fim else list(range(1, 13))
                print(f"SIA/APAC {modalidade} {uf} {ano}", flush=True)
                esperados = [cache / "downloads" / "ducklake" / "sia" / f"{grupo}{uf}{str(ano)[2:]}{mes:02d}.parquet" for mes in meses]
                existentes = [arquivo for arquivo in esperados if arquivo.exists()]
                if len(existentes) == len(esperados):
                    caminhos.extend(existentes)
                else:
                    caminhos.extend(baixar_com_retentativa(sia, uf, ano, meses, grupo))
            for caminho in caminhos:
                arquivo = caminho_real(cache, caminho)
                campos_especificos = [f"{grupo}_CID10", f"{grupo}_DTIDEN", f"{grupo}_DTINTR"]
                colunas = [
                    "AP_MVM", "AP_CODUNI", "AP_AUTORIZ", "AP_CNSPCN", "AP_UFMUN", "AP_MUNPCN",
                    "AP_COIDADE", "AP_NUIDADE", "AP_SEXO", "AP_PRIPAL", *campos_especificos,
                ]
                dados = pd.read_parquet(arquivo, columns=colunas)
                dados = dados.rename(columns={
                    f"{grupo}_CID10": "cid", f"{grupo}_DTIDEN": "data_diagnostico",
                    f"{grupo}_DTINTR": "data_inicio",
                })
                dados["modalidade"] = modalidade
                dados["uf_atendimento"] = uf
                quadros.append(dados)

    bruto = pd.concat(quadros, ignore_index=True)
    bruto["ano"] = pd.to_numeric(bruto.AP_MVM.str[:4], errors="coerce").astype("Int64")
    bruto["mes"] = pd.to_numeric(bruto.AP_MVM.str[4:6], errors="coerce").astype("Int64")
    bruto["regiao_atendimento"] = bruto.uf_atendimento.map(REGIOES)
    bruto["codigo_residencia"] = bruto.AP_MUNPCN.astype("string").str.zfill(6).str[:6]
    bruto["codigo_atendimento"] = bruto.AP_UFMUN.astype("string").str.zfill(6).str[:6]
    bruto["tipo_cancer"] = tipo_cancer(bruto.cid)
    bruto["sexo"] = bruto.AP_SEXO.map({"M": "Masculino", "F": "Feminino"}).fillna("Ignorado")
    idade = idade_anos(bruto.AP_COIDADE, bruto.AP_NUIDADE)
    bruto["faixa_etaria"] = pd.cut(
        idade, [-1, 14, 19, 39, 59, 79, np.inf],
        labels=["0–14", "15–19", "20–39", "40–59", "60–79", "80+"],
    ).astype("string").fillna("Ignorada")

    coords = carregar_coordenadas(coordenadas)
    bruto = bruto.merge(coords.add_suffix("_residencia"), left_on="codigo_residencia", right_on="codigo_municipio_residencia", how="left")
    bruto = bruto.merge(coords.add_suffix("_atendimento"), left_on="codigo_atendimento", right_on="codigo_municipio_atendimento", how="left")
    bruto["distancia_km"] = haversine(bruto.latitude_residencia, bruto.longitude_residencia,
                                       bruto.latitude_atendimento, bruto.longitude_atendimento)
    bruto["fora_municipio"] = bruto.codigo_residencia.ne(bruto.codigo_atendimento)
    bruto["faixa_distancia"] = pd.cut(bruto.distancia_km, [-1, 0.01, 50, 100, 200, math.inf],
        labels=["Mesmo município", "Até 50 km", "51–100 km", "101–200 km", "Mais de 200 km"]
    ).astype("string").fillna("Distância indisponível")

    dimensoes = ["ano", "mes", "modalidade", "regiao_atendimento", "uf_atendimento", "tipo_cancer", "sexo", "faixa_etaria", "faixa_distancia", "fora_municipio"]
    producao = bruto.groupby(dimensoes, observed=True, dropna=False).agg(
        apacs=("AP_AUTORIZ", "size"), soma_distancia_km=("distancia_km", "sum"),
        distancias_validas=("distancia_km", "count"),
    ).reset_index()

    # Uma pessoa pode ter a mesma APAC em várias competências e receber renovações.
    # O identificador do paciente é usado somente para deduplicar e nunca é exportado.
    identificador = bruto.AP_CNSPCN.astype("string").str.strip()
    valido = identificador.notna() & identificador.ne("") & identificador.ne("0")
    bruto["_chave_paciente"] = np.where(valido, identificador, "APAC:" + bruto.AP_AUTORIZ.astype("string"))
    inicios = bruto.sort_values("AP_MVM").drop_duplicates(["modalidade", "_chave_paciente"])
    diagnostico = pd.to_datetime(inicios.data_diagnostico, format="%Y%m%d", errors="coerce")
    tratamento = pd.to_datetime(inicios.data_inicio, format="%Y%m%d", errors="coerce")
    inicios["dias_ate_tratamento"] = (tratamento - diagnostico).dt.days
    limite_inicial = pd.Timestamp(inicio, 1, 1)
    limite_final = pd.Timestamp(fim, mes_final, 1) + pd.offsets.MonthEnd(0)
    # Exclui tratamentos iniciados antes da janela, que são casos prevalentes em continuidade.
    inicios = inicios[
        inicios.dias_ate_tratamento.between(0, 3650)
        & tratamento.between(limite_inicial, limite_final)
    ].copy()
    inicios["faixa_tempo"] = pd.cut(
        inicios.dias_ate_tratamento, [-1, 30, 60, 90, 180, 3650],
        labels=["Até 30 dias", "31–60 dias", "61–90 dias", "91–180 dias", "Mais de 180 dias"],
    ).astype("string")
    dimensoes_tempo = dimensoes + ["faixa_tempo"]
    tempos = inicios.groupby(dimensoes_tempo, observed=True, dropna=False).agg(
        pacientes=("_chave_paciente", "size"), soma_dias=("dias_ate_tratamento", "sum"),
    ).reset_index()

    payload = {
        "metadados": {
            "fonte": "SIA/SUS — APAC de quimioterapia (AQ) e radioterapia (AR)",
            "periodo": [inicio, fim],
            "ultima_competencia": f"{fim}{mes_final:02d}",
            "unidade_producao": "registros mensais de APAC",
            "unidade_tempo": "pessoas deduplicadas, com início do tratamento dentro do recorte e datas válidas",
            "limite": "Não representa incidência, pessoas únicas em toda a produção nem número de sessões.",
            "distancia": "linha reta entre coordenadas das sedes municipais; não representa trajeto rodoviário",
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        },
        "producao": producao.to_dict(orient="records"),
        "tempo": tempos.to_dict(orient="records"),
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_suffix(saida.suffix + ".tmp")
    temporario.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporario.replace(saida)
    print(f"Criado {saida}: {int(producao.apacs.sum()):,} APACs; {int(tempos.pacientes.sum()):,} pessoas com intervalo válido")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicio", type=int, default=2025)
    parser.add_argument("--fim", type=int, default=2026)
    parser.add_argument("--mes-final", type=int, default=6)
    parser.add_argument("--saida", type=Path, default=Path("dados/apac_oncologia.json"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/pysus"))
    parser.add_argument("--coordenadas", type=Path, default=Path("dados/municipios_coordenadas.csv"))
    args = parser.parse_args()
    gerar(args.saida.resolve(), args.cache, args.coordenadas, args.inicio, args.fim, args.mes_final)


if __name__ == "__main__":
    main()
