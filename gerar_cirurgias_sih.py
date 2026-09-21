"""Baixa e agrega cirurgias oncológicas do SIH/SUS (AIH)."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd


UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]
UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
REGIOES = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Centro-Oeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
}
URL_COORDENADAS = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"


def tipo_cancer(cid: pd.Series) -> pd.Series:
    numero = pd.to_numeric(cid.astype("string").str.extract(r"^C(\d{2})", expand=False), errors="coerce")
    condicoes = [cond.fillna(False).to_numpy(dtype=bool) for cond in [
        numero.eq(50), numero.eq(61), numero.between(18, 21), numero.between(33, 34), numero.eq(53),
        numero.between(91, 95), numero.between(70, 72), numero.between(81, 86),
    ]]
    return pd.Series(np.select(condicoes,
        ["Mama", "Próstata", "Colorretal", "Pulmão", "Colo do útero", "Leucemias", "SNC", "Linfomas"],
        default="Outras neoplasias malignas"), index=cid.index)


def baixar_com_retentativa(sih, uf: str, ano: int, meses: list[int]):
    erro = None
    for tentativa in range(1, 4):
        try:
            return sih(uf, ano, meses, group="RD")
        except Exception as atual:
            erro = atual
            print(f"Tentativa {tentativa}/3 falhou para RD/{uf}/{ano}; retomando.", flush=True)
            time.sleep(2 * tentativa)
    raise RuntimeError(f"Falha ao baixar RD/{uf}/{ano}") from erro


def caminho_real(cache: Path, caminho: object) -> Path:
    arquivo = Path(str(caminho))
    return arquivo if arquivo.exists() else cache / "downloads" / "ducklake" / "sih" / arquivo.name


def carregar_coordenadas(caminho: Path) -> pd.DataFrame:
    if not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(URL_COORDENADAS, timeout=90) as resposta:
            caminho.write_bytes(resposta.read())
    dados = pd.read_csv(caminho, dtype={"codigo_ibge": "string"})
    dados["codigo_municipio"] = dados.codigo_ibge.str[:6]
    return dados[["codigo_municipio", "nome", "latitude", "longitude"]].drop_duplicates("codigo_municipio")


def haversine(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def gerar(saida: Path, cache: Path, coordenadas: Path, inicio: int, fim: int, mes_final: int) -> None:
    os.environ["PYSUS_CACHEPATH"] = str(cache.resolve())
    from pysus.ftp import sih

    cirurgias = []
    for uf in UFS:
        for ano in range(inicio, fim + 1):
            meses = list(range(1, mes_final + 1)) if ano == fim else list(range(1, 13))
            print(f"SIH/AIH cirurgias {uf} {ano}", flush=True)
            esperados = [cache / "downloads" / "ducklake" / "sih" / f"RD{uf}{str(ano)[2:]}{mes:02d}.parquet" for mes in meses]
            caminhos = esperados if all(p.exists() for p in esperados) else baixar_com_retentativa(sih, uf, ano, meses)
            for caminho in caminhos:
                arquivo = caminho_real(cache, caminho)
                dados = pd.read_parquet(arquivo, columns=[
                    "ANO_CMPT", "MES_CMPT", "N_AIH", "PROC_REA", "DIAG_PRINC", "MUNIC_RES",
                    "MUNIC_MOV", "CNES", "IDADE", "SEXO", "MORTE",
                ])
                dados = dados[dados.PROC_REA.astype("string").str.startswith("0416", na=False)].copy()
                if not dados.empty:
                    cirurgias.append(dados)

    bruto = pd.concat(cirurgias, ignore_index=True).drop_duplicates("N_AIH")
    bruto["ano"] = pd.to_numeric(bruto.ANO_CMPT, errors="coerce").astype("Int64")
    bruto["mes"] = pd.to_numeric(bruto.MES_CMPT, errors="coerce").astype("Int64")
    bruto["codigo_residencia"] = bruto.MUNIC_RES.astype("string").str.zfill(6).str[:6]
    bruto["codigo_atendimento"] = bruto.MUNIC_MOV.astype("string").str.zfill(6).str[:6]
    bruto["uf_residencia"] = bruto.codigo_residencia.str[:2].map(UF_POR_CODIGO).fillna("Ignorada")
    bruto["uf_atendimento"] = bruto.codigo_atendimento.str[:2].map(UF_POR_CODIGO).fillna("Ignorada")
    bruto["regiao_atendimento"] = bruto.uf_atendimento.map(REGIOES).fillna("Ignorada")
    bruto["tipo_cancer"] = tipo_cancer(bruto.DIAG_PRINC)
    bruto["sexo"] = bruto.SEXO.astype("string").map({"1": "Masculino", "3": "Feminino"}).fillna("Ignorado")
    idade = pd.to_numeric(bruto.IDADE, errors="coerce")
    bruto["faixa_etaria"] = pd.cut(idade, [-1, 14, 19, 39, 59, 79, math.inf],
        labels=["0–14", "15–19", "20–39", "40–59", "60–79", "80+"]).astype("string").fillna("Ignorada")
    bruto["fora_municipio"] = bruto.codigo_residencia.ne(bruto.codigo_atendimento)
    bruto["obito"] = pd.to_numeric(bruto.MORTE, errors="coerce").fillna(0).astype(int)

    coords = carregar_coordenadas(coordenadas)
    res = coords.add_suffix("_residencia")
    aten = coords.add_suffix("_atendimento")
    bruto = bruto.merge(res, left_on="codigo_residencia", right_on="codigo_municipio_residencia", how="left")
    bruto = bruto.merge(aten, left_on="codigo_atendimento", right_on="codigo_municipio_atendimento", how="left")
    bruto["distancia_km"] = haversine(bruto.latitude_residencia, bruto.longitude_residencia,
                                       bruto.latitude_atendimento, bruto.longitude_atendimento)
    bruto["faixa_distancia"] = pd.cut(bruto.distancia_km, [-1, 0.01, 50, 100, 200, math.inf],
        labels=["Mesmo município", "Até 50 km", "51–100 km", "101–200 km", "Mais de 200 km"]
    ).astype("string").fillna("Distância indisponível")

    dimensoes = ["ano", "mes", "regiao_atendimento", "uf_atendimento", "uf_residencia", "tipo_cancer",
                 "sexo", "faixa_etaria", "faixa_distancia", "fora_municipio"]
    agregado = bruto.groupby(dimensoes, observed=True, dropna=False).agg(
        internacoes=("N_AIH", "size"), obitos=("obito", "sum"), soma_distancia_km=("distancia_km", "sum"),
        distancias_validas=("distancia_km", "count"),
    ).reset_index()
    payload = {
        "metadados": {
            "fonte": "SIH/SUS — arquivos RD de Autorização de Internação Hospitalar",
            "criterio": "Procedimento realizado no subgrupo SIGTAP 04.16 — Cirurgia em oncologia",
            "periodo": [inicio, fim], "ultima_competencia": f"{fim}{mes_final:02d}",
            "unidade": "internações/AIHs; não pessoas únicas",
            "distancia": "linha reta entre coordenadas das sedes municipais; não representa trajeto rodoviário",
            "coordenadas_fonte": "Municipios-Brasileiros, derivado de dados geográficos do IBGE",
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        },
        "dados": agregado.to_dict(orient="records"),
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_suffix(saida.suffix + ".tmp")
    temporario.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporario.replace(saida)
    print(f"Criado {saida}: {int(agregado.internacoes.sum()):,} internações cirúrgicas oncológicas")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicio", type=int, default=2025)
    parser.add_argument("--fim", type=int, default=2026)
    parser.add_argument("--mes-final", type=int, default=6)
    parser.add_argument("--saida", type=Path, default=Path("dados/cirurgias_oncologicas_sih.json"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/pysus"))
    parser.add_argument("--coordenadas", type=Path, default=Path("dados/municipios_coordenadas.csv"))
    args = parser.parse_args()
    gerar(args.saida.resolve(), args.cache, args.coordenadas, args.inicio, args.fim, args.mes_final)


if __name__ == "__main__":
    main()
