import streamlit as st
import pandas as pd
from database import run_query

def render_pneus():
    st.header("🔘 Estoque de Pneus")
    
    # --- FORMULÁRIO DE CADASTRO DE PNEU ---
    with st.expander("➕ Cadastrar Novo Pneu", expanded=False):
        with st.form("form_pneu"):
            col1, col2 = st.columns(2)
            marca_fogo = col1.text_input("Marca de Fogo / DOT (ID Único)")
            marca = col2.selectbox("Marca", ["Michelin", "Bridgestone", "Goodyear", "Pirelli", "Continental", "Outra"])
            
            col3, col4, col5 = st.columns(3)
            modelo = col3.text_input("Modelo (Ex: X Multi Z)")
            medida = col4.selectbox("Medida", ["295/80R22.5", "275/80R22.5", "11.00R22", "Outra"])
            vida = col5.selectbox("Ciclo de Vida", ["Novo", "1ª Recapagem", "2ª Recapagem"])
            
            if st.form_submit_button("Adicionar ao Estoque"):
                user_id = st.session_state['user_id']
                dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
                
                if dados_user and marca_fogo:
                    cliente_id = dados_user[0]['cliente_id']
                    ciclo_map = {"Novo": 0, "1ª Recapagem": 1, "2ª Recapagem": 2}
                    
                    try:
                        run_query(
                            """
                            INSERT INTO pneus (cliente_id, marca_fogo, marca, modelo, medida, status, ciclo_atual)
                            VALUES (%s, %s, %s, %s, %s, 'ESTOQUE', %s)
                            """,
                            (cliente_id, marca_fogo, marca, modelo, medida, ciclo_map[vida])
                        )
                        st.success("Pneu cadastrado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    # --- KPI RÁPIDO ---
    st.divider()
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    
    if dados_user:
        cliente_id = dados_user[0]['cliente_id']
        
        # Pneus em Estoque
        pneus_estoque = run_query("SELECT marca_fogo, marca, modelo, medida, status FROM pneus WHERE cliente_id = %s AND status = 'ESTOQUE'", (cliente_id,))
        
        st.metric("Pneus Disponíveis em Estoque", len(pneus_estoque) if pneus_estoque else 0)
        
        if pneus_estoque:
            st.dataframe(pd.DataFrame(pneus_estoque), use_container_width=True, hide_index=True)
        else:
            st.info("Estoque vazio.")