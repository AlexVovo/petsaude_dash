"""Gera um agregado nacional de habilitações oncológicas do CNES."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import unicodedata
from pathlib import Path
from urllib.request import urlopen

import pandas as pd


UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]
REGIOES = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Centro-Oeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
}
CODIGOS = {
    "1704": "Serviço isolado de radioterapia",
    "1706": "UNACON",
    "1707": "UNACON com radioterapia",
    "1708": "UNACON com hematologia",
    "1709": "UNACON com oncologia pediátrica",
    "1710": "UNACON exclusiva de hematologia",
    "1711": "UNACON exclusiva de oncologia pediátrica",
    "1712": "CACON",
    "1713": "CACON com oncologia pediátrica",
    "1714": "Hospital geral com cirurgia oncológica",
    "1715": "Radioterapia de complexo hospitalar",
    "1716": "Oncologia clínica de complexo hospitalar",
}
URL_SAES = (
    "https://www.gov.br/saude/pt-br/composicao/saes/cgcan/arquivos/"
    "hospitais-habilitados-em-oncologia-dezembro.xlsx/@@download/file"
)
URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


def normalizar(texto: object) -> str:
    base = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(base.upper().split())


def baixar_json(url: str) -> object:
    with urlopen(url, timeout=90) as resposta:
        conteudo = resposta.read()
        if conteudo[:2] == b"\x1f\x8b":
            conteudo = gzip.decompress(conteudo)
        return json.loads(conteudo.decode("utf-8"))


def nomes_saes(planilha: Path) -> dict[str, dict[str, str]]:
    if not planilha.exists():
        planilha.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(URL_SAES, timeout=90) as resposta:
            planilha.write_bytes(resposta.read())
    dados = pd.read_excel(planilha)
    dados.columns = [normalizar(c) for c in dados.columns]
    dados["CNES"] = dados["CNES"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    saida = {}
    for _, linha in dados.dropna(subset=["CNES"]).iterrows():
        saida[linha["CNES"]] = {
            "estabelecimento": str(linha.get("ESTABELECIMENTO", "")).strip(),
            "municipio_saes": str(linha.get("MUNICIPIO", "")).strip(),
        }
    return saida


def municipios_ibge() -> dict[str, str]:
    saida = {}
    for item in baixar_json(URL_MUNICIPIOS):
        # O CNES usa os seis primeiros dígitos do código municipal IBGE.
        saida[str(item["id"])[:6]] = item["nome"]
    return saida


def gestao(codigo: object) -> str:
    codigo = str(codigo).strip().upper()
    return {"F": "Federal", "E": "Estadual", "M": "Municipal", "D": "Dupla"}.get(codigo, "Não informada")


def natureza_juridica(natureza: object) -> str:
    nat = str(natureza).strip()
    if nat.startswith("1") or nat == "2011":
        return "Pública"
    if nat == "2054":
        return "Economia mista"
    if nat[:1] in {"2", "3", "4", "5"}:
        return "Privada"
    return "Não informada"


def gerar(ano: int, mes: int, saida: Path, cache: Path, planilha_saes: Path) -> None:
    os.environ["PYSUS_CACHEPATH"] = str(cache.resolve())
    from pysus.ftp import cnes

    quadros = []
    for uf in UFS:
        print(f"CNES {uf} {ano}-{mes:02d}", flush=True)
        caminhos = cnes(uf, ano, mes, group="HB")
        for caminho in caminhos:
            arquivo = Path(str(caminho))
            if not arquivo.exists():
                arquivo = cache / "downloads" / "ducklake" / "cnes" / arquivo.name
            quadro = pd.read_parquet(arquivo)
            quadro["uf"] = uf
            quadros.append(quadro)
    bruto = pd.concat(quadros, ignore_index=True)
    bruto["codigo"] = bruto["SGRUPHAB"].astype(str).str.zfill(4)
    bruto = bruto[bruto.codigo.isin(CODIGOS)].copy()
    bruto["CNES"] = bruto["CNES"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)

    nomes = nomes_saes(planilha_saes)
    municipios = municipios_ibge()
    registros = []
    for cnes_id, grupo in bruto.groupby("CNES", sort=True):
        primeira = grupo.iloc[0]
        codigos = sorted(grupo.codigo.unique().tolist())
        principal = next((c for c in ["1713", "1712", "1711", "1709", "1707", "1708", "1710", "1706", "1714", "1715", "1716", "1704"] if c in codigos), codigos[0])
        cadastro = nomes.get(cnes_id, {})
        codigo_municipio = str(primeira["CODUFMUN"]).strip().zfill(6)
        registros.append({
            "cnes": cnes_id,
            "estabelecimento": cadastro.get("estabelecimento") or f"Estabelecimento CNES {cnes_id}",
            "uf": primeira["uf"],
            "regiao": REGIOES[primeira["uf"]],
            "codigo_municipio": codigo_municipio,
            "municipio": municipios.get(codigo_municipio) or cadastro.get("municipio_saes") or "Não identificado",
            "gestao": gestao(primeira.get("ESFERA_A", "")),
            "natureza_juridica": natureza_juridica(primeira.get("NAT_JUR", "")),
            "tipo_principal": CODIGOS[principal],
            "codigos": codigos,
            "habilitacoes": [CODIGOS[c] for c in codigos],
            "cacon_unacon": any(c in codigos for c in ["1706", "1707", "1708", "1709", "1710", "1711", "1712", "1713"]),
            "radioterapia": any(c in codigos for c in ["1704", "1707", "1712", "1713", "1715"]),
            "hematologia": any(c in codigos for c in ["1708", "1710", "1712", "1713"]),
            "pediatria": any(c in codigos for c in ["1709", "1711", "1713"]),
            "cirurgia_oncologica": any(c in codigos for c in ["1706", "1707", "1708", "1709", "1712", "1713", "1714"]),
            "nome_referencia": "SAES dez/2024" if cnes_id in nomes else "Não disponível na planilha SAES dez/2024",
        })

    payload = {
        "metadados": {
            "fonte": "CNES/DATASUS — habilitações de estabelecimentos",
            "competencia": f"{ano}{mes:02d}",
            "criterio": "Habilitações oncológicas 17.04 e 17.06–17.16 ativas na competência",
            "nomes_fonte": "Lista nominal SAES de dezembro de 2024; novos CNES podem aparecer sem nome",
            "total_estabelecimentos": len(registros),
            "total_cacon_unacon": sum(r["cacon_unacon"] for r in registros),
        },
        "dados": registros,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_suffix(saida.suffix + ".tmp")
    temporario.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporario.replace(saida)
    print(f"Criado {saida}: {len(registros)} estabelecimentos")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ano", type=int, default=2026)
    parser.add_argument("--mes", type=int, default=7)
    parser.add_argument("--saida", type=Path, default=Path("dados/estrutura_oncologia_cnes.json"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/pysus"))
    parser.add_argument("--saes-xlsx", type=Path, default=Path("dados/hospitais_oncologia_saes_dez2024.xlsx"))
    args = parser.parse_args()
    gerar(args.ano, args.mes, args.saida.resolve(), args.cache, args.saes_xlsx)


if __name__ == "__main__":
    main()
