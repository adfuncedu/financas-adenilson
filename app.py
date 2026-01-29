import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# 1. Configuração da Página
st.set_page_config(page_title="Finanças Adenilson", layout="wide")
st.title("📊 Painel Financeiro - Adenilson")

# 2. Conexão com Google Sheets
# O parâmetro ttl=60 faz o cache durar 60 segundos (atualiza quase em tempo real)
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Lê a aba principal. Substitua 'Página1' pelo nome da sua aba se for diferente.
    df = conn.read(worksheet="Página1", ttl=60)
    
    # Garantir que a data seja lida como data
    df['Data_Transacao'] = pd.to_datetime(df['Data_Transacao'])
    
except Exception as e:
    st.error("Erro ao conectar na planilha. Verifique os Segredos (Secrets).")
    st.stop()

# 3. Barra Lateral (Filtros)
st.sidebar.header("Filtros")

# Filtro de Banco
bancos_disponiveis = df["Instituicao"].unique()
banco_selecionado = st.sidebar.multiselect("Bancos:", options=bancos_disponiveis, default=bancos_disponiveis)

# Filtro de Data (Mês)
df['Mes_Str'] = df['Data_Transacao'].dt.strftime('%Y-%m')
meses_disponiveis = sorted(df['Mes_Str'].unique())
mes_selecionado = st.sidebar.selectbox("Mês de Referência:", options=meses_disponiveis, index=len(meses_disponiveis)-1)

# Aplicando Filtros
df_filtrado = df[
    (df["Instituicao"].isin(banco_selecionado)) & 
    (df["Mes_Str"] == mes_selecionado)
]

# 4. KPIs
total_receita = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Receita']['Valor'].sum()
total_despesa = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Despesa']['Valor'].sum()
saldo = total_receita - total_despesa

col1, col2, col3 = st.columns(3)
col1.metric("Receitas", f"R$ {total_receita:,.2f}")
col2.metric("Despesas", f"R$ {total_despesa:,.2f}", delta=-total_despesa, delta_color="inverse")
col3.metric("Saldo do Mês", f"R$ {saldo:,.2f}")

# 5. Gráfico
st.markdown("---")
fig = px.bar(df_filtrado, x="Data_Transacao", y="Valor", color="Tipo_Movimento", title="Fluxo Diário")
st.plotly_chart(fig, use_container_width=True)

# 6. Exibir Dados Brutos (Opcional)
with st.expander("Ver dados detalhados"):
    st.dataframe(df_filtrado)
