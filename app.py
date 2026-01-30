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
# PARTE 5: O DASHBOARD VISUAL (COM LÓGICA DE ACUMULADO)
# ==============================================================================

st.markdown("---")

# 0. CONFIGURAÇÃO DE VISUALIZAÇÃO (O SELETOR DE MODO)
# ------------------------------------------------------------------------------
col_msg, col_toggle = st.columns([3, 1])
with col_msg:
    st.subheader("📊 Visão Estratégica")
with col_toggle:
    # O Pulo do Gato: Este botão define se olhamos o passado ou não
    usar_acumulado = st.toggle("Incluir Saldo Anterior?", value=True)

# 1. CÁLCULO DO SALDO ANTERIOR (A LÓGICA DO TEMPO)
# ------------------------------------------------------------------------------
saldo_anterior = 0.0

if usar_acumulado and 'mes_selecionado' in locals() and mes_selecionado:
    # Descobre o primeiro dia do mês selecionado
    ano_sel, mes_sel = map(int, mes_selecionado.split('-'))
    data_inicio_mes = pd.Timestamp(year=ano_sel, month=mes_sel, day=1)
    
    # Prepara os dados para cálculo (Cria coluna de valor com sinal correto)
    # Receita é positivo, Despesa é negativo
    df['Valor_Sinal'] = df.apply(lambda x: x['Valor'] if x['Tipo_Movimento'] == 'Receita' else -x['Valor'], axis=1)
    
    # Filtra o Passado:
    # 1. Data deve ser anterior ao mês atual
    # 2. Deve respeitar os filtros de Banco/Categoria que você escolheu na lateral
    df_passado = df[
        (df['Data_Transacao'] < data_inicio_mes) &
        (df['Instituicao'].isin(bancos_selecionados)) &
        (df['Categoria_Macro'].isin(categorias_selecionadas)) &
        (df['Status'].isin(status_selecionados))
    ]
    
    saldo_anterior = df_passado['Valor_Sinal'].sum()

# 2. CÁLCULOS DO MÊS ATUAL (KPIs)
# ------------------------------------------------------------------------------
# Receitas do Mês
total_receita_mes = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Receita']['Valor'].sum()

# Despesas do Mês
total_despesa_mes = df_filtrado[df_filtrado['Tipo_Movimento'] == 'Despesa']['Valor'].sum()

# Resultado Operacional (Só deste mês)
resultado_mes = total_receita_mes - total_despesa_mes

# Saldo Final (Depende do botão Toggle)
if usar_acumulado:
    saldo_final = saldo_anterior + resultado_mes
    texto_saldo = "Saldo Acumulado (Total)"
else:
    saldo_final = resultado_mes
    texto_saldo = "Resultado do Mês (Isolado)"

# Previsão Futura (Contas a pagar neste mês)
despesa_futura = df_filtrado[
    (df_filtrado['Tipo_Movimento'] == 'Despesa') & 
    (df_filtrado['Status'] == 'Projetado')
]['Valor'].sum()

# 3. EXIBIÇÃO DOS CARDS
# ------------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

if usar_acumulado:
    c1.metric("🏦 Saldo Anterior", f"R$ {saldo_anterior:,.2f}", help="Dinheiro que sobrou dos meses passados")
else:
    c1.metric("💰 Entradas (Mês)", f"R$ {total_receita_mes:,.2f}")

c2.metric("💸 Saídas (Mês)", f"R$ {total_despesa_mes:,.2f}", delta=-total_despesa_mes, delta_color="inverse")
c3.metric("📉 A Pagar (Previsão)", f"R$ {despesa_futura:,.2f}", help="Valor 'Projetado' que ainda vai sair")
c4.metric(f"equilíbrio {texto_saldo}", f"R$ {saldo_final:,.2f}", delta=saldo_final)

st.markdown("---")

# 4. GRÁFICOS INTELIGENTES
# ------------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📈 Evolução do Saldo", "📊 Fluxo Diário", "📂 Detalhes"])

