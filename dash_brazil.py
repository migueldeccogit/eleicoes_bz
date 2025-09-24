import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import datetime
import re

# Configuração da página com tema brasileiro
st.set_page_config(
    page_title="Eleições Brasil 2026",
    page_icon="🇧🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Cores dos partidos brasileiros (cores oficiais e representativas)
PARTY_COLORS = {
    "Lula": "#FF0000",  # Vermelho PT
    "Tarcísio": "#0070C5",  # Azul Republicanos
    "Ciro Gomes": "#C21E56",  # Rosa PDT
    "Ratinho Jr.": "#FFA500",  # Laranja PSD
    "Zema": "#F3701B",  # Laranja Novo
    "Caiado": "#2FBEF2",  # Azul claro União Brasil
    "Outros": "#808080",  # Cinza
    "Branco / Nulo / Indeciso": "#404040",  # Cinza escuro
}

# Headers para requisição
headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
}

URL = "https://en.wikipedia.org/wiki/Opinion_polling_for_the_2026_Brazilian_presidential_election"

# Mapeamento de nomes
de_para = {
    "Polling firm": "Instituto",
    "Polling period": "Data",
    "Lula": "Lula",
    "Freitas": "Tarcísio",
    "Gomes": "Ciro Gomes",
    "Ratinho": "Ratinho Jr.",
    "Zema": "Zema",
    "Caiado": "Caiado",
    "Others[a]": "Outros",
    "BlankNullUndec.[b]": "Branco / Nulo / Indeciso",
}


def scrapping_wikipedia(URL, headers):
    """Função para extrair dados da Wikipedia"""
    response = requests.get(URL, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    tables = soup.find_all("table", {"class": "wikitable"})
    table_25 = tables[0]

    columns = []
    header_rows = table_25.find_all("tr")[:2]

    for th in header_rows[0].find_all(["th", "td"]):
        if th.get_text(strip=True):
            columns.append(th.get_text(strip=True))

    data = []
    for row in table_25.find_all("tr")[2:]:
        cells = row.find_all(["td", "th"])
        if len(cells) >= len(columns):
            row_data = []
            for i, cell in enumerate(cells[: len(columns)]):
                text = cell.get_text(strip=True)
                text = re.sub(r"\[.*?\]", "", text)
                text = text.replace("\n", " ").strip()
                row_data.append(text if text else "—")
            data.append(row_data)

    df = pd.DataFrame(data, columns=columns)
    return df


def corrige_datas(df, col_date):
    """Função para corrigir formato das datas"""
    df[col_date] = df[col_date].apply(lambda x: x.split("–")[-1].strip())
    df[col_date] = pd.to_datetime(df[col_date], format="%d %b %Y", errors="coerce")
    return df


@st.cache_data(ttl=1800)  # Cache por 30 minutos
def carregar_dados():
    """Carrega e processa os dados"""
    try:
        df_25 = scrapping_wikipedia(URL, headers)
        df_25 = corrige_datas(df_25, "Polling period")
        df_25 = df_25.rename(columns=de_para)
        df_25 = df_25[list(de_para.values())]
        df_25 = df_25.replace("—", np.nan)
        df_25 = df_25.sort_values("Data")

        # Converter colunas numéricas
        candidatos = [
            "Lula",
            "Tarcísio",
            "Ciro Gomes",
            "Ratinho Jr.",
            "Zema",
            "Caiado",
            "Outros",
            "Branco / Nulo / Indeciso",
        ]
        for col in candidatos:
            if col in df_25.columns:
                df_25[col] = pd.to_numeric(df_25[col], errors="coerce")

        # Calcular médias móveis
        df_media = df_25.groupby("Data")[candidatos].mean().reset_index()
        df_media = df_media.sort_values("Data")

        # Média móvel de 3 períodos (adaptado para Brasil)
        for col in candidatos:
            if col in df_media.columns:
                df_media[col] = df_media[col].rolling(window=3, min_periods=1).mean()

        return df_25, df_media

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(), pd.DataFrame()


# Carregar dados
df_original, df_media = carregar_dados()

if df_original.empty:
    st.error("Não foi possível carregar os dados. Verifique sua conexão.")
    st.stop()

# HEADER PRINCIPAL

st.title("ELEIÇÕES PRESIDENCIAIS BRASIL 2026", )
st.markdown("Acompanhamento das Pesquisas de Intenção de Voto")

# SIDEBAR
st.sidebar.header("🔧 Filtros e Configurações")

# Filtros
institutos = df_original["Instituto"].dropna().unique()
candidatos_principais = [
    "Lula",
    "Tarcísio",
    "Zema",
    "Branco / Nulo / Indeciso",
]

# Data range
if not df_original["Data"].isna().all():
    min_date = df_original["Data"].min().date()
    max_date = df_original["Data"].max().date()

    selected_date_range = st.sidebar.slider(
        "📅 Período de Análise",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
    )
else:
    selected_date_range = (datetime.date.today(), datetime.date.today())

# Instituto
selected_instituto = st.sidebar.selectbox(
    "🏢 Instituto de Pesquisa", options=["Todos"] + list(institutos)
)

# Candidatos
selected_candidates = st.pills(
    "👥 Candidatos",
    options=candidatos_principais + ["Ciro Gomes", "Ratinho Jr.", "Caiado", "Outros"],
    default=candidatos_principais,
    selection_mode="multi",
)

# MÉTRICAS PRINCIPAIS
st.subheader("📊 Cenário Atual - Última Pesquisa")

if not df_media.empty and not df_media["Data"].isna().all():
    ultima_pesquisa = df_media.loc[df_media["Data"] == df_media["Data"].max()]

    cols_metricas = st.columns(4)

    for i, candidato in enumerate(candidatos_principais[:4]):
        with cols_metricas[i]:
            if candidato in ultima_pesquisa.columns:
                valor = ultima_pesquisa[candidato].iloc[0]
                if not pd.isna(valor):
                    st.metric(label=candidato, value=f"{valor:.1f}%", delta=None)

# FILTRAR DADOS
df_filtered = df_original.copy()
df_media_filtered = df_media.copy()

# Filtro por data
df_filtered = df_filtered[
    (df_filtered["Data"] >= pd.to_datetime(selected_date_range[0]))
    & (df_filtered["Data"] <= pd.to_datetime(selected_date_range[1]))
]
df_media_filtered = df_media_filtered[
    (df_media_filtered["Data"] >= pd.to_datetime(selected_date_range[0]))
    & (df_media_filtered["Data"] <= pd.to_datetime(selected_date_range[1]))
]

# Filtro por instituto
if selected_instituto != "Todos":
    df_filtered = df_filtered[df_filtered["Instituto"] == selected_instituto]

# GRÁFICOS PRINCIPAIS
col1, col2 = st.columns(2)

# Gráfico 1: Evolução por Instituto
with col1:
    st.subheader(f"📈 Evolução - {selected_instituto}")

    fig1 = go.Figure()

    for candidato in selected_candidates:
        if candidato in df_filtered.columns:
            data_candidato = df_filtered[df_filtered[candidato].notna()]
            fig1.add_trace(
                go.Scatter(
                    x=data_candidato["Data"],
                    y=data_candidato[candidato],
                    mode="lines+markers",
                    name=candidato,
                    line=dict(color=PARTY_COLORS.get(candidato, "#000000"), width=1.5),
                    marker=dict(size=8),
                )
            )

    # Linha dos 50% (maioria absoluta)
    if not df_filtered.empty:
        fig1.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="")

    fig1.update_layout(
        xaxis_title="Data",
        yaxis_title="Intenção de Voto (%)",
        template="plotly_white",
        hovermode="x unified",
    )

    st.plotly_chart(fig1, use_container_width=True)

