import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# PARTE 1: A FUNDAÇÃO (SETUP E BIBLIOTECAS)
# ==============================================================================

# 1. Configuração da Página (Obrigatório ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="Painel Financeiro Master",
    page_icon="💰",
    layout="wide", # Usa a tela inteira para caber mais gráficos
    initial_sidebar_state="expanded"
)

# 2. Cabeçalho Principal
st.title("💰 Painel Financeiro & Preditivo")
st.markdown("**Status do Sistema:** 🟢 Iniciado | **Modo:** Análise Avançada")
st.markdown("---")

# 3. Seletor de Fonte de Dados (Na Barra Lateral)
st.sidebar.header("📂 Fonte de Dados")

# O usuário escolhe: Conexão Automática (Sheets) ou Upload Manual
fonte_dados = st.sidebar.radio(
    "Como deseja carregar os dados?",
    ["Conexão Google Sheets (Automático)", "Upload de Arquivo (CSV/Excel)"],
    index=0 # Padrão: Google Sheets
)

st.sidebar.info(f"Modo Selecionado: **{fonte_dados}**")
st.sidebar.markdown("---")


# ==============================================================================
# PARTE 2: O NÚCLEO DE CONEXÃO (A "CAIXA PRETA")
# ==============================================================================

# Variável para armazenar os dados brutos
df = pd.DataFrame() 

try:
    # --- CENÁRIO A: CONEXÃO AUTOMÁTICA (GOOGLE SHEETS) ---
    if fonte_dados == "Conexão Google Sheets (Automático)":
        
        # Cria a conexão com os segredos configurados
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        with st.spinner("🔄 Conectando ao Google Sheets em tempo real..."):
            # ttl=0 força a atualização imediata (sem cache antigo)
            # Não especificamos worksheet="Nome", ele pega a primeira aba automaticamente (Blindagem)
            df = conn.read(ttl=0)

    # --- CENÁRIO B: UPLOAD MANUAL (ARQUIVO LOCAL) ---
    elif fonte_dados == "Upload de Arquivo (CSV/Excel)":
        
        st.subheader("📤 Importar Dados")
        arquivo_upload = st.file_uploader("Arraste seu arquivo aqui", type=["csv", "xlsx"])
        
        if arquivo_upload is not None:
            try:
                # Detecta se é CSV ou Excel e lê
                if arquivo_upload.name.endswith('.csv'):
                    df = pd.read_csv(arquivo_upload)
                else:
                    df = pd.read_excel(arquivo_upload)
                
                st.success("Arquivo carregado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")
                st.stop()
        else:
            st.info("Aguardando upload do arquivo para iniciar a análise...")
            st.stop() # Para o código aqui até o usuário subir o arquivo

    # --- VERIFICAÇÃO DE SEGURANÇA (DADOS VAZIOS) ---
    if df.empty:
        st.warning("⚠️ A conexão foi feita, mas a planilha parece estar vazia.")
        st.info("Verifique se há dados na primeira aba da sua planilha.")
        st.stop()

except Exception as e:
    st.error("🚨 Erro Crítico na Conexão!")
    st.markdown("### Diagnóstico do Erro:")
    st.code(str(e))
    st.warning("Se o erro for '403', verifique se a planilha está pública ou se os Secrets estão corretos.")
    st.stop()



# ==============================================================================
# PARTE 3: REFINARIA DE DADOS (LIMPEZA AUTOMÁTICA)
# ==============================================================================

