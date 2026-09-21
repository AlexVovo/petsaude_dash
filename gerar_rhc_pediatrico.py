"""Agrega casos pediátricos do Integrador RHC por CICI/ICCC-3 (IARC 2017).

Uso:
    .venv/bin/python gerar_rhc_pediatrico.py /caminho/download_tabwin.zip \
        dados/ICCC-2017.xlsx
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from dbfread import DBF


GRUPOS_ICCC = {
    1: "I. Leucemias, doenças mieloproliferativas e mielodisplásicas",
    2: "II. Linfomas e neoplasias reticuloendoteliais",
    3: "III. SNC e neoplasias intracranianas/intraespinhais",
    4: "IV. Neuroblastoma e outros tumores de células nervosas periféricas",
    5: "V. Retinoblastoma",
    6: "VI. Tumores renais",
    7: "VII. Tumores hepáticos",
    8: "VIII. Tumores ósseos malignos",
    9: "IX. Sarcomas de partes moles e extraósseos",
    10: "X. Tumores de células germinativas e gonadais",
    11: "XI. Outras neoplasias epiteliais e melanomas",
    12: "XII. Outras neoplasias malignas e não especificadas",
}
SUBGRUPOS_ICCC = {
    "011": "Ia. Leucemias linfoides", "012": "Ib. Leucemias mieloides agudas",
    "013": "Ic. Doenças mieloproliferativas crônicas", "014": "Id. Síndromes mielodisplásicas e outras doenças mieloproliferativas",
    "015": "Ie. Leucemias não especificadas e outras", "021": "IIa. Linfomas de Hodgkin",
    "022": "IIb. Linfomas não Hodgkin, exceto Burkitt", "023": "IIc. Linfoma de Burkitt",
    "024": "IId. Outras neoplasias linforreticulares", "025": "IIe. Linfomas não especificados",
    "031": "IIIa. Ependimomas e tumores do plexo coroide", "032": "IIIb. Astrocitomas",
    "033": "IIIc. Tumores embrionários intracranianos e intraespinhais", "034": "IIId. Outros gliomas",
    "035": "IIIe. Outras neoplasias intracranianas e intraespinhais especificadas", "036": "IIIf. Neoplasias intracranianas e intraespinhais não especificadas",
    "041": "IVa. Neuroblastoma e ganglioneuroblastoma", "042": "IVb. Outros tumores de células nervosas periféricas",
    "050": "V. Retinoblastoma", "061": "VIa. Nefroblastoma e outros tumores renais não epiteliais",
    "062": "VIb. Carcinomas renais", "063": "VIc. Tumores renais malignos não especificados",
    "071": "VIIa. Hepatoblastoma e tumores mesenquimais do fígado", "072": "VIIb. Carcinomas hepáticos",
    "073": "VIIc. Tumores hepáticos malignos não especificados", "081": "VIIIa. Osteossarcomas",
    "082": "VIIIb. Condrossarcomas", "083": "VIIIc. Tumor de Ewing e sarcomas ósseos relacionados",
    "084": "VIIId. Outros tumores ósseos malignos especificados", "085": "VIIIe. Tumores ósseos malignos não especificados",
    "091": "IXa. Rabdomiossarcomas", "092": "IXb. Fibrossarcomas e outras neoplasias fibrosas",
    "093": "IXc. Sarcoma de Kaposi", "094": "IXd. Outros sarcomas de partes moles especificados",
    "095": "IXe. Sarcomas de partes moles não especificados", "101": "Xa. Tumores germinativos intracranianos e intraespinhais",
    "102": "Xb. Tumores germinativos extracranianos e extragonadais", "103": "Xc. Tumores germinativos gonadais",
    "104": "Xd. Carcinomas gonadais", "105": "Xe. Outros tumores gonadais malignos e não especificados",
    "111": "XIa. Carcinomas adrenocorticais", "112": "XIb. Carcinomas da tireoide",
    "113": "XIc. Carcinomas nasofaríngeos", "114": "XId. Melanomas malignos",
    "115": "XIe. Carcinomas de pele", "116": "XIf. Outros carcinomas e carcinomas não especificados",
    "121": "XIIa. Outros tumores malignos especificados", "122": "XIIb. Outros tumores malignos não especificados",
    "999": "Não classificado",
}
SEXO = {"1": "Masculino", "2": "Feminino"}
RAZAO_NAO_TRATAMENTO = {
    "1": "Recusa do tratamento", "2": "Tratamento realizado fora", "3": "Doença avançada ou condição clínica",
    "4": "Abandono do tratamento", "5": "Complicações do tratamento", "6": "Óbito",
    "7": "Outras", "8": "Não se aplica", "9": "Sem informação",
}


def expandir_codigos(valor: object) -> set[int]:
    if pd.isna(valor):
        return set()
    resultado: set[int] = set()
    for parte in re.split(r"\s*,\s*", str(valor).strip()):
        if not parte:
            continue
        if "-" in parte:
            inicio, fim = (int(item) for item in parte.split("-", 1))
            resultado.update(range(inicio, fim + 1))
        else:
            resultado.add(int(float(parte)))
    return resultado


def carregar_regras(caminho: Path) -> list[dict]:
    tabela = pd.read_excel(caminho)
    tabela.columns = tabela.columns.str.strip()
    regras = []
    for _, linha in tabela.dropna(subset=["Regular Recode"]).iterrows():
        recode = int(linha["Regular Recode"])
        if recode == 999:
            continue
        regras.append({
            "morfologias": expandir_codigos(linha["ICD-O-3 Histology"]),
            "topografias": expandir_codigos(linha["ICD-O-3 Primary Site"]),
            "comportamentos": expandir_codigos(linha["ICD-O-3 Behavior"]),
            "recode": f"{recode:03d}",
            "grupo_numero": recode // 10,
        })
    return regras


def classificar_iccc(topografia: str, tipo_histologico: str, regras: list[dict]) -> tuple[str, str]:
    topo_texto = re.sub(r"\D", "", topografia or "")
    hist_match = re.fullmatch(r"(\d{4})/(\d)", (tipo_histologico or "").strip())
    if len(topo_texto) < 3 or not hist_match:
        return "999", "Não classificado"
    topo = int(topo_texto[:3])
    morfologia, comportamento = map(int, hist_match.groups())
    for regra in regras:
        if (morfologia in regra["morfologias"] and topo in regra["topografias"]
                and comportamento in regra["comportamentos"]):
            numero = regra["grupo_numero"]
            return regra["recode"], GRUPOS_ICCC[numero]
    return "999", "Não classificado"


def data_rhc(valor: str) -> date | None:
    try:
        return datetime.strptime((valor or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def faixa_idade(idade: int) -> str:
    if idade <= 4:
        return "0–4"
    if idade <= 9:
        return "5–9"
    if idade <= 14:
        return "10–14"
    return "15–19"


def primeiro_tratamento(codigo: str) -> str:
    codigo = (codigo or "").strip()
    if codigo == "1":
        return "Nenhum tratamento no hospital"
    if codigo in {"0", "-9", "8"}:
        return "Outros procedimentos"
    if not codigo or codigo == "9":
        return "Sem informação"
    modalidades = [("2", "Cirurgia"), ("3", "Radioterapia"), ("4", "Quimioterapia"),
                   ("5", "Hormonioterapia"), ("6", "Transplante de medula óssea")]
    presentes = [nome for digito, nome in modalidades if digito in codigo]
    return " + ".join(presentes) if presentes else "Sem informação"


def processar_dbf(caminho: Path, regras: list[dict], agregados: Counter, qualidade: Counter) -> None:
    ano_arquivo = 2000 + int(re.search(r"(\d{2})$", caminho.stem).group(1))
    tabela = DBF(caminho, encoding="latin1", load=False, char_decode_errors="replace")
    qualidade["registros_lidos"] += len(tabela)
    for registro in tabela:
        idade_texto = (registro.get("IDADE") or "").strip()
        if not idade_texto.isdigit() or not 0 <= int(idade_texto) <= 19:
            continue
        idade = int(idade_texto)
        recode, grupo = classificar_iccc(registro.get("LOCTUPRI", ""), registro.get("TIPOHIST", ""), regras)
        diagnostico = data_rhc(registro.get("DTDIAGNO", ""))
        tratamento = data_rhc(registro.get("DATAINITRT", ""))
        dias = (tratamento - diagnostico).days if diagnostico and tratamento else None
        if dias is None:
            faixa_tempo = "Sem intervalo calculável"
        elif dias < 0:
            faixa_tempo = "Tratamento anterior ao diagnóstico informado"
        elif dias <= 30:
            faixa_tempo = "Até 30 dias"
        elif dias <= 60:
            faixa_tempo = "31–60 dias"
        else:
            faixa_tempo = "Mais de 60 dias"

        ano = int(registro.get("DTPRICON") or ano_arquivo)
        tratamento_inicial = primeiro_tratamento(registro.get("PRITRATH", ""))
        razao = RAZAO_NAO_TRATAMENTO.get((registro.get("RZNTR") or "").strip(), "Sem informação")
        chave = (
            ano, grupo, recode, SUBGRUPOS_ICCC[recode], faixa_idade(idade), SEXO.get((registro.get("SEXO") or "").strip(), "Ignorado"),
            (registro.get("ESTADRES") or "Ignorada").strip(),
            (registro.get("UFUH") or "Ignorada").strip(), faixa_tempo,
            bool(tratamento), tratamento_inicial, razao,
        )
        agregados[chave] += 1
        qualidade["casos_0_19"] += 1
        qualidade["classificados_iccc"] += recode != "999"
        qualidade["tratamento_com_data"] += tratamento is not None


def main() -> None:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Uso: gerar_rhc_pediatrico.py PACOTE_RHC.zip ICCC-2017.xlsx [SAIDA.json]")
    pacote, tabela_iccc = map(Path, sys.argv[1:3])
    saida = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("dados/rhc_pediatrico_iccc.json")
    regras = carregar_regras(tabela_iccc)
    agregados: Counter = Counter()
    qualidade: Counter = Counter()
    anos = []
    with zipfile.ZipFile(pacote) as arquivo_zip, tempfile.TemporaryDirectory(prefix="rhc_ped_") as pasta:
        for nome in sorted(n for n in arquivo_zip.namelist() if re.fullmatch(r"rhc\d{2}\.dbf", Path(n).name, re.I)):
            destino = Path(pasta) / Path(nome).name
            with arquivo_zip.open(nome) as origem, destino.open("wb") as alvo:
                shutil.copyfileobj(origem, alvo)
            processar_dbf(destino, regras, agregados, qualidade)
            anos.append(2000 + int(re.search(r"(\d{2})", destino.stem).group(1)))
            destino.unlink()

    colunas = ["ano", "grupo_iccc", "recode_iccc", "subgrupo_iccc", "faixa_etaria", "sexo", "uf_residencia",
               "uf_hospital", "faixa_tempo", "tratamento_com_data", "primeiro_tratamento", "razao_nao_tratamento"]
    dados = [dict(zip(colunas, chave), casos=casos) for chave, casos in sorted(agregados.items())]
    total = qualidade["casos_0_19"]
    payload = {
        "metadados": {
            "fonte": "Integrador RHC/INCA — base pública anonimizada do SisRHC",
            "url": "https://irhc.inca.gov.br/RHCNet/selecionaDownloadTabWin.action?local=todosho&unidFed=",
            "periodo": [min(anos), max(anos)],
            "cobertura_geografica": "Todos os estados, exceto São Paulo",
            "faixa_etaria": "0 a 19 anos",
            "classificacao": "CICI/ICCC-3, atualização IARC 2017, derivada de topografia, morfologia e comportamento CID-O-3",
            "tabela_conversao": "SEER ICCC-2017.xlsx",
            "unidade": "caso/tumor registrado no RHC; não equivale a pessoa nem a caso incidente populacional",
            "total_casos": total,
            "percentual_classificado": qualidade["classificados_iccc"] / total if total else 0,
            "percentual_com_data_tratamento": qualidade["tratamento_com_data"] / total if total else 0,
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
        },
        "dados": dados,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{saida}: {total:,} casos pediátricos; {payload['metadados']['percentual_classificado']:.1%} classificados")


if __name__ == "__main__":
    main()
