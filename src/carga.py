"""Carregamento com cache e plano B.

Ordem de tentativa para cada base:
1. API pública ao vivo (IBGE / BCB);
2. snapshot salvo em data/ (atualizado semanalmente pelo GitHub Actions).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src import fontes

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_TTL = 6 * 60 * 60  # 6 horas


def _snapshot_info() -> str:
    arquivo = DATA_DIR / "atualizado_em.txt"
    return arquivo.read_text(encoding="utf-8").strip() if arquivo.exists() else "data desconhecida"


@st.cache_data(ttl=CACHE_TTL, show_spinner="Buscando a safra no IBGE…")
def carregar_lspa() -> tuple[pd.DataFrame, str]:
    try:
        return fontes.baixar_lspa(), f"API IBGE ao vivo · {datetime.now():%d/%m/%Y %H:%M}"
    except Exception:
        arquivo = DATA_DIR / "lspa.csv"
        if not arquivo.exists():
            raise
        df = pd.read_csv(arquivo, dtype={"periodo": str, "cod_local": str})
        return df, f"snapshot de {_snapshot_info()}"


@st.cache_data(ttl=CACHE_TTL, show_spinner="Buscando indicadores no Banco Central…")
def carregar_macro() -> tuple[pd.DataFrame, str]:
    try:
        return fontes.baixar_macro(), f"API BCB ao vivo · {datetime.now():%d/%m/%Y %H:%M}"
    except Exception:
        arquivo = DATA_DIR / "macro.csv"
        if not arquivo.exists():
            raise
        df = pd.read_csv(arquivo, parse_dates=["data"])
        return df, f"snapshot de {_snapshot_info()}"


def _area(anel: list) -> float:
    """Área com sinal (fórmula do laço): positiva = sentido anti-horário."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(anel, anel[1:])) / 2


def _orientar_para_plotly(geojson: dict) -> dict:
    """O mapa do Plotly (d3-geo) espera o contorno externo no sentido horário e
    os buracos no anti-horário; com a orientação trocada o polígono "vira" o
    mundo inteiro e o estado não aparece. Aqui garantimos a orientação certa."""
    for feature in geojson.get("features", []):
        geom = feature.get("geometry") or {}
        poligonos = geom.get("coordinates", [])
        if geom.get("type") == "Polygon":
            poligonos = [poligonos]
        elif geom.get("type") != "MultiPolygon":
            continue
        for poligono in poligonos:
            for i, anel in enumerate(poligono):
                externo = i == 0
                if (externo and _area(anel) > 0) or (not externo and _area(anel) < 0):
                    anel.reverse()
    return geojson


@st.cache_data(ttl=7 * 24 * 60 * 60, show_spinner=False)
def carregar_malha() -> dict | None:
    arquivo = DATA_DIR / "ufs.geojson"
    try:
        if arquivo.exists():
            malha = json.loads(arquivo.read_text(encoding="utf-8"))
        else:
            malha = fontes.baixar_malha_ufs()
    except Exception:
        return None
    return _orientar_para_plotly(malha)
