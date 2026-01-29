import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.title("🕵️ Tela de Diagnóstico")

# Tenta conectar
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    st.write("✅ Conexão iniciada...")
    
    # Tenta ler
    st.write("Tentando ler a planilha...")
    df = conn.read(worksheet="Página1") # Certifique-se que a aba chama Página1
    
    st.success("SUCESSO! Dados carregados:")
    st.dataframe(df.head())

except Exception as e:
    st.error("❌ ERRO ENCONTRADO!")
    st.markdown(f"**O computador disse:** `{e}`")
    
    st.warning("Verifique abaixo o que pode ser:")
    st.write("1. Se o erro for '403', sua planilha não está pública.")
    st.write("2. Se o erro for 'WorksheetNotFound', o nome da aba não é Página1.")
    st.write("3. Se o erro for 'No st.connection...', seus Secrets estão errados.")
