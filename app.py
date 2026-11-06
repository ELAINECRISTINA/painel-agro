"""Painel do Agronegócio Brasileiro – safra (IBGE/LSPA) e indicadores macro (BCB)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.carga import carregar_lspa, carregar_macro, carregar_malha
from src.fontes import SERIES_BCB
from src.transform import comparar_safras, lspa_largo, macro_mensal, ranking_ufs

st.set_page_config(page_title="Painel do Agronegócio", page_icon="🌾", layout="wide")

VERDE = "#2E7D32"
VERDE_CLARO = "#A5D6A7"
OCRE = "#C8962E"
CINZA = "#8A8F87"
ESCALA_MAPA = ["#F1F5EC", "#C5E1A5", "#7CB342", "#33691E"]

VARIAVEIS = {
    "producao_t": ("Produção", "t"),
    "area_plantada_ha": ("Área plantada", "ha"),
    "area_colhida_ha": ("Área colhida", "ha"),
    "rendimento_kg_ha": ("Rendimento médio", "kg/ha"),
}
CULTURA_PADRAO = "Soja"


# ──────────────────────────── formatação ────────────────────────────
def br(numero: float, casas: int = 0) -> str:
    if numero is None or pd.isna(numero):
        return "–"
    texto = f"{numero:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def grande(numero: float, unidade: str) -> str:
    """Formato curto: 354,5 mi t."""
    if numero is None or pd.isna(numero):
        return "–"
    if abs(numero) >= 1e6:
        return f"{br(numero / 1e6, 1)} mi {unidade}"
    if abs(numero) >= 1e3:
        return f"{br(numero / 1e3, 1)} mil {unidade}"
    return f"{br(numero)} {unidade}"


def delta(var: float | None) -> str | None:
    return None if var is None else f"{br(var, 1)}% vs ano anterior"


def layout(fig: go.Figure, altura: int = 380, safra: bool = False) -> go.Figure:
    if safra:  # rótulos como "2026 (est. set)" precisam de eixo categórico
        fig.update_xaxes(type="category")
    fig.update_layout(
        height=altura, margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.15), hovermode="x unified",
        separators=",.",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return fig


# ─────────────────────────────── dados ──────────────────────────────
try:
    lspa_bruto, origem_lspa = carregar_lspa()
    lspa = lspa_largo(lspa_bruto)
except Exception as erro:  # noqa: BLE001
    st.error(f"Não foi possível carregar os dados de safra do IBGE agora. Tente novamente em instantes.\n\n`{erro}`")
    st.stop()

try:
    macro_bruto, origem_macro = carregar_macro()
    macro = macro_mensal(macro_bruto)
except Exception:  # noqa: BLE001
    macro_bruto, macro, origem_macro = None, None, "indisponível"

culturas = sorted(lspa["cultura"].unique(), key=lambda c: (c.startswith("Grãos"), c))
periodos = lspa[["periodo", "rotulo"]].drop_duplicates().sort_values("periodo")
ultimo_periodo = periodos["periodo"].iloc[-1]
ultimo_rotulo = periodos["rotulo"].iloc[-1]

# ────────────────────────────── cabeçalho ───────────────────────────
st.title("🌾 Painel do Agronegócio Brasileiro")
st.caption(
    "Safra por cultura e estado (IBGE · LSPA) e indicadores macroeconômicos que movem o "
    "agro (Banco Central). Dados públicos, atualizados automaticamente."
)

with st.sidebar:
    st.header("Filtros")
    cultura = st.selectbox("Cultura", culturas, index=culturas.index(CULTURA_PADRAO) if CULTURA_PADRAO in culturas else 0)
    var = st.selectbox("Indicador", list(VARIAVEIS), format_func=lambda v: VARIAVEIS[v][0])
    st.divider()
    st.markdown("**Fontes**")
    st.caption(f"🌱 Safra: {origem_lspa}")
    st.caption(f"💱 Macro: {origem_macro}")
    st.caption(
        "A LSPA é uma estimativa mensal da safra do ano. Para anos encerrados usamos o "
        "levantamento de dezembro; o ano corrente mostra o levantamento mais recente."
    )
    st.divider()
    st.caption("Feito por [Elaine Cristina](https://github.com/ELAINECRISTINA)")

nome_var, unidade = VARIAVEIS[var]

aba_geral, aba_safra, aba_mapa, aba_macro, aba_dados = st.tabs(
    ["📊 Visão geral", "🌱 Safra", "🗺️ Mapa por estado", "💱 Macroeconomia", "📥 Dados"]
)

# ───────────────────────────── visão geral ──────────────────────────
with aba_geral:
    st.subheader(f"Safra {ultimo_rotulo}")
    destaques = [
        ("Grãos (cereais, leguminosas e oleaginosas)", "Grãos"),
        ("Soja", "Soja"),
        ("Milho (total)", "Milho"),
    ]
    cols = st.columns(4)
    for col, (nome_cultura, titulo) in zip(cols, destaques):
        c = comparar_safras(lspa, nome_cultura)
        col.metric(f"Produção de {titulo.lower()}", grande(c["atual"], "t"), delta(c["variacao"]))

    if macro is not None and not macro["dolar_medio"].dropna().empty:
        dolar = macro_bruto[macro_bruto["serie"] == "dolar"].sort_values("data")
        atual, ha_um_ano = dolar["valor"].iloc[-1], None
        ref = dolar[dolar["data"] <= dolar["data"].iloc[-1] - pd.DateOffset(years=1)]
        if not ref.empty:
            ha_um_ano = ref["valor"].iloc[-1]
        var_dolar = (atual / ha_um_ano - 1) * 100 if ha_um_ano else None
        cols[3].metric(
            f"Dólar em {dolar['data'].iloc[-1]:%d/%m/%Y}", f"R$ {br(atual, 2)}",
            None if var_dolar is None else f"{br(var_dolar, 1)}% em 12 meses", delta_color="inverse",
        )

    st.divider()
    esq, dir_ = st.columns([3, 2])

    cores_graos = {
        "Soja": VERDE, "Milho (total)": OCRE, "Algodão herbáceo": "#8FB573",
        "Arroz": "#D9C9A3", "Trigo": "#6B5B3E", "Feijão (total)": CINZA,
    }
    graos = lspa[(lspa["nivel"] == "N1") & (lspa["cultura"].isin(cores_graos))].copy()
    graos["producao_mi_t"] = graos["producao_t"] / 1e6
    fig = px.bar(
        graos, x="rotulo", y="producao_mi_t", color="cultura",
        color_discrete_map=cores_graos, category_orders={"cultura": list(cores_graos)},
        labels={"rotulo": "", "producao_mi_t": "Produção (milhões de t)", "cultura": ""},
        title="Produção das principais culturas de grãos – Brasil",
    )
    fig.update_traces(hovertemplate="%{y:.1f} mi t")
    esq.plotly_chart(layout(fig, safra=True), width="stretch")

    rank = ranking_ufs(lspa, "Grãos (cereais, leguminosas e oleaginosas)", ultimo_periodo, n=8)
    fig = px.bar(
        rank.iloc[::-1], x="participacao_%", y="uf", orientation="h",
        text=rank.iloc[::-1]["participacao_%"].map(lambda v: f"{br(v, 1)}%"),
        color_discrete_sequence=[VERDE],
        labels={"participacao_%": "Participação na safra de grãos (%)", "uf": ""},
        title=f"Estados que mais produzem grãos – {ultimo_rotulo}",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(range=[0, rank["participacao_%"].max() * 1.2 if not rank.empty else 1])
    dir_.plotly_chart(layout(fig).update_layout(hovermode="closest"), width="stretch")

# ──────────────────────────────── safra ─────────────────────────────
with aba_safra:
    st.subheader(f"{cultura} · {nome_var}")
    serie = lspa[(lspa["nivel"] == "N1") & (lspa["cultura"] == cultura)].sort_values("periodo")
    c = comparar_safras(lspa, cultura, var)

    m1, m2, m3 = st.columns(3)
    m1.metric(f"{nome_var} {c['rotulo']}", grande(c["atual"], unidade) if var != "rendimento_kg_ha" else f"{br(c['atual'])} {unidade}")
    m2.metric("Ano anterior", grande(c["anterior"], unidade) if var != "rendimento_kg_ha" else f"{br(c['anterior'])} {unidade}")
    m3.metric("Variação", "–" if c["variacao"] is None else f"{br(c['variacao'], 1)}%")

    fig = go.Figure()
    em_milhoes = var != "rendimento_kg_ha" and serie[var].max() >= 1e6
    y = serie[var] / 1e6 if em_milhoes else serie[var]
    unidade_eixo = f"milhões de {unidade}" if em_milhoes else unidade
    fig.add_trace(go.Scatter(
        x=serie["rotulo"], y=y, mode="lines+markers", name=nome_var,
        line=dict(color=VERDE, width=3), marker=dict(size=8),
        hovertemplate=("%{y:,.1f} " if em_milhoes else "%{y:,.0f} ") + unidade_eixo + "<extra></extra>",
    ))
    fig.update_layout(title=f"Evolução – Brasil ({unidade_eixo})")
    st.plotly_chart(layout(fig, safra=True), width="stretch")

    col_a, col_b = st.columns(2)
    escolha = col_a.selectbox("Ano para o ranking", periodos["periodo"][::-1].tolist(),
                              format_func=lambda p: periodos.set_index("periodo").loc[p, "rotulo"])
    rank = ranking_ufs(lspa, cultura, escolha, var if var != "rendimento_kg_ha" else "producao_t", n=10)
    if var == "rendimento_kg_ha":
        col_b.info("O ranking de rendimento médio usa os estados com maior produção.")
        rend = lspa[(lspa["cultura"] == cultura) & (lspa["periodo"] == escolha) & (lspa["uf"].isin(rank["uf"]))]
        fig = px.bar(rend.sort_values(var), x=var, y="uf", orientation="h",
                     color_discrete_sequence=[OCRE], labels={var: "kg/ha", "uf": ""})
    else:
        fig = px.bar(rank.iloc[::-1], x=var, y="uf", orientation="h",
                     hover_data={"participacao_%": True},
                     color_discrete_sequence=[VERDE], labels={var: f"{nome_var} ({unidade})", "uf": ""})
    fig.update_layout(title=f"Top 10 estados – {cultura}")
    st.plotly_chart(layout(fig, 420).update_layout(hovermode="closest"), width="stretch")

# ──────────────────────────────── mapa ──────────────────────────────
with aba_mapa:
    malha = carregar_malha()
    escolha_mapa = st.selectbox("Levantamento", periodos["periodo"][::-1].tolist(), key="periodo_mapa",
                                format_func=lambda p: periodos.set_index("periodo").loc[p, "rotulo"])
    dados_mapa = lspa[(lspa["nivel"] == "N3") & (lspa["cultura"] == cultura) & (lspa["periodo"] == escolha_mapa)]
    if malha is None:
        st.warning("Malha dos estados indisponível no momento.")
    elif dados_mapa[var].dropna().empty:
        st.info("Sem dados para essa combinação.")
    else:
        fig = px.choropleth(
            dados_mapa, geojson=malha, locations="cod_local", featureidkey="properties.codarea",
            color=var, hover_name="local", color_continuous_scale=ESCALA_MAPA,
            labels={var: f"{nome_var} ({unidade})"},
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0),
                          paper_bgcolor="rgba(0,0,0,0)", separators=",.")
        st.plotly_chart(fig, width="stretch")
        st.caption(f"{cultura} · {nome_var} por estado · IBGE/LSPA. Estados em branco não têm produção relevante ou dado divulgado.")

# ───────────────────────────── macroeconomia ────────────────────────
with aba_macro:
    if macro is None:
        st.warning("Indicadores do Banco Central indisponíveis no momento.")
    else:
        st.subheader("Câmbio, juros e inflação")
        st.caption("O dólar define a receita de quem exporta e o custo dos insumos importados; "
                   "a Selic encarece o crédito para máquinas e custeio.")
        fig = px.line(macro, x="mes", y="dolar_medio", labels={"mes": "", "dolar_medio": "R$"},
                      title="Dólar comercial – média mensal", color_discrete_sequence=[OCRE])
        fig.update_traces(hovertemplate="R$ %{y:.2f}<extra></extra>", line_width=2.5)
        st.plotly_chart(layout(fig), width="stretch")

        longo = macro.melt(id_vars="mes", value_vars=["selic", "ipca_12m", "igpm_12m"],
                           var_name="indicador", value_name="valor").dropna()
        nomes = {"selic": "Selic (meta, % a.a.)", "ipca_12m": "IPCA 12 meses (%)", "igpm_12m": "IGP-M 12 meses (%)"}
        longo["indicador"] = longo["indicador"].map(nomes)
        fig = px.line(longo, x="mes", y="valor", color="indicador",
                      color_discrete_sequence=[VERDE, OCRE, CINZA],
                      labels={"mes": "", "valor": "%", "indicador": ""}, title="Juros x inflação")
        fig.update_traces(hovertemplate="%{y:.2f}%", line_width=2.5)
        st.plotly_chart(layout(fig), width="stretch")
        st.caption("Fonte: Banco Central do Brasil – SGS (séries " +
                   ", ".join(str(c) for c, _ in SERIES_BCB.values()) + ").")

# ──────────────────────────────── dados ─────────────────────────────
with aba_dados:
    st.subheader("Base de safra tratada")
    filtro = lspa[lspa["cultura"] == cultura][
        ["rotulo", "local", "uf", "cultura"] + list(VARIAVEIS)
    ].rename(columns={"rotulo": "safra", **{k: f"{v[0]} ({v[1]})" for k, v in VARIAVEIS.items()}})
    st.dataframe(filtro, width="stretch", hide_index=True)
    st.download_button("⬇️ Baixar CSV da cultura selecionada",
                       filtro.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"safra_{cultura.lower().replace(' ', '_')}.csv", mime="text/csv")
