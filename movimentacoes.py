import streamlit as st
from database import run_query
from datetime import datetime

def render_movimentacoes():
    st.title("🛠️ Oficina Central")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user: return
    cliente_id = dados_user[0]['cliente_id']

    # Seletor global de caminhão
    caminhoes = run_query("SELECT id, placa, km_atual FROM caminhoes WHERE cliente_id = %s ORDER BY placa", (cliente_id,))
    if not caminhoes:
        st.warning("Sem caminhões.")
        return

    opcoes = {c['placa']: c for c in caminhoes}
    placa = st.selectbox("Selecione o Caminhão em Serviço", list(opcoes.keys()))
    cam = opcoes[placa]
    st.info(f"Hodômetro Atual Registrado: {cam['km_atual']} km")

    # Abas conforme Fluxo Principal (Pág 5 e 6)
    tab1, tab2, tab3 = st.tabs(["🔍 Inspeção & Medição", "🔧 Montagem", "🛑 Desmontagem/Baixa"])

    # --- ABA 1: INSPEÇÃO (Pág 6 - Item 4.5 e Pág 4 - Item 133) ---
    with tab1:
        st.subheader("Registrar Medição e Defeitos")
        pneus_montados = run_query("SELECT id, marca_fogo, posicao_atual FROM pneus WHERE caminhao_atual_id = %s", (cam['id'],))
        
        if pneus_montados:
            with st.form("form_inspecao"):
                col_pneu, col_km = st.columns(2)
                pneu_alvo = col_pneu.selectbox("Pneu", [f"{p['posicao_atual']} - {p['marca_fogo']}" for p in pneus_montados])
                novo_km = col_km.number_input("KM Atual do Caminhão", value=cam['km_atual'])
                
                c1, c2, c3 = st.columns(3)
                sulco = c1.number_input("Profundidade Sulco (mm)", min_value=0.0, step=0.1)
                pressao = c2.number_input("Pressão (PSI)", min_value=0)
                defeito = c3.selectbox("Defeito Visual?", ["Nenhum", "Desgaste Irregular", "Bolha", "Corte", "Separação"])
                
                obs = st.text_area("Observações")

                if st.form_submit_button("Salvar Inspeção"):
                    # Aqui, idealmente, salvaríamos em uma tabela 'inspecoes'.
                    # Como MVP, vamos atualizar o KM do pneu e registrar no histórico se houver defeito.
                    
                    pneu_id = next(p['id'] for p in pneus_montados if p['marca_fogo'] in pneu_alvo)
                    
                    # Atualiza KM do caminhão se mudou
                    if novo_km > cam['km_atual']:
                        run_query("UPDATE caminhoes SET km_atual = %s WHERE id = %s", (novo_km, cam['id']))
                        # TODO: Lógica para somar KM na vida do pneu (feature complexa para V2)
                    
                    st.success(f"Inspeção registrada para {pneu_alvo.split(' - ')[1]}!")
        else:
            st.info("Este caminhão está sem pneus.")

    # --- ABA 2: MONTAGEM (Pág 5 - Item 4.2) ---
    with tab2:
        st.write("Instalar pneu do estoque no caminhão")
        pneus_estoque = run_query("SELECT id, marca_fogo, marca, medida, ciclo_atual FROM pneus WHERE cliente_id = %s AND status = 'ESTOQUE'", (cliente_id,))
        
        if pneus_estoque:
            with st.form("montagem"):
                pneu_sel = st.selectbox("Pneu em Estoque", [f"{p['marca_fogo']} ({p['medida']})" for p in pneus_estoque])
                posicao = st.selectbox("Posição", ["FL", "FR", "TL_OUT", "TL_IN", "TR_IN", "TR_OUT"])
                km_inst = st.number_input("KM da Instalação", value=cam['km_atual'])
                
                if st.form_submit_button("Montar"):
                    pneu_id = next(p['id'] for p in pneus_estoque if p['marca_fogo'] in pneu_sel)
                    
                    # Transação atômica (Ideal)
                    run_query("UPDATE pneus SET status='MONTADO', caminhao_atual_id=%s, posicao_atual=%s WHERE id=%s", (cam['id'], posicao, pneu_id))
                    run_query("INSERT INTO movimentacoes (pneu_id, tipo_movimento, destino_caminhao_id, destino_posicao, km_momento, usuario_responsavel) VALUES (%s, 'MONTAGEM', %s, %s, %s, %s)", (pneu_id, cam['id'], posicao, km_inst, user_id))
                    run_query("UPDATE caminhoes SET km_atual = %s WHERE id = %s", (km_inst, cam['id']))
                    
                    st.success("Montado!")
                    st.rerun()
        else:
            st.warning("Estoque vazio.")

    # --- ABA 3: DESMONTAGEM/BAIXA (Pág 6 - Item 4.4 - Opção 4) ---
    with tab3:
        st.write("Retirar pneu para Estoque, Recapagem ou Sucata")
        if pneus_montados:
            with st.form("baixa"):
                pneu_baixa = st.selectbox("Pneu a retirar", [f"{p['posicao_atual']} - {p['marca_fogo']}" for p in pneus_montados])
                destino = st.selectbox("Enviar para", ["ESTOQUE", "RECAPAGEM", "SUCATA"])
                motivo = st.text_input("Motivo da Retirada")
                km_ret = st.number_input("KM da Retirada", value=cam['km_atual'])
                
                if st.form_submit_button("Confirmar Baixa"):
                    pneu_obj = next(p for p in pneus_montados if p['marca_fogo'] in pneu_baixa)
                    
                    # Regra de Negócio: Se for para Recapagem, incrementa ciclo? 
                    # R: Incrementa quando VOLTA da recapagem (Pág 6 - 216). Aqui só muda status.
                    
                    run_query("UPDATE pneus SET status=%s, caminhao_atual_id=NULL, posicao_atual=NULL WHERE id=%s", (destino, pneu_obj['id']))
                    
                    run_query("INSERT INTO movimentacoes (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, km_momento, usuario_responsavel) VALUES (%s, 'DESMONTAGEM', %s, %s, %s, %s)", (pneu_obj['id'], cam['id'], pneu_obj['posicao_atual'], km_ret, user_id))
                    
                    if destino == "SUCATA":
                        st.error("Pneu marcado como SUCATA.")
                    else:
                        st.success(f"Pneu enviado para {destino}.")
                    st.rerun()