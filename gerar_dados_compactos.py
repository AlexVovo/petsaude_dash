"""Gera e confere as cópias Parquet usadas para reduzir memória na hospedagem."""
import json
from pathlib import Path

import pandas as pd

from dados_compactos import resumo_arquivo


def gerar(pasta: Path) -> None:
    destino = pasta / "compactados"
    destino.mkdir(exist_ok=True)
    for fonte in sorted(pasta.glob("*.json")):
        payload = json.loads(fonte.read_text(encoding="utf-8"))
        tabelas = {}
        for chave, registros in payload.items():
            if not isinstance(registros, list):
                continue
            original = pd.DataFrame(registros)
            compacto = original.copy()
            for coluna in compacto.select_dtypes(include="object"):
                if compacto[coluna].map(lambda valor: isinstance(valor, str)).all():
                    compacto[coluna] = compacto[coluna].astype("string[pyarrow]")
            # A lista de habilitações do CNES é mantida como lista no Parquet.
            nome = f"{fonte.stem}_{chave}.parquet"
            compacto.to_parquet(destino / nome, index=False, compression="zstd")
            restaurado = pd.read_parquet(destino / nome)
            # Compara valores, incluindo listas convertidas em arrays pelo Arrow.
            for coluna in original:
                esperado = original[coluna].map(lambda v: list(v) if isinstance(v, list) else v)
                obtido = restaurado[coluna].map(lambda v: v.tolist() if hasattr(v, "tolist") else v)
                pd.testing.assert_series_equal(esperado, obtido, check_dtype=False)
            tabelas[chave] = nome
        manifesto = {"sha256_fonte": resumo_arquivo(fonte),
                     "metadados": payload["metadados"], "tabelas": tabelas}
        (destino / f"{fonte.stem}.json").write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{fonte.name}: valores conferidos", flush=True)


if __name__ == "__main__":
    gerar(Path(__file__).resolve().parent / "dados")