# Gráfico 2: Média de Todas as Pesquisas
with col2:
    st.subheader("📊 Média Móvel - Todos os Institutos")

    fig2 = go.Figure()

    # Pontos individuais (transparentes)
    for candidato in selected_candidates:
        if candidato in df_filtered.columns:
            data_candidato = df_original[df_original[candidato].notna()]
            data_candidato = data_candidato[
                (data_candidato["Data"] >= pd.to_datetime(selected_date_range[0]))
                & (data_candidato["Data"] <= pd.to_datetime(selected_date_range[1]))
            ]
            fig2.add_trace(
                go.Scatter(
                    x=data_candidato["Data"],
                    y=data_candidato[candidato],
                    mode="markers",
                    name=f"{candidato} (dados)",
                    marker=dict(
                        color=PARTY_COLORS.get(candidato, "#000000"),
                        opacity=0.3,
                        size=5,
                    ),
                    showlegend=False,
                )
            )

    # Linhas de média móvel
    for candidato in selected_candidates:
        if candidato in df_media_filtered.columns:
            data_candidato = df_media_filtered[df_media_filtered[candidato].notna()]
            fig2.add_trace(
                go.Scatter(
                    x=data_candidato["Data"],
                    y=data_candidato[candidato],
                    mode="lines",
                    name=candidato,
                    line=dict(color=PARTY_COLORS.get(candidato, "#000000"), width=2),
                    line_shape="spline",
                )
            )

    fig2.add_hline(
        y=50,
        line_dash="dash",
        line_color="red",
    )

    fig2.update_layout(
        xaxis_title="Data",
        yaxis_title="Intenção de Voto (%)",
        template="plotly_white",
        hovermode="x unified",
    )

    st.plotly_chart(fig2, use_container_width=True)

# RANKING DE INSTITUTOS
st.subheader("🏆 Atividade dos Institutos de Pesquisa")

instituto_counts = df_original["Instituto"].value_counts()
fig4 = go.Figure(
    go.Bar(
        x=instituto_counts.values,
        y=instituto_counts.index,
        orientation="h",
        marker=dict(color="#009739"),
    )
)

fig4.update_layout(
    title="Número de Pesquisas por Instituto",
    xaxis_title="Quantidade de Pesquisas",
    yaxis_title="Instituto",
    template="plotly_white",
)

st.plotly_chart(fig4, use_container_width=True)

# TABELA DE DADOS
st.subheader("📋 Dados das Pesquisas")

# Mostrar apenas as colunas selecionadas
colunas_mostrar = ["Instituto", "Data"] + selected_candidates
df_display = df_filtered[colunas_mostrar].copy()

# Ordenar por data (mais recente primeiro)
df_display = df_display.sort_values("Data", ascending=False)

# Formatar data
df_display["Data"] = df_display["Data"].dt.strftime("%d/%m/%Y")


st.dataframe(df_display, use_container_width=True)

# FOOTER
st.markdown("---")
st.markdown(
    """
<div style="text-align: center; color: #666;">
    <p>🇧🇷 Dashboard desenvolvido para acompanhamento das Eleições Presidenciais 2026</p>
    <p>Dados extraídos da Wikipedia | Atualização automática</p>
</div>
""",
    unsafe_allow_html=True,
)



