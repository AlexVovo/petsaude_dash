import json
from pathlib import Path
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def dados(nome, chave="dados"):
    return pd.DataFrame(json.loads((ROOT / "dados" / nome).read_text())[chave])


def valor(app, label):
    return next(m.value for m in app.metric if m.label == label)


def selecionar(app, label, valores):
    next(w for w in app.multiselect if w.label == label).set_value(valores)


def abrir(app, aba):
    app.session_state["aba_ativa"] = aba
    app.run(timeout=60)


class FiltrosTest(unittest.TestCase):
    def app(self):
        app = AppTest.from_file(str(ROOT / "dash_onco_pet.py")).run(timeout=60)
        self.assertFalse(app.exception)
        return app

    def test_categoria_residual_em_apac_e_custos(self):
        app = self.app()
        selecionar(app, "Tipo de câncer (SIM/SIA/SIH)", ["Outras neoplasias malignas"])
        app.run(timeout=60)
        self.assertFalse(app.exception)
        abrir(app, "Acesso")
        self.assertFalse(app.exception)
        apac = dados("apac_oncologia.json", "producao")
        esperado = int(apac.loc[apac.tipo_cancer == "Outros diagnósticos oncológicos", "apacs"].sum())
        self.assertEqual(valor(app, "Registros mensais de APAC"), f"{esperado:,}".replace(",", "."))
        abrir(app, "Custos")
        self.assertFalse(app.exception)
        custos = dados("custos_oncologia_sia_sih.json")
        esperado_custos = custos.loc[custos.tipo_cancer == "Outros diagnósticos oncológicos", "valor"].sum()
        self.assertEqual(valor(app, "Custo total em oncologia"), f"R$ {esperado_custos / 1e9:.2f} bi".replace(".", ","))

    def test_regiao_e_classificacao_rhc(self):
        app = self.app()
        selecionar(app, "Região", ["Sul"])
        app.run(timeout=60)
        self.assertFalse(app.exception)
        abrir(app, "Pediatria e suporte")
        self.assertFalse(app.exception)
        rhc = dados("rhc_pediatrico_iccc.json")
        sul = rhc[rhc.uf_residencia.isin(["PR", "SC", "RS"])]
        self.assertEqual(valor(app, "Casos registrados no RHC"), f"{sul.casos.sum():,}".replace(",", "."))
        grupo = sul.grupo_iccc.iloc[0]
        selecionar(app, "Grupo CICI/ICCC-3 (RHC)", [grupo])
        app.run(timeout=60)
        self.assertFalse(app.exception)
        abrir(app, "Pediatria e suporte")
        self.assertFalse(app.exception)
        esperado = sul.loc[sul.grupo_iccc == grupo, "casos"].sum()
        self.assertEqual(valor(app, "Casos registrados no RHC"), f"{esperado:,}".replace(",", "."))

    def test_taxa_compativel_e_unidade_apac(self):
        app = self.app()
        sim = dados("sim_oncologia_agregado.json")
        pop = dados("populacao_ibge.json")
        numerador = sim.loc[
            sim.ano.between(2000, 2024) & sim.sexo.isin(["Masculino", "Feminino"])
            & sim.faixa_etaria.isin(pop.faixa_etaria.unique()) & sim.uf.isin(pop.uf.unique()), "obitos"
        ].sum()
        denominador = pop.loc[pop.ano.between(2000, 2024), "populacao"].sum()
        self.assertEqual(valor(app, "Taxa bruta no período"), f"{numerador / denominador * 100000:.1f} / 100 mil")
        self.assertTrue(any("Taxa bruta: 2000–2024" in c.value for c in app.caption))
        abrir(app, "Acesso")
        self.assertFalse(app.exception)
        self.assertEqual(valor(app, "Registros de início por modalidade"), "762.812")
        self.assertFalse(any(m.label == "Pessoas no indicador de tempo" for m in app.metric))

    def test_sexo_ignorado_mantem_contagem_sem_taxa(self):
        app = self.app()
        selecionar(app, "Sexo", ["Ignorado"])
        app.run(timeout=60)
        self.assertFalse(app.exception)
        sim = dados("sim_oncologia_agregado.json")
        esperado = sim.loc[sim.sexo == "Ignorado", "obitos"].sum()
        self.assertEqual(valor(app, "Óbitos por câncer"), f"{esperado:,}".replace(",", "."))
        self.assertEqual(valor(app, "Taxa bruta no período"), "Indisponível")


if __name__ == "__main__":
    unittest.main()
