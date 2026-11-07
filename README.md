# 🌾 Painel do Agronegócio Brasileiro

**Dashboard interativo com a safra brasileira por cultura e estado e os indicadores macroeconômicos que movem o agro, alimentado por APIs públicas e atualizado automaticamente.**

🔗 **Demo online:** _em breve_

---

## 🎯 Que perguntas ele responde

- Quanto o Brasil deve colher este ano de soja, milho, algodão, café e outras culturas, e como isso se compara ao ano anterior?
- Quais estados lideram cada cultura e qual a participação de cada um?
- Como evoluíram área plantada, produção e produtividade (kg/ha) nos últimos 10 anos?
- Como andam o dólar, a Selic, o IPCA e o IGP-M, que afetam receita de exportação, custo de insumos e crédito rural?

## 🧭 O que tem no painel

| Aba | Conteúdo |
|---|---|
| 📊 **Visão geral** | Safra de grãos, soja e milho do ano corrente vs ano anterior; dólar; composição da safra; ranking dos estados |
| 🌱 **Safra** | Série histórica por cultura e indicador (produção, área plantada, área colhida, rendimento); top 10 estados |
| 🗺️ **Mapa por estado** | Mapa coroplético por cultura, indicador e ano |
| 💱 **Macroeconomia** | Dólar (média mensal), Selic e inflação acumulada em 12 meses |
| 📥 **Dados** | Tabela tratada com download em CSV |

## 🏗️ Arquitetura

```
 APIs públicas                    Tratamento                 App
┌──────────────────────┐      ┌─────────────────────┐     ┌──────────────┐
│ IBGE · SIDRA (LSPA)   │─────▶│ src/fontes.py       │────▶│ app.py       │
│ IBGE · Malhas (UFs)   │      │  coleta + retries   │     │ Streamlit    │
│ BCB · SGS             │      │ src/transform.py    │     │ + Plotly     │
└──────────────────────┘      │  formato largo,     │     └──────▲───────┘
          │                    │  totais, 12 meses   │            │ plano B
          ▼                    └─────────────────────┘     ┌──────┴───────┐
 scripts/atualizar_dados.py ─────────────────────────────▶ │ data/ snapshot│
                                                           └──────────────┘
```

- **Dados ao vivo com cache:** o app tenta as APIs com uma consulta rápida e guarda o resultado por 6 horas.
- **Plano B:** se a API não responder, o app usa o snapshot versionado em `data/`. Isso é importante porque as APIs do IBGE costumam recusar acessos de fora do Brasil, e servidores de hospedagem como o Streamlit Community Cloud ficam no exterior.
- **Qualidade:** testes automatizados com `pytest`, executados pelo GitHub Actions a cada push.
- **Tratamentos:** soma das safras de milho e feijão e das espécies de café (arábica + canéfora) em um total com rendimento recalculado; inflação acumulada em 12 meses; participação dos estados no total nacional.

## 📚 Fontes

| Fonte | Dado | Acesso |
|---|---|---|
| IBGE – LSPA (tabela 6588) | Área plantada, área colhida, produção e rendimento por cultura e UF | API de agregados do SIDRA |
| IBGE – Malhas | Contorno dos estados | API de malhas |
| Banco Central – SGS | Dólar (1), Selic meta (432), IPCA (433), IGP-M (189) | API do SGS |

> A LSPA é uma estimativa mensal da safra do ano. Para anos encerrados o painel usa o levantamento de dezembro; o ano corrente mostra o levantamento mais recente.

## 🚀 Como rodar

```bash
git clone https://github.com/ELAINECRISTINA/painel-agro.git
cd painel-agro
pip install -r requirements.txt
streamlit run app.py
```

Testes e atualização do snapshot (rode de uma conexão no Brasil e faça commit da pasta `data/`):

```bash
python -m pytest
python scripts/atualizar_dados.py
```

## 🛠️ Stack

`Python` · `Streamlit` · `Plotly` · `Pandas` · `Requests` · `Pytest` · `GitHub Actions`

## 🗺️ Próximos passos

- [ ] Preços agrícolas (CEPEA) e relação preço × câmbio
- [ ] Exportações do agro por produto e destino (Comex Stat)
- [ ] Orquestração com Airflow e modelagem com dbt

---

Feito por **Elaine Cristina** · [LinkedIn](https://www.linkedin.com/in/elaine-cristina-silva-1650bb170/) · [GitHub](https://github.com/ELAINECRISTINA)
