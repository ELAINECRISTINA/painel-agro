"""Tratamento dos dados: formato largo, totais por cultura e indicadores macro."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.fontes import UF_SIGLAS

COLUNAS_VARIAVEIS = ["producao_t", "area_plantada_ha", "area_colhida_ha", "rendimento_kg_ha"]
SOMAVEIS = ["producao_t", "area_plantada_ha", "area_colhida_ha"]

# Culturas que o IBGE divulga por safra e que somamos em um total
TOTAIS = {
    "Milho (total)": ["Milho 1ª safra", "Milho 2ª safra"],
    "Feijão (total)": ["Feijão 1ª safra", "Feijão 2ª safra", "Feijão 3ª safra"],
}
# Componentes que não aparecem nos filtros (ficam só no total)
OCULTAS = ["Feijão 1ª safra", "Feijão 2ª safra", "Feijão 3ª safra"]

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def lspa_largo(longo: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por período × local × cultura, uma coluna por variável."""
    largo = (
        longo.pivot_table(
            index=["periodo", "cod_local", "local", "nivel", "cultura"],
            columns="variavel", values="valor", aggfunc="first",
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for col in COLUNAS_VARIAVEIS:
        if col not in largo.columns:
            largo[col] = np.nan

    largo = pd.concat([largo, _totais(largo)], ignore_index=True)
    largo = largo[~largo["cultura"].isin(OCULTAS)]

    largo["periodo"] = largo["periodo"].astype(str)
    largo["cod_local"] = largo["cod_local"].astype(str)
    largo["ano"] = largo["periodo"].str[:4].astype(int)
    mes = largo["periodo"].str[4:].astype(int)
    largo["final_do_ano"] = mes == 12
    largo["rotulo"] = np.where(
        largo["final_do_ano"],
        largo["ano"].astype(str),
        largo["ano"].astype(str) + " (est. " + mes.map(lambda m: MESES[m - 1]) + ")",
    )
    largo["uf"] = largo["cod_local"].map(UF_SIGLAS)
    return largo.sort_values(["cultura", "nivel", "local", "periodo"]).reset_index(drop=True)


def _totais(largo: pd.DataFrame) -> pd.DataFrame:
    """Soma produção e áreas das safras e recalcula o rendimento médio."""
    chaves = ["periodo", "cod_local", "local", "nivel"]
    partes = []
    for nome, componentes in TOTAIS.items():
        sub = largo[largo["cultura"].isin(componentes)]
        if sub.empty:
            continue
        soma = sub.groupby(chaves, as_index=False)[SOMAVEIS].sum(min_count=1)
        soma["cultura"] = nome
        soma["rendimento_kg_ha"] = rendimento(soma["producao_t"], soma["area_colhida_ha"])
        partes.append(soma)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def rendimento(producao_t: pd.Series, area_colhida_ha: pd.Series) -> pd.Series:
    """Rendimento médio em kg/ha."""
    area = area_colhida_ha.replace(0, np.nan)
    return (producao_t * 1000 / area).round(0)


def variacao(atual: float, anterior: float) -> float | None:
    """Variação percentual; None quando não é possível calcular."""
    if anterior is None or atual is None or pd.isna(anterior) or pd.isna(atual) or anterior == 0:
        return None
    return (atual / anterior - 1) * 100


def comparar_safras(largo: pd.DataFrame, cultura: str, variavel: str = "producao_t") -> dict:
    """Compara o levantamento mais recente (Brasil) com o ano anterior."""
    br = largo[(largo["nivel"] == "N1") & (largo["cultura"] == cultura)].sort_values("periodo")
    if br.empty:
        return {"atual": None, "anterior": None, "variacao": None, "rotulo": "-"}
    ultimo = br.iloc[-1]
    anterior = br[(br["ano"] == ultimo["ano"] - 1) & br["final_do_ano"]]
    valor_ant = anterior[variavel].iloc[0] if not anterior.empty else None
    return {
        "atual": ultimo[variavel],
        "anterior": valor_ant,
        "variacao": variacao(ultimo[variavel], valor_ant),
        "rotulo": ultimo["rotulo"],
    }


def ranking_ufs(largo: pd.DataFrame, cultura: str, periodo: str,
                variavel: str = "producao_t", n: int = 10) -> pd.DataFrame:
    """Maiores UFs e sua participação no total nacional."""
    sel = largo[(largo["cultura"] == cultura) & (largo["periodo"] == periodo)]
    ufs = sel[sel["nivel"] == "N3"].dropna(subset=[variavel])
    total = sel.loc[sel["nivel"] == "N1", variavel].sum()
    top = ufs.nlargest(n, variavel)[["uf", "local", variavel]].copy()
    top["participacao_%"] = (top[variavel] / total * 100).round(1) if total else np.nan
    return top.reset_index(drop=True)


def macro_mensal(macro: pd.DataFrame) -> pd.DataFrame:
    """Indicadores mensais: dólar médio, Selic no fim do mês e
    inflação acumulada em 12 meses (IPCA e IGP-M)."""
    macro = macro.copy()
    macro["data"] = pd.to_datetime(macro["data"])
    macro["mes"] = macro["data"].dt.to_period("M").dt.to_timestamp()

    def serie(chave, agg):
        s = macro[macro["serie"] == chave]
        return s.groupby("mes")["valor"].agg(agg) if not s.empty else pd.Series(dtype=float)

    out = pd.DataFrame({
        "dolar_medio": serie("dolar", "mean"),
        "selic": serie("selic", "last"),
        "ipca_mes": serie("ipca", "last"),
        "igpm_mes": serie("igpm", "last"),
    })
    for col in ["ipca", "igpm"]:
        mensal = out[f"{col}_mes"] / 100 + 1
        out[f"{col}_12m"] = (mensal.rolling(12, min_periods=12).apply(np.prod, raw=True) - 1) * 100
    return out.reset_index().rename(columns={"index": "mes"})
