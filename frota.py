import streamlit as st
import pandas as pd
from database import run_query

def render_frota():  # <--- ESSA LINHA É A MAIS IMPORTANTE
    st.header("🚛 Gestão da Frota")

    # --- ABA DE CADASTRO ---
    with st.expander("➕ Cadastrar Novo Caminhão", expanded=False):
        with st.form("form_caminhao"):
            col1, col2, col3 = st.columns(3)
            placa = col1.text_input("Placa").upper()
            modelo = col2.text_input("Modelo (Ex: Scania R450)")
            eixos = col3.selectbox("Configuração de Eixos", ["4x2", "6x2", "6x4"])
            
            if st.form_submit_button("Salvar Veículo"):
                if len(placa) < 7:
                    st.warning("Placa inválida.")
                else:
                    user_id = st.session_state['user_id']
                    # Busca cliente do usuário
                    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
                    
                    if dados_user:
                        cliente_id = dados_user[0]['cliente_id']
                        
                        # Tenta salvar
                        try:
                            # Garante que a coluna config_eixos existe
                            run_query(
                                """
                                INSERT INTO caminhoes (cliente_id, placa, modelo, config_eixos, km_atual)
                                VALUES (%s, %s, %s, %s, 0)
                                """,
                                (cliente_id, placa, modelo, eixos)
                            )
                            st.success(f"Caminhão {placa} cadastrado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")

    # --- TABELA DE VISUALIZAÇÃO ---
    st.divider()
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    
    if dados_user:
        cliente_id = dados_user[0]['cliente_id']
        df = run_query("SELECT placa, modelo, config_eixos, km_atual, ativo FROM caminhoes WHERE cliente_id = %s ORDER BY placa", (cliente_id,))
        
        if df:
            st.dataframe(
                pd.DataFrame(df),
                column_config={
                    "placa": "Placa",
                    "modelo": "Modelo",
                    "km_atual": st.column_config.NumberColumn("KM", format="%d km"),
                    "ativo": "Status"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhum caminhão cadastrado.")