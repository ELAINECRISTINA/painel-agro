"""Coleta de dados públicos: IBGE (LSPA/SIDRA) e Banco Central (SGS).

As funções deste módulo não dependem do Streamlit, para poderem ser usadas
tanto pelo app quanto pelo script que atualiza o snapshot em data/.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd
import requests

IBGE_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados"
IBGE_MALHAS = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
BCB_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# LSPA - Tabela 6588 (série histórica da estimativa anual da safra)
TABELA_LSPA = 6588
ANO_INICIAL = 2016

VARIAVEIS_LSPA = {
    35: "producao_t",
    109: "area_plantada_ha",
    216: "area_colhida_ha",
    36: "rendimento_kg_ha",
}

# Categorias da classificação 48 (Produto das lavouras)
CULTURAS_LSPA = {
    39428: "Grãos (cereais, leguminosas e oleaginosas)",
    39443: "Soja",
    39441: "Milho 1ª safra",
    39442: "Milho 2ª safra",
    39429: "Algodão herbáceo",
    39432: "Arroz",
    39436: "Feijão 1ª safra",
    39437: "Feijão 2ª safra",
    39438: "Feijão 3ª safra",
    39445: "Trigo",
    39454: "Café arábica",
    39455: "Café canéfora",
    39456: "Cana-de-açúcar",
    39463: "Laranja",
}

# Séries do SGS/BCB
SERIES_BCB = {
    "dolar": (1, "Dólar comercial (venda) – R$"),
    "selic": (432, "Selic meta – % a.a."),
    "ipca": (433, "IPCA – variação mensal %"),
    "igpm": (189, "IGP-M – variação mensal %"),
}

UF_SIGLAS = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

_SESSAO = requests.Session()
_SESSAO.headers.update({"User-Agent": "painel-agro (github.com/ELAINECRISTINA/painel-agro)"})


# As APIs do IBGE costumam recusar conexões de fora do Brasil. O app (que pode
# rodar em servidores no exterior) usa tentativas rápidas e cai no snapshot;
# o script de atualização, rodado de uma máquina no Brasil, usa o modo paciente.
TENTATIVAS = 3
TIMEOUT = (10, 60)  # (conexão, leitura) em segundos


def modo_rapido() -> None:
    """Uma única tentativa com timeout curto de conexão."""
    global TENTATIVAS, TIMEOUT
    TENTATIVAS, TIMEOUT = 1, (5, 30)


def _get(url: str, params: dict | None = None):
    """GET com novas tentativas e espera progressiva."""
    ultimo_erro = None
    for i in range(TENTATIVAS):
        try:
            resp = _SESSAO.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as erro:
            ultimo_erro = erro
            if i < TENTATIVAS - 1:
                time.sleep(2 ** i)
    raise ConnectionError(f"Falha ao acessar {url}: {ultimo_erro}")


# ─────────────────────────────── IBGE ───────────────────────────────
def periodos_lspa() -> list[str]:
    """Escolhe os períodos da série: dezembro de cada ano (estimativa final
    do ano) e o levantamento mais recente disponível."""
    periodos = [p["id"] for p in _get(f"{IBGE_AGREGADOS}/{TABELA_LSPA}/periodos")]
    ultimo = periodos[-1]
    escolhidos = [p for p in periodos if p.endswith("12") and int(p[:4]) >= ANO_INICIAL]
    if ultimo not in escolhidos:
        escolhidos.append(ultimo)
    return escolhidos


def _valor(texto) -> float:
    try:
        return float(texto)
    except (TypeError, ValueError):
        return float("nan")  # o IBGE usa "-", "..." e "X" para ausência/sigilo


def parse_lspa(resposta: list) -> pd.DataFrame:
    """Converte a resposta JSON da API de agregados em formato longo."""
    linhas = []
    for variavel in resposta:
        nome_var = VARIAVEIS_LSPA.get(int(variavel["id"]), variavel["variavel"])
        for resultado in variavel["resultados"]:
            cat_id = int(next(iter(resultado["classificacoes"][0]["categoria"])))
            cultura = CULTURAS_LSPA.get(cat_id, str(cat_id))
            for serie in resultado["series"]:
                loc = serie["localidade"]
                for periodo, valor in serie["serie"].items():
                    linhas.append({
                        "periodo": periodo,
                        "cod_local": loc["id"],
                        "local": loc["nome"],
                        "nivel": loc["nivel"]["id"],
                        "cultura": cultura,
                        "variavel": nome_var,
                        "valor": _valor(valor),
                    })
    return pd.DataFrame(linhas)


def baixar_lspa() -> pd.DataFrame:
    """Baixa a LSPA para Brasil e UFs, culturas e variáveis selecionadas."""
    periodos = "|".join(periodos_lspa())
    variaveis = "|".join(str(v) for v in VARIAVEIS_LSPA)
    culturas = ",".join(str(c) for c in CULTURAS_LSPA)
    url = f"{IBGE_AGREGADOS}/{TABELA_LSPA}/periodos/{periodos}/variaveis/{variaveis}"
    resposta = _get(url, params={
        "localidades": "N1[all]|N3[all]",
        "classificacao": f"48[{culturas}]",
    })
    return parse_lspa(resposta)


def baixar_malha_ufs() -> dict:
    """GeoJSON das UFs (propriedade 'codarea' = código IBGE da UF)."""
    return _get(IBGE_MALHAS, params={
        "formato": "application/vnd.geo+json",
        "qualidade": "minima",
        "intrarregiao": "UF",
    })


# ─────────────────────────────── BCB ────────────────────────────────
def baixar_serie_bcb(codigo: int, anos: int = 10) -> pd.DataFrame:
    """Série do SGS. A API limita consultas por período a 10 anos."""
    hoje = date.today()
    inicio = hoje - timedelta(days=365 * anos - 1)
    dados = _get(BCB_SGS.format(codigo=codigo), params={
        "formato": "json",
        "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": hoje.strftime("%d/%m/%Y"),
    })
    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df[df["data"] <= pd.Timestamp(hoje)].reset_index(drop=True)


def baixar_macro() -> pd.DataFrame:
    """Todas as séries macro em formato longo (data, serie, valor)."""
    partes = []
    for chave, (codigo, _) in SERIES_BCB.items():
        df = baixar_serie_bcb(codigo)
        df["serie"] = chave
        partes.append(df)
    return pd.concat(partes, ignore_index=True)