with st.spinner("🛠️ Refinando e padronizando dados..."):
    
    # 1. Padronização de Colunas (Remove espaços extras nos nomes)
    df.columns = df.columns.str.strip()

    # 2. Tratamento de DATAS (Blindado)
    if 'Data_Transacao' in df.columns:
        # Converte para data. Se houver erro, transforma em NaT (Not a Time) sem quebrar
        df['Data_Transacao'] = pd.to_datetime(df['Data_Transacao'], errors='coerce')
        # Remove linhas onde a data é inválida (essencial para gráficos de tempo)
        df = df.dropna(subset=['Data_Transacao'])
    else:
        st.error("🚨 Coluna Obrigatória Ausente: 'Data_Transacao'")
        st.info("Sua planilha precisa ter uma coluna com datas de vencimento/pagamento.")
        st.stop()

    # 3. Tratamento de VALORES (Numérico)
    if 'Valor' in df.columns:
        # Garante que é número float (decimal)
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0.0)
    else:
        st.error("🚨 Coluna Obrigatória Ausente: 'Valor'")
        st.stop()

    # 4. Tratamento de STATUS (Para Previsibilidade) - INTELIGÊNCIA EXTRA
    # Se a coluna Status não existir, assumimos que tudo já foi 'Realizado'
    if 'Status' not in df.columns:
        df['Status'] = 'Realizado'
    else:
        # Preenche vazios com 'Realizado' e padroniza texto
        df['Status'] = df['Status'].fillna('Realizado').astype(str)

    # 5. Tratamento de Texto (Categorias e Bancos)
    cols_texto = ['Instituicao', 'Tipo_Movimento', 'Categoria_Macro', 'Descricao']
    for col in cols_texto:
        if col not in df.columns:
            df[col] = "Não Informado" # Cria coluna falsa para não quebrar filtros
        else:
            df[col] = df[col].astype(str).fillna("-")

    # 6. Ordenação Cronológica (Para gráficos bonitos)
    df = df.sort_values(by='Data_Transacao', ascending=False)

    # Feedback visual discreto
    st.toast(f"{len(df)} registros processados com sucesso!", icon="✅")



# ==============================================================================
# PARTE 4: O MOTOR DE FILTROS (INTERATIVIDADE)
# ==============================================================================

st.sidebar.header("🔍 Filtros Inteligentes")

# 1. Preparação para Filtro de Tempo (Cria coluna Ano-Mês)
df['Mes_Referencia'] = df['Data_Transacao'].dt.strftime('%Y-%m')
meses_disponiveis = sorted(df['Mes_Referencia'].unique())

# --- FILTRO 1: PERÍODO (TIME SLICE) ---
if meses_disponiveis:
    # Padrão: Seleciona o último mês disponível (o mais recente)
    mes_atual_index = len(meses_disponiveis) - 1
    mes_selecionado = st.sidebar.selectbox(
        "📅 Mês de Referência:",
        options=meses_disponiveis,
        index=mes_atual_index
    )
else:
    mes_selecionado = None

# --- FILTRO 2: INSTITUIÇÃO FINANCEIRA (BANCOS) ---
bancos_unicos = sorted(df["Instituicao"].unique())
bancos_selecionados = st.sidebar.multiselect(
    "🏦 Contas / Bancos:",
    options=bancos_unicos,
    default=bancos_unicos # Padrão: Seleciona todos
)

# --- FILTRO 3: CATEGORIAS ---
categorias_unicas = sorted(df["Categoria_Macro"].unique())
categorias_selecionadas = st.sidebar.multiselect(
    "🏷️ Categorias de Gasto:",
    options=categorias_unicas,
    default=categorias_unicas
)

# --- FILTRO 4: PREVISIBILIDADE (STATUS) ---
# Aqui você controla se quer ver o FUTURO ou só o PASSADO
status_unicos = sorted(df["Status"].unique())
status_selecionados = st.sidebar.multiselect(
    "🔮 Status (Realizado vs Projetado):",
    options=status_unicos,
    default=status_unicos
)

# --- APLICAÇÃO DOS FILTROS (O MOTOR DE CORTE) ---
# Se não tiver mês selecionado (planilha vazia), não filtra nada
if mes_selecionado:
    df_filtrado = df[
        (df['Mes_Referencia'] == mes_selecionado) &
        (df['Instituicao'].isin(bancos_selecionados)) &
        (df['Categoria_Macro'].isin(categorias_selecionadas)) &
        (df['Status'].isin(status_selecionados))
    ]
else:
    df_filtrado = df

# --- VALIDAÇÃO FINAL DO CORTE ---
if df_filtrado.empty:
    st.warning("⚠️ Nenhum dado encontrado para essa combinação de filtros.")
    st.info("Tente adicionar mais bancos ou categorias na barra lateral.")
    st.stop() # Para o código aqui para não gerar gráficos vazios



# ==============================================================================
# PARTE 5: O DASHBOARD VISUAL (GRÁFICOS, KPIs E PREVISIBILIDADE)
# ==============================================================================

