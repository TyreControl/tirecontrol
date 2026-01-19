import streamlit as st
from database import run_query

def render_movimentacoes():
    st.title("🔧 Central de Oficina")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user: return
    cliente_id = dados_user[0]['cliente_id']

    # SELEÇÃO DO CONTEXTO
    caminhoes = run_query("SELECT id, placa, km_atual FROM caminhoes WHERE cliente_id = %s ORDER BY placa", (cliente_id,))
    opcoes_cam = {c['placa']: c for c in caminhoes}
    
    col_cam, col_km = st.columns([2, 1])
    with col_cam:
        placa = st.selectbox("Veículo em Manutenção", list(opcoes_cam.keys()))
        cam = opcoes_cam[placa]
    with col_km:
        novo_km = st.number_input("Hodômetro Atual", value=cam['km_atual'])
        if novo_km != cam['km_atual']:
            if st.button("Atualizar KM"):
                run_query("UPDATE caminhoes SET km_atual = %s WHERE id = %s", (novo_km, cam['id']))
                st.success("KM Atualizado!")
                st.rerun()

    st.divider()

    # --- ABA DE OPERAÇÕES ---
    tab_montar, tab_baixar, tab_rodizio = st.tabs(["⬇️ Montar (Estoque -> Pneu)", "⬆️ Desmontar (Pneu -> Fora)", "🔄 Rodízio (Pneu <-> Pneu)"])

    # 1. MONTAGEM
    with tab_montar:
        st.subheader("Instalar Pneu do Estoque")
        pneus_estoque = run_query("SELECT id, marca_fogo, marca, medida FROM pneus WHERE cliente_id = %s AND status = 'ESTOQUE'", (cliente_id,))
        
        if not pneus_estoque:
            st.warning("Estoque Vazio. Realize a entrada de nota primeiro.")
        else:
            with st.form("form_montar"):
                col_p, col_pos = st.columns(2)
                pneu_escolhido = col_p.selectbox("Pneu Disponível", [f"{p['marca_fogo']} ({p['medida']})" for p in pneus_estoque])
                posicao_alvo = col_pos.selectbox("Posição Alvo", ["FL", "FR", "TL_OUT", "TL_IN", "TR_IN", "TR_OUT", "RL_OUT", "RL_IN", "RR_IN", "RR_OUT"])
                
                if st.form_submit_button("Executar Montagem"):
                    # Verifica se posição está ocupada
                    ocupado = run_query("SELECT id FROM pneus WHERE caminhao_atual_id = %s AND posicao_atual = %s", (cam['id'], posicao_alvo))
                    if ocupado:
                        st.error(f"Posição {posicao_alvo} já tem pneu! Desmonte-o primeiro.")
                    else:
                        pneu_id = next(p['id'] for p in pneus_estoque if p['marca_fogo'] in pneu_escolhido)
                        # Movimentação Atômica
                        run_query("UPDATE pneus SET status='MONTADO', caminhao_atual_id=%s, posicao_atual=%s WHERE id=%s", (cam['id'], posicao_alvo, pneu_id))
                        run_query("""
                            INSERT INTO movimentacoes (pneu_id, tipo_movimento, destino_caminhao_id, destino_posicao, km_momento, usuario_responsavel)
                            VALUES (%s, 'MONTAGEM', %s, %s, %s, %s)
                        """, (pneu_id, cam['id'], posicao_alvo, novo_km, user_id))
                        st.success(f"Pneu montado em {posicao_alvo}!")
                        st.rerun()

    # 2. DESMONTAGEM (BAIXA)
    with tab_baixar:
        st.subheader("Retirar Pneu do Veículo")
        pneus_montados = run_query("SELECT id, marca_fogo, posicao_atual FROM pneus WHERE caminhao_atual_id = %s", (cam['id'],))
        
        if not pneus_montados:
            st.info("Caminhão sem pneus montados.")
        else:
            with st.form("form_baixar"):
                col_b1, col_b2 = st.columns(2)
                pneu_alvo = col_b1.selectbox("Pneu a Retirar", [f"{p['posicao_atual']} - {p['marca_fogo']}" for p in pneus_montados])
                destino = col_b2.selectbox("Destino Físico", ["ESTOQUE (Guardar)", "RECAPAGEM (Enviar)", "SUCATA (Descarte)"])
                motivo = st.text_input("Motivo Técnico (Ex: Desgaste natural, Corte lateral)")
                
                if st.form_submit_button("Confirmar Retirada"):
                    pneu_obj = next(p for p in pneus_montados if p['marca_fogo'] in pneu_alvo)
                    status_destino = destino.split(" ")[0] # Pega só a primeira palavra
                    
                    # Atualiza Pneu
                    run_query("UPDATE pneus SET status=%s, caminhao_atual_id=NULL, posicao_atual=NULL WHERE id=%s", (status_destino, pneu_obj['id']))
                    
                    # Registra Histórico
                    run_query("""
                        INSERT INTO movimentacoes (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, km_momento, usuario_responsavel)
                        VALUES (%s, 'DESMONTAGEM', %s, %s, %s, %s)
                    """, (pneu_obj['id'], cam['id'], pneu_obj['posicao_atual'], novo_km, user_id))
                    
                    st.success(f"Pneu enviado para {status_destino}.")
                    st.rerun()

    # 3. RODÍZIO
    with tab_rodizio:
        st.subheader("Rodízio de Posições")
        st.caption("Troca direta entre duas posições do mesmo veículo.")
        if len(pneus_montados) < 2:
            st.warning("Necessário pelo menos 2 pneus montados.")
        else:
            c1, c2 = st.columns(2)
            pos_a = c1.selectbox("Posição A", [p['posicao_atual'] for p in pneus_montados])
            pos_b = c2.selectbox("Posição B", [p['posicao_atual'] for p in pneus_montados])
            
            if st.button("Executar Troca"):
                if pos_a == pos_b:
                    st.error("Selecione posições diferentes.")
                else:
                    id_a = next(p['id'] for p in pneus_montados if p['posicao_atual'] == pos_a)
                    id_b = next(p['id'] for p in pneus_montados if p['posicao_atual'] == pos_b)
                    
                    # Swap com posição temporária para evitar erro de UNIQUE constraint se houver
                    run_query("UPDATE pneus SET posicao_atual='TEMP' WHERE id=%s", (id_a,))
                    run_query("UPDATE pneus SET posicao_atual=%s WHERE id=%s", (pos_a, id_b))
                    run_query("UPDATE pneus SET posicao_atual=%s WHERE id=%s", (pos_b, id_a))
                    
                    run_query("""
                        INSERT INTO movimentacoes (pneu_id, tipo_movimento, origem_posicao, destino_posicao, km_momento, usuario_responsavel)
                        VALUES (%s, 'RODIZIO', %s, %s, %s, %s)
                    """, (id_a, pos_a, pos_b, novo_km, user_id))
                    
                    st.success(f"Rodízio realizado: {pos_a} ↔ {pos_b}")
                    st.rerun()