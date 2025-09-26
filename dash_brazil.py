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


def scrapping_wikipedia(URL, headers, table):
    """Função para extrair dados da Wikipedia"""
    response = requests.get(URL, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    tables = soup.find_all("table", {"class": "wikitable"})
    table_25 = tables[table]

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


def processar_dados(df, candidatos):
    """Processa e calcula médias móveis para os dados"""
    for col in candidatos:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcular médias móveis
    df_media = df.groupby("Data")[candidatos].mean().reset_index()
    df_media = df_media.sort_values("Data")

    # Média móvel de 3 períodos
    for col in candidatos:
        if col in df_media.columns:
            df_media[col] = df_media[col].rolling(window=3, min_periods=1).mean()

    return df, df_media


@st.cache_data(ttl=1800)  # Cache por 30 minutos
def carregar_dados():
    """Carrega e processa os dados"""
    try:
        # Primeiro turno
        df_25 = scrapping_wikipedia(URL, headers, table=0)
        df_25 = corrige_datas(df_25, "Polling period")
        df_25 = df_25.rename(columns=de_para)
        df_25 = df_25[list(de_para.values())]
        df_25 = df_25.replace("—", np.nan)
        df_25 = df_25.sort_values("Data", ascending=False)

        # Segundo turno
        df_25_2 = scrapping_wikipedia(URL, headers, table=1)
        df_25_2 = corrige_datas(df_25_2, "Polling period")
        df_25_2 = df_25_2.rename(columns=de_para)
        df_25_2 = df_25_2[["Instituto", "Data", "Lula", "Tarcísio"]]
        df_25_2 = df_25_2.replace("—", np.nan)
        df_25_2 = df_25_2.sort_values("Data", ascending=False)

        # Processar dados
        candidatos_1t = [
            "Lula",
            "Tarcísio",
            "Ciro Gomes",
            "Ratinho Jr.",
            "Zema",
            "Caiado",
            "Outros",
            "Branco / Nulo / Indeciso",
        ]
        candidatos_2t = ["Lula", "Tarcísio"]

        df_25, df_media = processar_dados(df_25, candidatos_1t)
        df_25_2, df_media_2t = processar_dados(df_25_2, candidatos_2t)

        return df_25, df_media, df_25_2, df_media_2t

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def filtrar_dados_por_data(df, data_inicio, data_fim):
    """Filtra dataframe por período de datas"""
    return df[
        (df["Data"] >= pd.to_datetime(data_inicio))
        & (df["Data"] <= pd.to_datetime(data_fim))
    ].copy()


def filtrar_dados_por_instituto(df, instituto_selecionado):
    """Filtra dataframe por instituto"""
    if instituto_selecionado != "Todos":
        return df[df["Instituto"] == instituto_selecionado]
    return df


def criar_metricas(df_media, candidatos, titulo):
    """Cria métricas da última pesquisa"""
    st.subheader(titulo)

    if not df_media.empty and not df_media["Data"].isna().all():
        ultima_pesquisa = df_media.loc[df_media["Data"] == df_media["Data"].max()]

        cols = st.columns(len(candidatos))

        for i, candidato in enumerate(candidatos):
            with cols[i]:
                if candidato in ultima_pesquisa.columns:
                    valor = ultima_pesquisa[candidato].iloc[0]
                    if not pd.isna(valor):
                        st.metric(label=candidato, value=f"{valor:.1f}%")


def criar_grafico_evolucao(df_filtrado, candidatos, titulo_instituto):
    """Cria gráfico de evolução por instituto"""
    fig = go.Figure()

    for candidato in candidatos:
        if candidato in df_filtrado.columns:
            data_candidato = df_filtrado[df_filtrado[candidato].notna()]
            fig.add_trace(
                go.Scatter(
                    x=data_candidato["Data"],
                    y=data_candidato[candidato],
                    mode="lines+markers",
                    name=candidato,
                    line=dict(
                        color=PARTY_COLORS.get(candidato, "#000000"),
                        width=1.5 if len(candidatos) > 2 else 2,
                    ),
                    marker=dict(size=8 if len(candidatos) > 2 else 10),
                )
            )

    if not df_filtrado.empty:
        fig.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="")

    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Intenção de Voto (%)",
        template="plotly_white",
        hovermode="x unified",
    )

    return fig


