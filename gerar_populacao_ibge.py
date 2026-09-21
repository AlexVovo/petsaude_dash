"""Converte a Projeção da População IBGE 2024 em denominadores do painel."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


FAIXAS = ["0–14", "15–19", "20–39", "40–59", "60–79", "80+"]


def gerar(entrada: Path, saida: Path, ano_final: int = 2026) -> None:
    bruto = pd.read_excel(entrada, header=5)
    ufs = bruto["CÓD."].between(11, 53) & bruto["SIGLA"].astype(str).str.len().eq(2)
    dados = bruto.loc[ufs & bruto["SEXO"].isin(["Homens", "Mulheres"])].copy()
    anos = [coluna for coluna in dados.columns if isinstance(coluna, int) and 2000 <= coluna <= ano_final]
    longo = dados.melt(
        id_vars=["IDADE", "SEXO", "SIGLA"], value_vars=anos,
        var_name="ano", value_name="populacao",
    )
    longo["sexo"] = longo["SEXO"].map({"Homens": "Masculino", "Mulheres": "Feminino"})
    # Na planilha, 90 representa a classe aberta de 90 anos ou mais.
    longo["faixa_etaria"] = pd.cut(
        longo["IDADE"], [-1, 14, 19, 39, 59, 79, np.inf], labels=FAIXAS,
    ).astype("string")
    agregado = (
        longo.groupby(["ano", "SIGLA", "sexo", "faixa_etaria"], observed=True)["populacao"]
        .sum().round().astype("int64").reset_index().rename(columns={"SIGLA": "uf"})
        .sort_values(["ano", "uf", "sexo", "faixa_etaria"])
    )
    payload = {
        "metadados": {
            "fonte": "IBGE — Projeções da População, Revisão 2024",
            "referencia": "População em 1º de julho, por UF, sexo e idade simples",
            "periodo": [int(agregado.ano.min()), int(agregado.ano.max())],
            "revisao": 2024,
        },
        "dados": agregado.to_dict(orient="records"),
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_suffix(saida.suffix + ".tmp")
    temporario.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporario.replace(saida)
    print(f"Criado {saida}: {len(agregado):,} denominadores")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("entrada", type=Path)
    parser.add_argument("--saida", type=Path, default=Path("dados/populacao_ibge.json"))
    parser.add_argument("--ano-final", type=int, default=2026)
    args = parser.parse_args()
    gerar(args.entrada.resolve(), args.saida.resolve(), args.ano_final)


if __name__ == "__main__":
    main()
