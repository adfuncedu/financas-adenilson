import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# 1. Configuração da Página
st.set_page_config(page_title="Finanças Adenilson", layout="wide")
st.title("📊 Painel Financeiro - Adenilson")

# 2. Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # AQUI ESTAVA O ERRO: Agora buscamos a aba "Dados" (sem acento)
    df = conn.read(worksheet="Dados", ttl=60)
    
    # Garantir que a data seja lida como data
    if 'Data_Transacao' in df.columns:
        df['Data_Transacao'] = pd.to_datetime(df['Data_Transacao'])
    
except Exception as e:
    st.error("Erro na leitura. Verifique se a aba da planilha se chama 'Dados'.")
    st.stop()

# 3. Barra Lateral (Filtros)
st.sidebar.header("Filtros")

# Verifica se existem dados antes de filtrar
if not df.empty:
    # Filtro de Banco
    bancos_disponiveis = df["Instituicao"].unique() if "Instituicao" in df.columns else []
    banco_selecionado = st.sidebar.multiselect("Bancos:", options=bancos_disponiveis, default=bancos_disponiveis)

    # Filtro de Data
    df['Mes_Str'] = df['Data_Transacao'].dt.strftime('%Y-%m')
    meses_disponiveis = sorted(df['Mes_Str'].unique())
    if meses_disponiveis:
        mes_selecionado = st.sidebar.selectbox("Mês de Referência:", options=meses_disponiveis, index=len(meses_disponiveis)-1)
        
        # Aplicando Filtros
        df_filtrado = df[
            (df["Instituicao"].isin(banco_selecionado)) & 
            (df["Mes_Str"] == mes_selecionado)
        ]
    else:
        df_filtrado = df # Fallback se não tiver datas
else:
    st.warning("A planilha parece estar vazia.")
    st.stop()

# 4. KPIs
if not df_filtrado.empty:
    total_receita = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Receita']['Valor'].sum()
    total_despesa = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Despesa']['Valor'].sum()
    
    # Previsibilidade (Projetado)
    despesa_futura = df_filtrado[(df_filtrado['Tipo_Movimento'] == 'Despesa') & (df_filtrado['Status'] == 'Projetado')]['Valor'].sum()
    
    saldo = total_receita - total_despesa

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Receitas", f"R$ {total_receita:,.2f}")
    col2.metric("Despesas Totais", f"R$ {total_despesa:,.2f}", delta=-total_despesa, delta_color="inverse")
    col3.metric("Saldo Líquido", f"R$ {saldo:,.2f}")
    col4.metric("A Vencer (Projetado)", f"R$ {despesa_futura:,.2f}", help="Valor que ainda vai sair da conta este mês")

    # 5. Gráfico
    st.markdown("---")
    st.subheader("Fluxo de Caixa Diário")
    fig = px.bar(df_filtrado, x="Data_Transacao", y="Valor", color="Tipo_Movimento", 
                 title="Entradas e Saídas", color_discrete_map={"Receita": "#00CC96", "Despesa": "#EF553B"})
    st.plotly_chart(fig, use_container_width=True)

    # 6. Tabela Detalhada
    with st.expander("Ver Extrato Detalhado"):
        st.dataframe(df_filtrado.sort_values(by="Data_Transacao", ascending=False))