def criar_grafico_media_movel(
    df_original, df_media_filtrado, candidatos, selected_date_range
):
    """Cria gráfico de média móvel"""
    fig = go.Figure()

    # Pontos individuais (transparentes)
    for candidato in candidatos:
        if candidato in df_original.columns:
            data_candidato = df_original[df_original[candidato].notna()]
            data_candidato = filtrar_dados_por_data(
                data_candidato, selected_date_range[0], selected_date_range[1]
            )

            fig.add_trace(
                go.Scatter(
                    x=data_candidato["Data"],
                    y=data_candidato[candidato],
                    mode="markers",
                    name=f"{candidato} (dados)",
                    marker=dict(
                        color=PARTY_COLORS.get(candidato, "#000000"),
                        opacity=0.3 if len(candidatos) > 2 else 0.4,
                        size=5 if len(candidatos) > 2 else 8,
                    ),
                    showlegend=False,
                )
            )

    # Linhas de média móvel
    for candidato in candidatos:
        if candidato in df_media_filtrado.columns:
            data_candidato = df_media_filtrado[df_media_filtrado[candidato].notna()]
            fig.add_trace(
                go.Scatter(
                    x=data_candidato["Data"],
                    y=data_candidato[candidato],
                    mode="lines",
                    name=candidato,
                    line=dict(
                        color=PARTY_COLORS.get(candidato, "#000000"),
                        width=2 if len(candidatos) > 2 else 3,
                    ),
                    line_shape="spline",
                )
            )

    fig.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="")

    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Intenção de Voto (%)",
        template="plotly_white",
        hovermode="x unified",
    )

    return fig


def criar_grafico_comparacao_direta(df_media_filtrado):
    """Cria gráfico de barras para comparação direta (segundo turno)"""
    if df_media_filtrado.empty:
        return None

    ultima_data = df_media_filtrado.loc[
        df_media_filtrado["Data"] == df_media_filtrado["Data"].max()
    ]

    if ultima_data.empty:
        return None

    lula_val = (
        ultima_data["Lula"].iloc[0] if not pd.isna(ultima_data["Lula"].iloc[0]) else 0
    )
    tarcisio_val = (
        ultima_data["Tarcísio"].iloc[0]
        if not pd.isna(ultima_data["Tarcísio"].iloc[0])
        else 0
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["Lula", "Tarcísio"],
            y=[lula_val, tarcisio_val],
            marker=dict(color=[PARTY_COLORS["Lula"], PARTY_COLORS["Tarcísio"]]),
            text=[f"{lula_val:.1f}%", f"{tarcisio_val:.1f}%"],
            textposition="auto",
            width=[0.4, 0.4],  # Barras mais finas
        )
    )

    fig.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="")

    fig.update_layout(
        title="Cenário Atual - Segundo Turno",
        yaxis_title="Intenção de Voto (%)",
        template="plotly_white",
        showlegend=False,
    )

    return fig


def criar_ranking_institutos(df_original):
    """Cria gráfico de ranking dos institutos"""
    instituto_counts = df_original["Instituto"].value_counts()
    fig = go.Figure(
        go.Bar(
            x=instituto_counts.values,
            y=instituto_counts.index,
            orientation="h",
            marker=dict(color="#009739"),
        )
    )

    fig.update_layout(
        title="Número de Pesquisas por Instituto",
        xaxis_title="Quantidade de Pesquisas",
        yaxis_title="Instituto",
        template="plotly_white",
    )

    return fig


def criar_tabela_dados(df_filtrado, candidatos):
    """Cria tabela formatada com os dados"""
    colunas_mostrar = ["Instituto", "Data"] + candidatos
    df_display = df_filtrado[colunas_mostrar].copy()
    df_display = df_display.sort_values("Data", ascending=False)
    df_display["Data"] = df_display["Data"].dt.strftime("%d/%m/%Y")
    return df_display


def criar_filtros_sidebar(df, titulo, key_suffix):
    """Cria filtros na sidebar"""
    st.sidebar.header(titulo)

    # Data range
    if not df["Data"].isna().all():
        min_date = df["Data"].min().date()
        max_date = df["Data"].max().date()

        selected_date_range = st.sidebar.slider(
            "📅 Período de Análise",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date),
            key=f"date_{key_suffix}",
        )
    else:
        selected_date_range = (datetime.date.today(), datetime.date.today())

    # Instituto
    institutos = df["Instituto"].dropna().unique()
    selected_instituto = st.sidebar.selectbox(
        "🏢 Instituto de Pesquisa",
        options=["Todos"] + list(institutos),
        key=f"instituto_{key_suffix}",
    )

    return selected_date_range, selected_instituto


# Carregar dados
df_original, df_media, df_segundo_turno, df_media_2t = carregar_dados()

if df_original.empty:
    st.error("Não foi possível carregar os dados. Verifique sua conexão.")
    st.stop()

# HEADER PRINCIPAL
st.markdown(
    "<h1 style='text-align: center;'>🇧🇷 ELEIÇÕES PRESIDENCIAIS BRASIL 2026</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='text-align: center;'>Acompanhamento das Pesquisas de Intenção de Voto</div>",
    unsafe_allow_html=True,
)

# MENU LATERAL - Escolha de cenário
pagina = st.sidebar.radio(
    "📌 Escolha o cenário", ["1️⃣ PRIMEIRO TURNO", "2️⃣ SEGUNDO TURNO"]
)

