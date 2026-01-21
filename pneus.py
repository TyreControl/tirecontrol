"""
FLUXO 1 & 2 - pneus.py
Implementa: Cadastro de Lote + Atribuição de Pneus
"""

import streamlit as st
import pandas as pd
from datetime import date
from database import (
    criar_lote_pneus, adicionar_pneus_ao_lote, obter_lotes_cliente,
    obter_pneus_lote, atribuir_pneu_posicao, remover_pneu_posicao,
    obter_pneus_estoque_disponiveis, obter_pneus_caminhao_por_posicao,
    run_query
)

def render_pneus():
    """Nova versão com FLUXOS 1 e 2 implementados"""
    
    st.title("🏭 Gestão de Ativos e Estoque")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    
    if not dados_user:
        st.error("Usuário não encontrado")
        return
    
    cliente_id = dados_user[0]['cliente_id']
    
    # ==================== TABS ====================
    tab_novo_lote, tab_atribuir, tab_estoque, tab_recap = st.tabs([
        "📦 Novo Lote de Pneus", 
        "🔧 Atribuir Pneus a Caminhão",
        "📊 Inventário Geral",
        "♻️ Fluxo de Recapagem"
    ])
    
    # ==================== TAB 1: NOVO LOTE ====================
    with tab_novo_lote:
        st.subheader("➕ Cadastro de Novo Lote")
        st.markdown("""
        **Como funciona:**
        1. Gestor recebe nota fiscal com pneus do fornecedor
        2. Registra o lote (quantidade total, não números individuais ainda)
        3. Sistema gera número único do lote
        4. Depois, se quiser, adiciona números de série de cada pneu
        """)
        
        col1, col2 = st.columns(2)
        
        with st.form("novo_lote"):
            st.markdown("### 📋 Dados da Nota Fiscal")
            
            c1, c2, c3 = st.columns(3)
            n_nota = c1.text_input("Nota Fiscal", key="nf_lote")
            fornecedor = c2.text_input("Fornecedor", key="forn_lote")
            data_chegada = c3.date_input("Data Chegada", value=date.today(), key="data_lote")
            
            st.markdown("### 🛞 Especificação de Pneus")
            
            c4, c5, c6 = st.columns(3)
            marca = c4.selectbox("Marca", [
                "Michelin", "Bridgestone", "Goodyear", "Pirelli", 
                "Continental", "Firestone", "Outra"
            ], key="marca_lote")
            medida = c5.selectbox("Medida", [
                "295/80R22.5", "275/80R22.5", "11.00R22", "12R22.5",
                "185/65R15", "195/60R15", "225/70R15", "235/75R17"
            ], key="medida_lote")
            modelo = c6.text_input("Modelo (ex: X Multi Z)", key="modelo_lote")
            
            st.markdown("### 💰 Quantidade e Preço")
            
            c7, c8 = st.columns(2)
            quantidade = c7.number_input("Quantidade de Pneus", min_value=1, value=10, 
                                        step=1, key="qtd_lote")
            preco_unitario = c8.number_input("Preço Unitário (R$)", 
                                            min_value=0.0, value=850.0, step=10.0, key="preco_lote")
            
            st.markdown(f"### 💵 Total: R$ {quantidade * preco_unitario:,.2f}")
            
            # Checkbox: Adicionar números de série agora?
            adicionar_series = st.checkbox(
                "✅ Vou adicionar números de série (marcas de fogo) agora",
                key="check_series"
            )
            
            if adicionar_series:
                st.markdown(f"### 🔤 Marcas de Fogo (Digite {quantidade} números)")
                fogos_text = st.text_area(
                    f"Uma marca por linha (ex: MIC001, MIC002, ...)",
                    height=150,
                    key="fogos_lote"
                )
            else:
                fogos_text = None
            
            submitted = st.form_submit_button("✅ Cadastrar Lote", use_container_width=True)
            
            if submitted:
                # Validar dados
                if not n_nota or not fornecedor or not marca or not medida:
                    st.error("❌ Preencha todos os campos obrigatórios")
                else:
                    # PASSO 1: Criar lote
                    resultado_lote = criar_lote_pneus(
                        cliente_id=cliente_id,
                        marca=marca,
                        medida=medida,
                        modelo=modelo or "Não especificado",
                        fornecedor=fornecedor,
                        quantidade=quantidade,
                        preco_unitario=preco_unitario,
                        n_nota_fiscal=n_nota,
                        data_chegada=data_chegada
                    )
                    
                    if resultado_lote:
                        st.success(f"✅ Lote criado: {resultado_lote['numero_lote']}")
                        
                        # PASSO 2: Adicionar pneus se tiver números de série
                        if adicionar_series and fogos_text:
                            lista_fogos = [x.strip().upper() for x in fogos_text.split('\n') if x.strip()]
                            
                            if len(lista_fogos) != quantidade:
                                st.warning(f"⚠️ Você informou {quantidade} pneus, mas digitou {len(lista_fogos)} números")
                            else:
                                sucesso = adicionar_pneus_ao_lote(
                                    cliente_id=cliente_id,
                                    lote_id=resultado_lote['lote_id'],
                                    lista_marcas_fogo=lista_fogos,
                                    marca=marca,
                                    medida=medida,
                                    modelo=modelo or "Não especificado",
                                    fornecedor=fornecedor,
                                    custo=preco_unitario,
                                    data_compra=data_chegada,
                                    n_nota_fiscal=n_nota
                                )
                                
                                if sucesso:
                                    st.success(f"✅ {quantidade} pneus adicionados ao lote!")
                                    st.balloons()
                                else:
                                    st.error("❌ Erro ao adicionar pneus")
                        
                        st.info("💡 Próximo passo: Ir para 'Atribuir Pneus a Caminhão' para montar os pneus")
                    else:
                        st.error("❌ Erro ao criar lote")
        
        # Mostrar lotes recentes
        st.markdown("---")
        st.markdown("### 📜 Lotes Recentes")
        
        lotes = obter_lotes_cliente(cliente_id)
        if lotes:
            df_lotes = pd.DataFrame(lotes)
            df_lotes_display = df_lotes[[
                'numero_lote', 'marca', 'medida', 'quantidade_total', 
                'quantidade_disponivel', 'fornecedor', 'data_chegada'
            ]].rename(columns={
                'numero_lote': 'Lote',
                'marca': 'Marca',
                'medida': 'Medida',
                'quantidade_total': 'Total',
                'quantidade_disponivel': 'Disponível',
                'fornecedor': 'Fornecedor',
                'data_chegada': 'Data'
            })
            st.dataframe(df_lotes_display, use_container_width=True)
        else:
            st.info("Nenhum lote cadastrado ainda")
    
    # ==================== TAB 2: ATRIBUIR PNEUS ====================
    with tab_atribuir:
        st.subheader("🔧 Atribuir Pneus a Caminhão")
        st.markdown("""
        **Como funciona:**
        1. Selecione o caminhão
        2. Veja o mapa visual dos pneus
        3. Clique em uma posição para adicionar/trocar pneu
        4. Selecione o pneu do estoque
        5. Confirme a troca
        """)
        
        # Selecionar caminhão
        query_caminhoes = "SELECT id, placa, modelo, config_eixos FROM caminhoes WHERE cliente_id = %s ORDER BY placa"
        caminhoes = run_query(query_caminhoes, (cliente_id,))
        
        if not caminhoes:
            st.warning("Nenhum caminhão cadastrado")
            return
        
        opcoes_cam = {c['placa']: c for c in caminhoes}
        placa_sel = st.selectbox("🚛 Selecione o Veículo", list(opcoes_cam.keys()))
        cam_sel = opcoes_cam[placa_sel]
        
        col_info, col_mapa = st.columns([2, 3])
        
        with col_info:
            st.info(f"""
            **Veículo Selecionado:**
            - Placa: {cam_sel['placa']}
            - Modelo: {cam_sel['modelo']}
            - Config: {cam_sel['config_eixos']} pneus
            """)
        
        with col_mapa:
            st.markdown("### 🗺️ Mapa de Pneus (Vista de Topo)")
            
            # Obter pneus montados
            mapa_pneus = obter_pneus_caminhao_por_posicao(cam_sel['id'])
            
            # Renderizar chassi visualmente
            st.markdown("""
            ```
                        Dianteiro
                      ┌─────┬─────┐
                      │  1  │  2  │
                      └─────┴─────┘
                      ┌─────┬─────┐
                      │  3  │  4  │
                      └─────┴─────┘
                        Traseiro
            ```
            """)
            
            # Mostrar posições disponíveis
            posicoes = {
                'FL': 'Dianteiro Esquerdo',
                'FR': 'Dianteiro Direito',
                'TL1': 'Traseiro Esquerdo (externo)',
                'TL2': 'Traseiro Esquerdo (interno)',
                'TR1': 'Traseiro Direito (externo)',
                'TR2': 'Traseiro Direito (interno)',
                'RL': 'Estepe Esquerdo',
                'RR': 'Estepe Direito'
            }
            
            for pos_code, pos_label in posicoes.items():
                if pos_code in mapa_pneus:
                    pneu = mapa_pneus[pos_code]
                    st.success(f"✅ {pos_label}: {pneu['marca_fogo']} ({pneu['marca']})")
                else:
                    if st.button(f"➕ Adicionar a {pos_label}", key=f"add_{pos_code}"):
                        st.session_state[f'show_selector_{pos_code}'] = True
                
                # Seletor de pneu para essa posição
                if st.session_state.get(f'show_selector_{pos_code}'):
                    with st.expander(f"Selecionar pneu para {pos_label}", expanded=True):
                        pneus_disp = obter_pneus_estoque_disponiveis(cliente_id)
                        
                        if pneus_disp:
                            pneu_selecionado = st.selectbox(
                                "Escolha um pneu:",
                                options=pneus_disp,
                                format_func=lambda x: f"{x['marca_fogo']} - {x['marca']} ({x['tipo_pneu']}) - {x['km_restante']} km",
                                key=f"select_{pos_code}"
                            )
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.button("✅ Confirmar", key=f"confirm_{pos_code}"):
                                    if atribuir_pneu_posicao(
                                        pneu_id=pneu_selecionado['id'],
                                        veiculo_id=cam_sel['id'],
                                        posicao_nova=pos_code,
                                        usuario_id=user_id
                                    ):
                                        st.success(f"✅ Pneu atribuído com sucesso!")
                                        st.session_state[f'show_selector_{pos_code}'] = False
                                        st.rerun()
                            
                            with col_btn2:
                                if st.button("❌ Cancelar", key=f"cancel_{pos_code}"):
                                    st.session_state[f'show_selector_{pos_code}'] = False
                                    st.rerun()
                        else:
                            st.warning("Nenhum pneu disponível no estoque")
    
    # ==================== TAB 3: INVENTÁRIO ====================
    with tab_estoque:
        st.subheader("📊 Inventário Geral")
        
        filtro = st.multiselect("Filtrar Status", [
            "ESTOQUE", "MONTADO", "RECAPAGEM", "SUCATA"
        ], default=["ESTOQUE", "MONTADO"])
        
        if filtro:
            placeholders = ', '.join(['%s'] * len(filtro))
            query = f"""
            SELECT marca_fogo, marca, medida, status, ciclo_atual, 
                   posicao_atual, km_vida_total, custo_aquisicao
            FROM pneus 
            WHERE cliente_id = %s AND status IN ({placeholders})
            ORDER BY status, km_vida_total DESC
            """
            
            params = [cliente_id] + filtro
            dados = run_query(query, tuple(params))
            
            if dados:
                df = pd.DataFrame(dados)
                st.dataframe(df, use_container_width=True)
                
                # Métricas
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Total de Pneus", len(df))
                col_m2.metric("Investimento Total", f"R$ {df['custo_aquisicao'].sum():,.2f}")
                col_m3.metric("Vida Média", f"{df['km_vida_total'].mean():.0f} km")
            else:
                st.info("Nenhum pneu encontrado com esse filtro")
    
    # ==================== TAB 4: RECAPAGEM ====================
    with tab_recap:
        st.subheader("♻️ Fluxo de Recapagem")
        st.info("Funcionalidade de recapagem em desenvolvimento...")
