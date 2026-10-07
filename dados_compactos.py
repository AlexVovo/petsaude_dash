"""Leitura compacta dos agregados, com verificação da fonte JSON."""
import hashlib
import json
from pathlib import Path

import pandas as pd


def resumo_arquivo(caminho: Path) -> str:
    with caminho.open("rb") as arquivo:
        return hashlib.file_digest(arquivo, "sha256").hexdigest()


def ler_payload(caminho: Path) -> dict:
    pasta = caminho.parent / "compactados"
    manifesto = pasta / f"{caminho.stem}.json"
    if manifesto.exists():
        indice = json.loads(manifesto.read_text(encoding="utf-8"))
        tabelas = indice["tabelas"]
        if (all((pasta / nome).exists() for nome in tabelas.values())
                and resumo_arquivo(caminho) == indice["sha256_fonte"]):
            return {
                "metadados": indice["metadados"],
                **{chave: pd.read_parquet(pasta / nome, dtype_backend="pyarrow") for chave, nome in tabelas.items()},
            }
    # Um JSON atualizado nunca usa silenciosamente uma cópia compacta antiga.
    with caminho.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)