# -----------------------------
# PRIMEIRO TURNO
# -----------------------------
if pagina == "1️⃣ PRIMEIRO TURNO":
    # Configurações primeiro turno
    candidatos_principais = ["Lula", "Tarcísio", "Zema", "Branco / Nulo / Indeciso"]
    todos_candidatos = candidatos_principais + [
        "Ciro Gomes",
        "Ratinho Jr.",
        "Caiado",
        "Outros",
    ]

    # ---- Filtros Primeiro Turno ----
    st.sidebar.header("🔎 Filtros - Primeiro Turno")
    selected_date_range, selected_instituto = criar_filtros_sidebar(
        df_original, "", "1t"
    )

    # Candidatos
    selected_candidates = st.pills(
        "👥 Candidatos",
        options=todos_candidatos,
        default=candidatos_principais,
        selection_mode="multi",
        key="candidatos_1t",
    )

    # Métricas
    criar_metricas(
        df_original, candidatos_principais[:4], "📊 Cenário Atual - Última Pesquisa"
    )

    # Filtrar dados
    df_filtered = filtrar_dados_por_data(
        df_original, selected_date_range[0], selected_date_range[1]
    )
    df_media_filtered = filtrar_dados_por_data(
        df_media, selected_date_range[0], selected_date_range[1]
    )
    df_filtered = filtrar_dados_por_instituto(df_filtered, selected_instituto)

    # Gráficos
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"📈 Evolução - {selected_instituto}")
        fig1 = criar_grafico_evolucao(
            df_filtered, selected_candidates, selected_instituto
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("📊 Média Móvel - Todos os Institutos")
        fig2 = criar_grafico_media_movel(
            df_original, df_media_filtered, selected_candidates, selected_date_range
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Ranking institutos
    st.subheader("🏆 Atividade dos Institutos de Pesquisa")
    fig4 = criar_ranking_institutos(df_original)
    st.plotly_chart(fig4, use_container_width=True)

    # Tabela
    st.subheader("📋 Dados das Pesquisas")
    df_display = criar_tabela_dados(df_filtered, selected_candidates)
    st.dataframe(df_display, use_container_width=True)

# -----------------------------
# SEGUNDO TURNO
# -----------------------------
elif pagina == "2️⃣ SEGUNDO TURNO":
    if not df_segundo_turno.empty:
        # Configurações segundo turno
        candidatos_2t = ["Lula", "Tarcísio"]

        # ---- Filtros Segundo Turno ----
        st.sidebar.header("🔎  Filtros - Segundo Turno")
        selected_date_range_2t, selected_instituto_2t = criar_filtros_sidebar(
            df_segundo_turno, "", "2t"
        )

        # Métricas
        criar_metricas(
            df_segundo_turno,
            candidatos_2t,
            "Cenário Segundo Turno - Última Pesquisa",
        )

        # Filtrar dados
        df_filtered_2t = filtrar_dados_por_data(
            df_segundo_turno, selected_date_range_2t[0], selected_date_range_2t[1]
        )
        df_media_filtered_2t = filtrar_dados_por_data(
            df_media_2t, selected_date_range_2t[0], selected_date_range_2t[1]
        )
        df_filtered_2t = filtrar_dados_por_instituto(
            df_filtered_2t, selected_instituto_2t
        )

        # Gráficos evolução e média móvel
        col1_2t, col2_2t = st.columns(2)

        with col1_2t:
            st.subheader(f"📈 Evolução 2º Turno - {selected_instituto_2t}")
            fig1_2t = criar_grafico_evolucao(
                df_filtered_2t, candidatos_2t, selected_instituto_2t
            )
            st.plotly_chart(fig1_2t, use_container_width=True)

        with col2_2t:
            st.subheader("📊 Média Móvel 2º Turno")
            fig2_2t = criar_grafico_media_movel(
                df_segundo_turno,
                df_media_filtered_2t,
                candidatos_2t,
                selected_date_range_2t,
            )
            st.plotly_chart(fig2_2t, use_container_width=True)

        # ---- Comparação direta + Ranking institutos ----
        st.subheader("⚔️ Comparação Direta e Atividade dos Institutos - Segundo Turno")
        col3_2t, col4_2t = st.columns(2)

        with col3_2t:
            fig_comp = criar_grafico_comparacao_direta(df_media_filtered_2t)
            if fig_comp:
                st.plotly_chart(fig_comp, use_container_width=True)

        with col4_2t:
            fig_rank_2t = criar_ranking_institutos(df_segundo_turno)
            st.plotly_chart(fig_rank_2t, use_container_width=True)

        # Tabela
        st.subheader("📋 Dados das Pesquisas - Segundo Turno")
        df_display_2t = criar_tabela_dados(df_filtered_2t, candidatos_2t)
        st.dataframe(df_display_2t, use_container_width=True)

    else:
        st.warning("⚠️ Dados do segundo turno não disponíveis")

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
