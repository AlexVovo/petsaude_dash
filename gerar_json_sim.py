"""Gera um JSON agregado de mortalidade oncológica a partir dos CSVs do SIM.

Uso:
    .venv/bin/python gerar_json_sim.py /home/alex/CSV_SIM/CSV

Os arquivos nacionais DOBR<ano>.csv são usados para evitar dupla contagem com
os arquivos estaduais. Somente óbitos cuja causa básica é CID-10 C00–C97
são incluídos.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

REGIAO_POR_UF = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Centro-Oeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
}

COLUNAS_GRUPO = [
    "ano", "mes", "uf", "regiao", "tipo_cancer", "faixa_etaria", "sexo", "segmento"
]


def tipo_cancer(cid: pd.Series) -> pd.Series:
    numero = pd.to_numeric(cid.str.extract(r"^C(\d{2})", expand=False), errors="coerce")
    condicoes = [
        cond.fillna(False).to_numpy(dtype=bool)
        for cond in [
            numero.eq(50), numero.eq(61), numero.between(18, 21), numero.between(33, 34),
            numero.eq(53), numero.between(91, 95), numero.between(70, 72), numero.between(81, 86),
        ]
    ]
    rotulos = ["Mama", "Próstata", "Colorretal", "Pulmão", "Colo do útero", "Leucemias", "SNC", "Linfomas"]
    return pd.Series(np.select(condicoes, rotulos, default="Outras neoplasias malignas"), index=cid.index)


def idade_em_anos(valor: pd.Series) -> pd.Series:
    codigo = pd.to_numeric(valor, errors="coerce")
    unidade = np.floor(codigo / 100)
    quantidade = codigo % 100
    return pd.Series(
        np.select(
            [
                unidade.eq(4).fillna(False).to_numpy(dtype=bool),
                unidade.eq(5).fillna(False).to_numpy(dtype=bool),
                unidade.isin([1, 2, 3]).fillna(False).to_numpy(dtype=bool),
            ],
            [quantidade, 100 + quantidade, 0],
            default=np.nan,
        ),
        index=valor.index,
    )


def agregar_arquivo(caminho: Path) -> tuple[pd.DataFrame, int]:
    partes: list[pd.DataFrame] = []
    total_oncologia = 0
    with caminho.open("rb") as arquivo:
        cabecalho = arquivo.readline()
    separador = ";" if cabecalho.count(b";") > cabecalho.count(b",") else ","
    for bruto in pd.read_csv(
        caminho,
        sep=separador,
        usecols=["DTOBITO", "CAUSABAS", "SEXO", "IDADE", "CODMUNRES"],
        dtype="string",
        chunksize=250_000,
        low_memory=False,
    ):
        cid = bruto["CAUSABAS"].str.upper().str.replace(".", "", regex=False).str.strip()
        mascara = cid.str.match(r"^C(?:0[0-9]|[1-8][0-9]|9[0-7])", na=False)
        dados = bruto.loc[mascara].copy()
        if dados.empty:
            continue
        cid = cid.loc[dados.index]
        total_oncologia += len(dados)
        data = pd.to_datetime(dados["DTOBITO"], format="%d%m%Y", errors="coerce")
        idade = idade_em_anos(dados["IDADE"])
        uf = dados["CODMUNRES"].str.replace(r"\.0$", "", regex=True).str.zfill(6).str[:2].map(UF_POR_CODIGO)
        base = pd.DataFrame({
            "ano": data.dt.year,
            "mes": data.dt.month,
            "uf": uf.fillna("Ignorada"),
            "regiao": uf.map(REGIAO_POR_UF).fillna("Ignorada"),
            "tipo_cancer": tipo_cancer(cid),
            "faixa_etaria": pd.cut(
                idade, [-1, 14, 19, 39, 59, 79, np.inf],
                labels=["0–14", "15–19", "20–39", "40–59", "60–79", "80+"],
            ).astype("string").fillna("Ignorada"),
            "sexo": dados["SEXO"].str.strip().map({"1": "Masculino", "2": "Feminino"}).fillna("Ignorado"),
            "segmento": np.where(idade.lt(20), "Pediátrico", np.where(idade.notna(), "Adulto", "Ignorado")),
        }).dropna(subset=["ano", "mes"])
        base[["ano", "mes"]] = base[["ano", "mes"]].astype(int)
        partes.append(base.groupby(COLUNAS_GRUPO, observed=True, dropna=False).size().rename("obitos").reset_index())

    if not partes:
        return pd.DataFrame(columns=COLUNAS_GRUPO + ["obitos"]), total_oncologia
    agregado = pd.concat(partes, ignore_index=True)
    agregado = agregado.groupby(COLUNAS_GRUPO, observed=True, dropna=False)["obitos"].sum().reset_index()
    return agregado, total_oncologia


def gerar_json(pasta: Path, saida: Path) -> None:
    arquivos = sorted(
        (p for p in pasta.glob("DOBR????.csv") if re.fullmatch(r"DOBR\d{4}\.csv", p.name)),
        key=lambda p: p.name,
    )
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo DOBR<ano>.csv encontrado em {pasta}")

    anuais: list[pd.DataFrame] = []
    total = 0
    for indice, arquivo in enumerate(arquivos, start=1):
        agregado, quantidade = agregar_arquivo(arquivo)
        anuais.append(agregado)
        total += quantidade
        print(f"[{indice:02d}/{len(arquivos)}] {arquivo.name}: {quantidade:,} óbitos oncológicos", flush=True)

    dados = pd.concat(anuais, ignore_index=True)
    dados = dados.groupby(COLUNAS_GRUPO, observed=True, dropna=False)["obitos"].sum().reset_index()
    dados = dados.sort_values(COLUNAS_GRUPO).reset_index(drop=True)
    total_analisavel = int(dados["obitos"].sum())

    payload = {
        "metadados": {
            "fonte": "Sistema de Informações sobre Mortalidade (SIM/DATASUS)",
            "criterio": "Causa básica CID-10 C00–C97",
            "unidade": "óbitos",
            "arquivos": len(arquivos),
            "periodo": [int(dados["ano"].min()), int(dados["ano"].max())],
            "total_obitos": total_analisavel,
            "registros_excluidos_data_invalida": int(total - total_analisavel),
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
            "observacao": "Contagens de óbitos; não são taxas populacionais nem incidência.",
            "periodos_provisorios": {
                "2025": "preliminar",
                "2026": "1ª prévia; extração em 01/06/2026",
            },
        },
        "dados": dados.to_dict(orient="records"),
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_suffix(saida.suffix + ".tmp")
    temporario.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporario.replace(saida)
    print(f"JSON criado: {saida} ({saida.stat().st_size / 1024 / 1024:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pasta", type=Path, help="Pasta com os CSVs do SIM")
    parser.add_argument("--saida", type=Path, default=Path("dados/sim_oncologia_agregado.json"))
    args = parser.parse_args()
    gerar_json(args.pasta.expanduser().resolve(), args.saida.resolve())


if __name__ == "__main__":
    main()