with tab1:
    st.subheader(f"Evolução: {texto_saldo}")
    
    # Prepara dados para o gráfico de linha
    df_grafico = df_filtrado.sort_values("Data_Transacao").copy()
    
    # Cria coluna de valor com sinal (+/-)
    df_grafico['Valor_Real'] = df_grafico.apply(lambda x: x['Valor'] if x['Tipo_Movimento'] == 'Receita' else -x['Valor'], axis=1)
    
    # Calcula o acumulado dia a dia
    if usar_acumulado:
        # Começa a soma a partir do saldo anterior
        df_grafico['Saldo_Acumulado'] = df_grafico['Valor_Real'].cumsum() + saldo_anterior
    else:
        # Começa do zero
        df_grafico['Saldo_Acumulado'] = df_grafico['Valor_Real'].cumsum()
    
    fig_line = px.line(
        df_grafico, 
        x="Data_Transacao", 
        y="Saldo_Acumulado", 
        title="Tendência Financeira",
        markers=True
    )
    # Linha de alerta no Zero
    fig_line.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Zero")
    st.plotly_chart(fig_line, use_container_width=True)

with tab2:
    st.subheader("Entradas vs. Saídas (Diário)")
    fig_bar = px.bar(
        df_filtrado, 
        x="Data_Transacao", 
        y="Valor", 
        color="Tipo_Movimento", 
        title="Fluxo de Caixa",
        color_discrete_map={"Receita": "#00CC96", "Despesa": "#EF553B"},
        barmode='group'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with tab3:
    # Tabela simples e limpa
    cols_view = [c for c in ['Data_Transacao', 'Descricao', 'Valor', 'Tipo_Movimento', 'Status', 'Instituicao'] if c in df_filtrado.columns]
    st.dataframe(
        df_filtrado[cols_view].sort_values(by="Data_Transacao", ascending=False),
        use_container_width=True,
        hide_index=True
    )




# ==============================================================================
# PARTE 6: GESTOR DE BAIXAS (MODIFICAR A PLANILHA REAL)
# ==============================================================================

st.markdown("---")
st.subheader("📝 Gestor de Pagamentos Pendentes")

# 1. Filtra apenas o que é DESPESA e está PROJETADO
# Criamos uma cópia para não bagunçar a análise principal
df_pendente = df[
    (df['Tipo_Movimento'] == 'Despesa') & 
    (df['Status'] == 'Projetado')
].copy()

if not df_pendente.empty:
    st.info("Abaixo estão suas contas futuras. Mude o status para 'Realizado' e clique em Salvar.")
    
    # 2. Mostra a tabela editável
    # O usuário pode editar diretamente na tela
    df_edicao = st.data_editor(
        df_pendente,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["Projetado", "Realizado"], # Opções disponíveis
                required=True
            ),
            "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
            "Data_Transacao": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
        },
        disabled=["Instituicao", "Descricao", "Categoria_Macro"], # Bloqueia edição destas colunas para segurança
        hide_index=True,
        use_container_width=True,
        key="editor_baixas"
    )

    # 3. Botão para ENVIAR PARA O GOOGLE SHEETS
    if st.button("💾 Salvar Alterações na Planilha"):
        
        # A. Atualiza o DataFrame Principal com as mudanças feitas na tabela
        # Percorre as linhas editadas e atualiza o original
        # (Usamos o índice original para garantir que estamos mexendo na linha certa)
        df.update(df_edicao)
        
        # B. Tenta escrever no Google Sheets
        try:
            with st.spinner("Enviando dados para o Google Sheets..."):
                conn.update(data=df) # SOBRESCREVE a aba com os dados novos
                st.success("✅ Planilha atualizada com sucesso!")
                st.cache_data.clear() # Limpa a memória para recarregar os dados novos
                st.rerun() # Recarrega a página automaticamente
                
        except Exception as e:
            st.error("Erro ao salvar na planilha.")
            st.warning("Verifique se sua planilha está compartilhada como 'Editor' ou se os Secrets têm permissão de escrita.")
            st.code(str(e))

else:
    st.success("🎉 Nenhuma conta pendente (Projetada) encontrada para os filtros atuais!")
