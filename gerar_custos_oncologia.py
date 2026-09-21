"""Agrega valores administrativos de oncologia do SIA/APAC e SIH/AIH."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


REGIOES = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Centro-Oeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
}
UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


def tipo_cancer(cid: pd.Series) -> pd.Series:
    numero = pd.to_numeric(cid.astype("string").str.extract(r"^C(\d{2})", expand=False), errors="coerce")
    condicoes = [cond.fillna(False).to_numpy(dtype=bool) for cond in [
        numero.eq(50), numero.eq(61), numero.between(18, 21), numero.between(33, 34), numero.eq(53),
        numero.between(91, 95), numero.between(70, 72), numero.between(81, 86),
    ]]
    return pd.Series(np.select(condicoes,
        ["Mama", "Próstata", "Colorretal", "Pulmão", "Colo do útero", "Leucemias", "SNC", "Linfomas"],
        default="Outros diagnósticos oncológicos"), index=cid.index)


def faixa_etaria(idade: pd.Series) -> pd.Series:
    return pd.cut(pd.to_numeric(idade, errors="coerce"), [-1, 14, 19, 39, 59, 79, np.inf],
        labels=["0–14", "15–19", "20–39", "40–59", "60–79", "80+"]
    ).astype("string").fillna("Ignorada")


def idade_apac(unidade: pd.Series, quantidade: pd.Series) -> pd.Series:
    unidade = pd.to_numeric(unidade, errors="coerce")
    quantidade = pd.to_numeric(quantidade, errors="coerce")
    return pd.Series(np.where(unidade.eq(4), quantidade, np.where(unidade.isin([1, 2, 3]), 0, np.nan)), index=unidade.index)


def competencia(caminho: Path) -> tuple[int, int]:
    achado = re.search(r"(\d{2})(\d{2})\.parquet$", caminho.name)
    if not achado:
        raise ValueError(f"Competência não reconhecida: {caminho.name}")
    return 2000 + int(achado.group(1)), int(achado.group(2))


def agregar_sia(pasta: Path) -> pd.DataFrame:
    partes = []
    for arquivo in sorted([*pasta.glob("AQ*.parquet"), *pasta.glob("AR*.parquet")]):
        grupo = arquivo.name[:2]
        cid = f"{grupo}_CID10"
        dados = pd.read_parquet(arquivo, columns=[
            "AP_MVM", "AP_UFMUN", "AP_SEXO", "AP_COIDADE", "AP_NUIDADE", "AP_VL_AP", cid,
        ])
        ano, mes = competencia(arquivo)
        dados["ano"], dados["mes"] = ano, mes
        dados["sistema"] = "SIA"
        dados["modalidade"] = "Quimioterapia" if grupo == "AQ" else "Radioterapia"
        dados["uf_atendimento"] = arquivo.name[2:4]
        dados["regiao_atendimento"] = dados.uf_atendimento.map(REGIOES)
        dados["tipo_cancer"] = tipo_cancer(dados[cid])
        dados["sexo"] = dados.AP_SEXO.map({"M": "Masculino", "F": "Feminino"}).fillna("Ignorado")
        dados["faixa_etaria"] = faixa_etaria(idade_apac(dados.AP_COIDADE, dados.AP_NUIDADE))
        dados["valor"] = pd.to_numeric(dados.AP_VL_AP, errors="coerce").fillna(0)
        dimensoes = ["ano", "mes", "sistema", "modalidade", "regiao_atendimento", "uf_atendimento",
                     "tipo_cancer", "sexo", "faixa_etaria"]
        partes.append(dados.groupby(dimensoes, observed=True, dropna=False).valor.sum().reset_index())
    return pd.concat(partes, ignore_index=True).groupby(
        ["ano", "mes", "sistema", "modalidade", "regiao_atendimento", "uf_atendimento",
         "tipo_cancer", "sexo", "faixa_etaria"], observed=True, dropna=False
    ).valor.sum().reset_index()


def agregar_sih(pasta: Path) -> pd.DataFrame:
    partes = []
    for arquivo in sorted(pasta.glob("RD*.parquet")):
        dados = pd.read_parquet(arquivo, columns=[
            "ANO_CMPT", "MES_CMPT", "N_AIH", "DIAG_PRINC", "MUNIC_MOV", "SEXO", "IDADE", "VAL_TOT",
        ])
        cid = dados.DIAG_PRINC.astype("string").str.upper()
        dados = dados[cid.str.match(r"^(C\d{2}|D(?:0\d|[1-3]\d|4[0-8]))", na=False)].copy()
        if dados.empty:
            continue
        dados = dados.drop_duplicates("N_AIH")
        dados["ano"] = pd.to_numeric(dados.ANO_CMPT, errors="coerce").astype("Int64")
        dados["mes"] = pd.to_numeric(dados.MES_CMPT, errors="coerce").astype("Int64")
        dados["sistema"] = "SIH"
        dados["modalidade"] = "Internações"
        dados["uf_atendimento"] = dados.MUNIC_MOV.astype("string").str.zfill(6).str[:2].map(UF_POR_CODIGO).fillna("Ignorada")
        dados["regiao_atendimento"] = dados.uf_atendimento.map(REGIOES).fillna("Ignorada")
        dados["tipo_cancer"] = tipo_cancer(dados.DIAG_PRINC)
        dados["sexo"] = dados.SEXO.astype("string").map({"1": "Masculino", "3": "Feminino"}).fillna("Ignorado")
        dados["faixa_etaria"] = faixa_etaria(dados.IDADE)
        dados["valor"] = pd.to_numeric(dados.VAL_TOT, errors="coerce").fillna(0)
        partes.append(dados[["N_AIH", "ano", "mes", "sistema", "modalidade", "regiao_atendimento", "uf_atendimento",
                             "tipo_cancer", "sexo", "faixa_etaria", "valor"]])
    bruto = pd.concat(partes, ignore_index=True).drop_duplicates("N_AIH")
    dimensoes = ["ano", "mes", "sistema", "modalidade", "regiao_atendimento", "uf_atendimento",
                 "tipo_cancer", "sexo", "faixa_etaria"]
    return bruto.groupby(dimensoes, observed=True, dropna=False).valor.sum().reset_index()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path(".cache/pysus/downloads/ducklake"))
    parser.add_argument("--saida", type=Path, default=Path("dados/custos_oncologia_sia_sih.json"))
    args = parser.parse_args()
    sia, sih = agregar_sia(args.cache / "sia"), agregar_sih(args.cache / "sih")
    dados = pd.concat([sia, sih], ignore_index=True)
    ultima = dados.assign(comp=dados.ano * 100 + dados.mes).comp.max()
    payload = {
        "metadados": {
            "fonte": "DATASUS — SIA/SUS (APAC AQ/AR) e SIH/SUS (AIH RD)",
            "periodo": [int(dados.ano.min()), int(dados.ano.max())],
            "ultima_competencia": str(int(ultima)),
            "criterio_sia": "Soma de AP_VL_AP nas APACs de quimioterapia e radioterapia",
            "criterio_sih": "Soma de VAL_TOT nas AIHs com diagnóstico principal C00–C97 ou D00–D48",
            "interpretacao": "Valores administrativos aprovados/registrados; não representam custo econômico nem necessariamente pagamento efetivo.",
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        },
        "dados": dados.to_dict(orient="records"),
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{args.saida}: SIA R$ {sia.valor.sum():,.2f}; SIH R$ {sih.valor.sum():,.2f}")


if __name__ == "__main__":
    main()
