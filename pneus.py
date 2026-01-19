import streamlit as st
import pandas as pd
from database import run_query

def render_pneus():
    st.header("🏭 Gestão de Ativos (Pneus)")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user: return
    cliente_id = dados_user[0]['cliente_id']

    tab1, tab2 = st.tabs(["📦 Estoque & Cadastro", "♻️ Controle de Recapagem"])

    with tab1:
        # Formulário de Cadastro Novo
        with st.expander("➕ Cadastrar Pneu Novo", expanded=True):
            with st.form("novo_pneu"):
                c1, c2, c3 = st.columns(3)
                mf = c1.text_input("Marca de Fogo (DOT)").upper()
                marca = c2.selectbox("Marca", ["Michelin", "Bridgestone", "Goodyear", "Pirelli", "Outra"])
                medida = c3.selectbox("Medida", ["295/80R22.5", "275/80R22.5", "Outra"])
                
                if st.form_submit_button("Cadastrar"):
                    try:
                        run_query("INSERT INTO pneus (cliente_id, marca_fogo, marca, medida, status, ciclo_atual, km_vida_total) VALUES (%s, %s, %s, %s, 'ESTOQUE', 0, 0)", (cliente_id, mf, marca, medida))
                        st.success("Cadastrado!")
                        st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")

        # Tabela de Estoque
        st.subheader("Disponível em Estoque")
        estoque = run_query("SELECT marca_fogo, marca, medida, ciclo_atual FROM pneus WHERE cliente_id = %s AND status = 'ESTOQUE'", (cliente_id,))
        if estoque:
            st.dataframe(pd.DataFrame(estoque), use_container_width=True)

    with tab2:
        st.subheader("♻️ Retorno de Recapagem")
        st.info("Pneus que foram enviados para recapagem e estão voltando para o estoque.")
        
        # Busca pneus que estão na Recapadora
        em_recap = run_query("SELECT id, marca_fogo, marca, ciclo_atual FROM pneus WHERE cliente_id = %s AND status = 'RECAPAGEM'", (cliente_id,))
        
        if em_recap:
            with st.form("retorno_recap"):
                pneu_sel = st.selectbox("Selecione o Pneu Retornando", [f"{p['marca_fogo']} (Ciclo {p['ciclo_atual']})" for p in em_recap])
                custo = st.number_input("Custo do Serviço (R$)", min_value=0.0)
                nova_banda = st.text_input("Modelo da Nova Banda (Ex: K44)")
                
                if st.form_submit_button("Confirmar Retorno ao Estoque"):
                    pneu_obj = next(p for p in em_recap if p['marca_fogo'] in pneu_sel)
                    novo_ciclo = pneu_obj['ciclo_atual'] + 1
                    
                    # Atualiza pneu: Volta pro estoque, Incrementa ciclo (Pág 3 - 90)
                    run_query("UPDATE pneus SET status='ESTOQUE', ciclo_atual=%s, modelo=%s WHERE id=%s", (novo_ciclo, nova_banda, pneu_obj['id']))
                    
                    # Registra histórico
                    run_query("INSERT INTO movimentacoes (pneu_id, tipo_movimento, usuario_responsavel) VALUES (%s, 'RETORNO_RECAP', %s)", (pneu_obj['id'], user_id))
                    
                    st.success(f"Pneu {pneu_obj['marca_fogo']} atualizado para Ciclo {novo_ciclo}!")
                    st.rerun()
        else:
            st.info("Nenhum pneu na recapadora no momento.")