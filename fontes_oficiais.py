"""Acesso e transformação de fontes oficiais usadas pelo painel.

O PySUS é somente o cliente de acesso. Os registros permanecem identificados
como provenientes do DATASUS/SIM e são filtrados para neoplasias malignas.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


UF_REGIAO = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
    "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}


def _idade_sim(valor: object) -> float:
    """Converte o código etário de três posições do SIM em anos completos."""
    texto = str(valor).strip().replace(".0", "")
    if not texto.isdigit() or len(texto) < 3:
        return np.nan
    codigo = int(texto)
    unidade, quantidade = codigo // 100, codigo % 100
    if unidade == 4:  # anos
        return float(quantidade)
    if unidade == 5:  # 100 anos ou mais
        return float(100 + quantidade)
    if unidade in {1, 2, 3}:  # minutos, horas ou dias
        return 0.0
    return np.nan


def _tipo_cancer(cid: object) -> str:
    codigo = str(cid).upper().replace(".", "").strip()
    if codigo.startswith("C50"): return "Mama"
    if codigo.startswith("C61"): return "Próstata"
    if any(codigo.startswith(f"C{i}") for i in range(18, 22)): return "Colorretal"
    if codigo.startswith(("C33", "C34")): return "Pulmão"
    if codigo.startswith("C53"): return "Colo do útero"
    if any(codigo.startswith(f"C{i}") for i in range(91, 96)): return "Leucemias"
    if codigo.startswith(("C70", "C71", "C72")): return "SNC"
    if any(codigo.startswith(f"C{i}") for i in range(81, 87)): return "Linfomas"
    return "Outras neoplasias malignas"


def baixar_sim_oncologia(uf: str, ano: int, cache_dir: str | Path = ".cache/pysus") -> pd.DataFrame:
    """Baixa o SIM e devolve óbitos cuja causa básica está entre C00 e C97."""
    cache = Path(cache_dir).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYSUS_CACHEPATH", str(cache))

    import pysus  # import tardio: o app abre mesmo se a dependência opcional falhar

    pysus.disable_progress_bars()
    # O catálogo do SIM resolve automaticamente DO/DOR conforme UF e período.
    # Informar o grupo explicitamente retorna vazio em algumas versões do catálogo.
    bruto = pysus.ftp.sim(state=uf, year=int(ano), as_dataframe=True)
    if not isinstance(bruto, pd.DataFrame):
        raise RuntimeError("O PySUS não retornou uma tabela para a consulta solicitada.")

    bruto.columns = [str(c).upper() for c in bruto.columns]
    exigidas = {"DTOBITO", "CAUSABAS", "SEXO", "IDADE", "CODMUNRES"}
    ausentes = exigidas - set(bruto.columns)
    if ausentes:
        raise ValueError("Campos ausentes no SIM: " + ", ".join(sorted(ausentes)))

    cid = bruto["CAUSABAS"].astype(str).str.upper().str.replace(".", "", regex=False).str.strip()
    oncologia = bruto.loc[cid.str.match(r"^C(?:0[0-9]|[1-8][0-9]|9[0-7])")].copy()
    oncologia["cid10"] = cid.loc[oncologia.index]
    oncologia["data_obito"] = pd.to_datetime(oncologia["DTOBITO"], format="%d%m%Y", errors="coerce")
    oncologia["idade"] = oncologia["IDADE"].map(_idade_sim)
    oncologia["sexo"] = oncologia["SEXO"].astype(str).str.strip().map({"1": "Masculino", "2": "Feminino"}).fillna("Ignorado")
    oncologia["tipo_cancer"] = oncologia["cid10"].map(_tipo_cancer)
    oncologia["municipio_residencia_ibge"] = oncologia["CODMUNRES"].astype(str).str.replace(r"\.0$", "", regex=True)
    oncologia["uf"] = uf
    oncologia["regiao"] = UF_REGIAO[uf]
    oncologia["ano"] = oncologia["data_obito"].dt.year.fillna(int(ano)).astype(int)
    oncologia["mes"] = oncologia["data_obito"].dt.month
    oncologia["faixa_etaria"] = pd.cut(
        oncologia["idade"], [-1, 14, 19, 39, 59, 79, 200],
        labels=["0–14", "15–19", "20–39", "40–59", "60–79", "80+"],
    )
    colunas = ["data_obito", "ano", "mes", "cid10", "tipo_cancer", "idade", "faixa_etaria", "sexo",
               "municipio_residencia_ibge", "uf", "regiao"]
    return oncologia[colunas].reset_index(drop=True)
