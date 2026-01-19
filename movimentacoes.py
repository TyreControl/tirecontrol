import streamlit as st
from database import run_query
import datetime

def render_movimentacoes():
    st.title("🔧 Oficina e Movimentações")
    st.info("Central de Operações: Realize trocas, montagens e baixas aqui.")

    # 1. Identificar Cliente
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user: return
    cliente_id = dados_user[0]['cliente_id']

    # 2. Selecionar Caminhão Alvo
    caminhoes = run_query("SELECT id, placa FROM caminhoes WHERE cliente_id = %s ORDER BY placa", (cliente_id,))
    opcoes_caminhoes = {c['placa']: c['id'] for c in caminhoes}
    
    col_sel, col_info = st.columns([1, 2])
    with col_sel:
        placa = st.selectbox("Selecione o Caminhão", list(opcoes_caminhoes.keys()))
        caminhao_id = opcoes_caminhoes[placa]

    # Abas de Operação (Conforme PDF Pág 6 - Manobras)
    tab1, tab2, tab3 = st.tabs(["⬇️ Montagem (Estoque -> Caminhão)", "⬆️ Desmontagem (Caminhão -> Fora)", "🔄 Rodízio (Troca Posição)"])

    # --- ABA 1: MONTAGEM ---
    with tab1:
        st.subheader("Montar Pneu do Estoque")
        # Buscar pneus em estoque
        pneus_estoque = run_query("SELECT id, marca_fogo, marca, medida FROM pneus WHERE cliente_id = %s AND status = 'ESTOQUE'", (cliente_id,))
        
        if not pneus_estoque:
            st.warning("Sem pneus no estoque. Cadastre novos pneus primeiro.")
        else:
            with st.form("form_montagem"):
                pneu_choice = st.selectbox("Escolha o Pneu", [f"{p['marca_fogo']} - {p['marca']}" for p in pneus_estoque])
                posicao = st.selectbox("Posição no Caminhão", ["FL", "FR", "TL_OUT", "TL_IN", "TR_IN", "TR_OUT"])
                km_atual = st.number_input("KM Atual do Caminhão", min_value=0)
                
                if st.form_submit_button("Confirmar Montagem"):
                    # Extrair ID do pneu selecionado
                    marca_fogo_sel = pneu_choice.split(" - ")[0]
                    pneu_id = next(p for p in pneus_estoque if p['marca_fogo'] == marca_fogo_sel)['id']
                    
                    # 1. Atualizar Pneu
                    run_query("""
                        UPDATE pneus SET status = 'MONTADO', caminhao_atual_id = %s, posicao_atual = %s 
                        WHERE id = %s
                    """, (caminhao_id, posicao, pneu_id))
                    
                    # 2. Registrar Histórico (Movimentação)
                    run_query("""
                        INSERT INTO movimentacoes (pneu_id, tipo_movimento, destino_caminhao_id, destino_posicao, km_momento, usuario_responsavel)
                        VALUES (%s, 'MONTAGEM', %s, %s, %s, %s)
                    """, (pneu_id, caminhao_id, posicao, km_atual, user_id))
                    
                    # 3. Atualizar KM Caminhão
                    run_query("UPDATE caminhoes SET km_atual = %s WHERE id = %s", (km_atual, caminhao_id))
                    
                    st.success("Pneu montado com sucesso!")
                    st.rerun()

    # --- ABA 2: DESMONTAGEM ---
    with tab2:
        st.subheader("Retirar Pneu do Caminhão")
        # Buscar pneus no caminhão
        pneus_no_caminhao = run_query("""
            SELECT id, marca_fogo, posicao_atual FROM pneus 
            WHERE caminhao_atual_id = %s AND status = 'MONTADO'
        """, (caminhao_id,))
        
        if not pneus_no_caminhao:
            st.warning("Este caminhão não tem pneus montados.")
        else:
            with st.form("form_baixa"):
                pneu_baixa = st.selectbox("Qual pneu retirar?", [f"{p['posicao_atual']} - {p['marca_fogo']}" for p in pneus_no_caminhao])
                destino = st.selectbox("Destino", ["ESTOQUE", "RECAPAGEM", "SUCATA"])
                motivo = st.text_input("Motivo (Ex: Desgaste natural, Furo)")
                km_baixa = st.number_input("KM Atual (Baixa)", min_value=0)
                
                if st.form_submit_button("Confirmar Retirada"):
                    marca_fogo_alvo = pneu_baixa.split(" - ")[1]
                    pneu_obj = next(p for p in pneus_no_caminhao if p['marca_fogo'] == marca_fogo_alvo)
                    
                    # Atualiza Pneu
                    run_query("""
                        UPDATE pneus SET status = %s, caminhao_atual_id = NULL, posicao_atual = NULL 
                        WHERE id = %s
                    """, (destino, pneu_obj['id']))
                    
                    # Histórico
                    run_query("""
                        INSERT INTO movimentacoes (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, km_momento, usuario_responsavel)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (pneu_obj['id'], 'DESMONTAGEM', caminhao_id, pneu_obj['posicao_atual'], km_baixa, user_id))
                    
                    st.success(f"Pneu enviado para {destino}!")
                    st.rerun()

    # --- ABA 3: RODÍZIO ---
    with tab3:
        st.write("Funcionalidade de troca rápida entre posições (Em desenvolvimento - use Desmontar + Montar por enquanto)")