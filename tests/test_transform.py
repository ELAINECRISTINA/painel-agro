"""Testes do tratamento, usando o formato real de resposta da API do IBGE."""
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fontes import parse_lspa  # noqa: E402
from src.transform import comparar_safras, lspa_largo, macro_mensal, ranking_ufs, variacao  # noqa: E402


def _resultado(cat_id, cat_nome, series):
    return {
        "classificacoes": [{"id": "48", "nome": "Produto das lavouras", "categoria": {str(cat_id): cat_nome}}],
        "series": [
            {"localidade": {"id": loc_id, "nivel": {"id": nivel, "nome": ""}, "nome": nome}, "serie": serie}
            for loc_id, nivel, nome, serie in series
        ],
    }


# Valores reais da LSPA (dez/2025 e set/2026) para Brasil, SP e MT
RESPOSTA = [
    {"id": "35", "variavel": "Produção", "unidade": "Toneladas", "resultados": [
        _resultado(39443, "1.17 Soja", [
            ("1", "N1", "Brasil", {"202512": "166054076", "202609": "174983776"}),
            ("35", "N3", "São Paulo", {"202512": "5387912", "202609": "5368800"}),
            ("51", "N3", "Mato Grosso", {"202512": "50175032", "202609": "50665337"}),
        ]),
        _resultado(39441, "1.15 Milho (1ª Safra)", [
            ("1", "N1", "Brasil", {"202512": "25729396", "202609": "29715196"}),
        ]),
        _resultado(39442, "1.16 Milho (2ª Safra)", [
            ("1", "N1", "Brasil", {"202512": "116005049", "202609": "113633533"}),
        ]),
    ]},
    {"id": "216", "variavel": "Área colhida", "unidade": "Hectares", "resultados": [
        _resultado(39441, "1.15 Milho (1ª Safra)", [("1", "N1", "Brasil", {"202512": "4000000", "202609": "-"})]),
        _resultado(39442, "1.16 Milho (2ª Safra)", [("1", "N1", "Brasil", {"202512": "17000000", "202609": "..."})]),
    ]},
]


def test_parse_lspa_formato_longo():
    df = parse_lspa(RESPOSTA)
    assert set(df.columns) == {"periodo", "cod_local", "local", "nivel", "cultura", "variavel", "valor"}
    soja_br = df[(df["cultura"] == "Soja") & (df["cod_local"] == "1") & (df["periodo"] == "202609")]
    assert soja_br["valor"].iloc[0] == 174983776
    # símbolos do IBGE viram NaN
    assert df[df["periodo"] == "202609"].query("variavel == 'area_colhida_ha'")["valor"].isna().all()


def test_total_de_milho_e_rendimento():
    largo = lspa_largo(parse_lspa(RESPOSTA))
    milho = largo[(largo["cultura"] == "Milho (total)") & (largo["periodo"] == "202512")].iloc[0]
    assert milho["producao_t"] == 25729396 + 116005049
    assert milho["area_colhida_ha"] == 21000000
    assert milho["rendimento_kg_ha"] == round((25729396 + 116005049) * 1000 / 21000000)


def test_rotulos_e_ufs():
    largo = lspa_largo(parse_lspa(RESPOSTA))
    assert set(largo["rotulo"]) == {"2025", "2026 (est. set)"}
    assert set(largo.loc[largo["nivel"] == "N3", "uf"]) == {"SP", "MT"}


def test_comparacao_com_ano_anterior():
    largo = lspa_largo(parse_lspa(RESPOSTA))
    c = comparar_safras(largo, "Soja")
    assert c["rotulo"] == "2026 (est. set)"
    assert math.isclose(c["variacao"], (174983776 / 166054076 - 1) * 100)


def test_ranking_participacao():
    largo = lspa_largo(parse_lspa(RESPOSTA))
    rank = ranking_ufs(largo, "Soja", "202609")
    assert rank["uf"].tolist() == ["MT", "SP"]
    assert rank.loc[0, "participacao_%"] == round(50665337 / 174983776 * 100, 1)


def test_variacao_sem_base():
    assert variacao(10, 0) is None
    assert variacao(10, None) is None


def test_macro_ipca_acumulado():
    datas = pd.date_range("2025-01-01", periods=12, freq="MS")
    macro = pd.DataFrame({"data": datas, "serie": "ipca", "valor": [0.5] * 12})
    out = macro_mensal(macro)
    assert math.isclose(out["ipca_12m"].iloc[-1], (1.005 ** 12 - 1) * 100)
