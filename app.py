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

   # 3. Tratamento de VALORES (Blindado para R$ Brasileiro)
    if 'Valor' in df.columns:
        # A. Se a coluna for lida como Texto (com vírgulas e pontos)
        if df['Valor'].dtype == 'object':
            # Remove o ponto de milhar (1.000 -> 1000) e troca a vírgula por ponto (50,00 -> 50.00)
            df['Valor'] = df['Valor'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.')
        
        # B. Converte finalmente para número
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
tab1, tab2, tab3 = st.tabs(["📈 Evolução do Saldo", "📊 Fluxo Diário", "📂 Extrato Diário"])

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
    # ==========================================================================
    # NOVO VISUAL - PARTE 1: O DESIGN SYSTEM (CSS)
    # ==========================================================================
    st.markdown("""
    <style>
    /* 1. Container Geral da Linha do Tempo */
    .timeline-container {
        font-family: 'Segoe UI', sans-serif;
        max-width: 800px;
        margin: 0 auto;
    }

    /* 2. Cabeçalho do Dia (Ex: 27 • terça-feira) */
    .day-header {
        font-size: 14px;
        color: #666;
        margin-top: 25px;
        margin-bottom: 10px;
        font-weight: 500;
        padding-left: 10px;
    }

    /* 3. Linha da Transação */
    .transaction-row {
        display: flex;
        align-items: center;
        padding: 12px 10px;
        background-color: white;
        border-left: 2px solid #e0e0e0; /* A linha vertical contínua */
        margin-left: 10px; /* Espaço para alinhar com o cabeçalho */
        transition: background 0.2s;
    }
    .transaction-row:hover {
        background-color: #f9f9f9;
        border-left: 2px solid #2196F3; /* Destaque azul ao passar o mouse */
    }

    /* 4. Ícone (Bolinha Colorida) */
    .t-icon {
        width: 35px;
        height: 35px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        margin-right: 15px;
        color: white;
        font-weight: bold;
        flex-shrink: 0; /* Não deixa o ícone esmagar */
    }
    .bg-green { background-color: #4CAF50; } /* Receita */
    .bg-red   { background-color: #EF5350; } /* Despesa */
    .bg-blue  { background-color: #2196F3; } /* Transferencia/Outro */

    /* 5. Textos da Transação */
    .t-details {
        flex-grow: 1;
    }
    .t-title {
        font-size: 15px;
        font-weight: 600;
        color: #333;
        margin: 0;
    }
    .t-subtitle {
        font-size: 12px;
        color: #888;
        margin: 0;
    }

    /* 6. Valor (Direita) */
    .t-value {
        font-size: 15px;
        font-weight: 600;
        text-align: right;
    }
    .val-green { color: #4CAF50; }
    .val-red   { color: #EF5350; }

    /* 7. Resumo Diário (Rodapé do dia) */
    .daily-summary {
        margin-left: 12px; /* Alinhado com a linha vertical */
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 0 0 8px 8px;
        font-size: 13px;
        border-left: 2px solid #e0e0e0;
    }
    .summary-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        color: #555;
    }
    .summary-total {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px dashed #ccc;
        font-weight: bold;
        font-size: 14px;
        color: #333;
    }
    </style>
    """, unsafe_allow_html=True)
    # ==========================================================================
    # PARTE 2: PREPARAÇÃO DOS DADOS (AGRUPAMENTO E CÁLCULO DE SALDO)
    # ==========================================================================
    
    if not df_filtrado.empty:
        # 1. Cria uma cópia para cálculo matemático (Ordenação Cronológica: Antigo -> Novo)
        df_calc = df_filtrado.copy()
        df_calc['Data_Transacao'] = pd.to_datetime(df_calc['Data_Transacao'])
        df_calc = df_calc.sort_values(by=["Data_Transacao"], ascending=True)

        # 2. Cria coluna de Valor Real (+ para Receita, - para Despesa)
        df_calc['Valor_Real'] = df_calc.apply(lambda x: x['Valor'] if x['Tipo_Movimento'] == 'Receita' else -x['Valor'], axis=1)

        # 3. Calcula o Saldo Acumulado (Runway)
        # Verifica se deve incluir o histórico passado (variavel criada na Parte 5)
        base_inicial = saldo_anterior if 'saldo_anterior' in locals() and usar_acumulado else 0.0
        
        # A mágica: vai somando linha a linha
        df_calc['Saldo_Acumulado_Ate_Aqui'] = df_calc['Valor_Real'].cumsum() + base_inicial

        # 4. Inverte para visualização (Visual: Novo -> Antigo)
        # Agora temos o saldo calculado corretamente em cada linha
        df_timeline = df_calc.sort_values(by=["Data_Transacao"], ascending=False)
        
        # 5. Extrai dias únicos para o loop
        dias_unicos = df_timeline['Data_Transacao'].dt.date.unique()

        # 6. Mapa de Dias da Semana
        dias_semana_map = {
            0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
            3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"
        }

        # 7. Abre o Container Principal
        st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
        # ==========================================================================
        # PARTE 3: O LOOP CONSTRUTOR (TIMELINE COM SALDO TOTAL)
        # ==========================================================================
        
        for dia_atual in dias_unicos:
            
            # A. Filtra dados deste dia
            df_dia = df_timeline[df_timeline['Data_Transacao'].dt.date == dia_atual]
            
            # B. Cálculos do Rodapé (Resumo do Dia)
            soma_receita = df_dia[df_dia['Tipo_Movimento'] == 'Receita']['Valor'].sum()
            soma_despesa = df_dia[df_dia['Tipo_Movimento'] == 'Despesa']['Valor'].sum()
            saldo_dia_final = soma_receita - soma_despesa
            
            # CÁLCULO DO SALDO TOTAL (ACUMULADO) DO DIA
            # Como ordenamos do mais recente para o mais antigo, 
            # o saldo da PRIMEIRA linha deste dia representa o saldo no FECHAMENTO deste dia.
            saldo_total_acumulado = df_dia.iloc[0]['Saldo_Acumulado_Ate_Aqui']
            
            # C. Renderiza o CABEÇALHO DO DIA
            dia_semana_texto = dias_semana_map[dia_atual.weekday()]
            st.markdown(f"""
                <div class="day-header">
                    {dia_atual.day} • {dia_semana_texto}
                </div>
            """, unsafe_allow_html=True)
            
            # D. Loop das Transações
            for _, row in df_dia.iterrows():
                
                tipo = row['Tipo_Movimento']
                valor = row['Valor']
                descricao = row['Descricao']
                banco = row['Instituicao']
                categoria = row['Categoria_Macro']
                
                if tipo == 'Receita':
                    cor_bg = "bg-green"
                    cor_val = "val-green"
                    sinal = "+"
                    icone_letra = "💰" 
                else:
                    cor_bg = "bg-red"
                    cor_val = "val-red"
                    sinal = "-"
                    icone_letra = categoria[0].upper() if categoria else "💸"

                st.markdown(f"""
                <div class="transaction-row">
                    <div class="t-icon {cor_bg}">{icone_letra}</div>
                    <div class="t-details">
                        <p class="t-title">{descricao}</p>
                        <p class="t-subtitle">{categoria} • {banco}</p>
                    </div>
                    <div class="t-value {cor_val}">
                        {sinal}R$ {valor:,.2f}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # E. Renderiza o RODAPÉ DO DIA (Agora com 4 linhas)
            st.markdown(f"""
            <div class="daily-summary">
                <div class="summary-row">
                    <span>🔵 Total Crédito</span>
                    <span class="val-green">+R$ {soma_receita:,.2f}</span>
                </div>
                <div class="summary-row">
                    <span>🔴 Total Débito</span>
                    <span class="val-red">-R$ {soma_despesa:,.2f}</span>
                </div>
                <div class="summary-total" style="border-top: 1px dashed #ccc; padding-top:5px; margin-top:5px;">
                    <span style="font-weight:normal;">Saldo do dia (Isolado)</span>
                    <span>R$ {saldo_dia_final:,.2f}</span>
                </div>
                <div class="summary-total" style="color:#2196F3; font-size:15px; border-top:none; margin-top:2px;">
                    <span>🏦 Saldo Total (Acumulado)</span>
                    <span>R$ {saldo_total_acumulado:,.2f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # 5. Fecha o Container Principal
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.info("Nenhum dado encontrado para exibir no extrato detalhado.")








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