st.markdown("---")

# 1. CÁLCULO DE KPIs (INDICADORES CHAVE)
# ------------------------------------------------------------------------------
# Receitas (Dinheiro que entrou)
total_receita = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Receita']['Valor'].sum()

# Despesas Totais (Tudo que é saída)
total_despesa = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Despesa']['Valor'].sum()

# PREVISIBILIDADE: Quanto disso é PROJETADO (Futuro)?
# Isso responde à sua pergunta: "Quanto ainda tenho que pagar este mês?"
despesa_futura = df_filtrado[
    (df_filtrado['Tipo_Movimento'] == 'Despesa') & 
    (df_filtrado['Status'] == 'Projetado')
]['Valor'].sum()

saldo_liquido = total_receita - total_despesa

# 2. EXIBIÇÃO DOS CARDS (TOPO DO PAINEL)
# ------------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 Entradas Totais", f"R$ {total_receita:,.2f}")
col2.metric("💸 Saídas Totais", f"R$ {total_despesa:,.2f}", delta=-total_despesa, delta_color="inverse")
col3.metric("📉 A Pagar (Previsão)", f"R$ {despesa_futura:,.2f}", help="Valor agendado/projetado que ainda sairá da conta")
col4.metric("equilíbrio Saldo Líquido", f"R$ {saldo_liquido:,.2f}", delta=saldo_liquido)

st.markdown("---")

# 3. ÁREA GRÁFICA (VISÃO ESTRATÉGICA)
# ------------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Fluxo Diário", "📈 Previsibilidade de Saldo", "📂 Detalhe por Banco"])

with tab1:
    st.subheader("Entradas vs. Saídas (Dia a Dia)")
    # Gráfico de barras agrupado por dia
    fig_bar = px.bar(
        df_filtrado, 
        x="Data_Transacao", 
        y="Valor", 
        color="Tipo_Movimento", 
        title="Fluxo de Caixa Diário",
        color_discrete_map={"Receita": "#00CC96", "Despesa": "#EF553B"}, # Verde e Vermelho
        barmode='group',
        text_auto='.2s'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    st.subheader("Simulação de Saldo Acumulado")
    # Cria uma simulação de como o saldo se comporta ao longo do mês
    df_saldo = df_filtrado.sort_values("Data_Transacao").copy()
    # Transforma despesa em negativo para somar corretamente
    df_saldo['Valor_Real'] = df_saldo.apply(lambda x: x['Valor'] if x['Tipo_Movimento'] == 'Receita' else -x['Valor'], axis=1)
    df_saldo['Saldo_Acumulado'] = df_saldo['Valor_Real'].cumsum()
    
    fig_line = px.line(
        df_saldo, 
        x="Data_Transacao", 
        y="Saldo_Acumulado", 
        title="Tendência do Saldo (Runway)",
        markers=True
    )
    # Adiciona linha de alerta no Zero
    fig_line.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Limite Zero")
    st.plotly_chart(fig_line, use_container_width=True)

with tab3:
    st.subheader("Análise por Instituição")
    # Gráfico de Rosca para ver onde está o dinheiro saindo
    fig_pie = px.sunburst(
        df_filtrado[df_filtrado['Tipo_Movimento'] == 'Despesa'], 
        path=['Instituicao', 'Categoria_Macro'], 
        values='Valor',
        title="Onde estou gastando? (Drill-down)"
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# 4. TABELA DETALHADA (EXTRATO)
# ------------------------------------------------------------------------------
with st.expander("📝 Ver Extrato Completo (Dados Brutos)", expanded=True):
    # Seleciona colunas mais relevantes para mostrar
    cols_view = [c for c in ['Data_Transacao', 'Descricao', 'Categoria_Macro', 'Valor', 'Tipo_Movimento', 'Status', 'Instituicao'] if c in df_filtrado.columns]
    
    st.dataframe(
        df_filtrado[cols_view].sort_values(by="Data_Transacao", ascending=False),
        use_container_width=True,
        hide_index=True
    )

# 5. RODAPÉ (CRÉDITOS)
st.markdown("---")
st.caption("🚀 Sistema Financeiro Inteligente | Desenvolvido via Streamlit & Python")
