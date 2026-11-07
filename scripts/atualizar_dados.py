"""Atualiza o snapshot em data/ (usado quando as APIs estiverem fora do ar).

Rode de uma máquina no Brasil (as APIs do IBGE costumam bloquear acessos do exterior)
e depois faça commit da pasta data/.
Uso local:  python scripts/atualizar_dados.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import fontes  # noqa: E402

DATA = RAIZ / "data"


def main() -> None:
    DATA.mkdir(exist_ok=True)

    lspa = fontes.baixar_lspa()
    lspa.to_csv(DATA / "lspa.csv", index=False)
    print(f"LSPA: {len(lspa):,} linhas")

    macro = fontes.baixar_macro()
    macro.to_csv(DATA / "macro.csv", index=False)
    print(f"Macro: {len(macro):,} linhas")

    malha = fontes.baixar_malha_ufs()
    (DATA / "ufs.geojson").write_text(json.dumps(malha), encoding="utf-8")
    print(f"Malha: {len(malha['features'])} UFs")

    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    (DATA / "atualizado_em.txt").write_text(f"{agora:%d/%m/%Y}", encoding="utf-8")


if __name__ == "__main__":
    main()
