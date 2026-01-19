import streamlit as st
import pandas as pd
from database import run_query

def render_pneus():
    st.header("🔘 Gestão de Estoque e Ativos")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user: return
    cliente_id = dados_user[0]['cliente_id']

    # --- CADASTRO COMPLETO ---
    with st.expander("➕ Cadastrar Novo Pneu (Entrada de Nota)", expanded=False):
        with st.form("form_pneu_completo"):
            st.write("Dados do Ativo")
            c1, c2, c3 = st.columns(3)
            marca_fogo = c1.text_input("Marca de Fogo (DOT)").upper()
            marca = c2.selectbox("Marca", ["Michelin", "Bridgestone", "Goodyear", "Pirelli", "Continental", "Outra"])
            modelo = c3.text_input("Modelo (Ex: X Multi Z)")
            
            c4, c5, c6 = st.columns(3)
            medida = c4.selectbox("Medida", ["295/80R22.5", "275/80R22.5", "11.00R22"])
            vida = c5.selectbox("Ciclo de Vida", ["Novo (0)", "1ª Recap (1)", "2ª Recap (2)"])
            custo = c6.number_input("Custo de Aquisição (R$)", min_value=0.0)
            
            if st.form_submit_button("Registrar Entrada"):
                ciclo_map = {"Novo (0)": 0, "1ª Recap (1)": 1, "2ª Recap (2)": 2}
                try:
                    run_query("""
                        INSERT INTO pneus (cliente_id, marca_fogo, marca, modelo, medida, status, ciclo_atual, km_vida_total)
                        VALUES (%s, %s, %s, %s, %s, 'ESTOQUE', %s, 0)
                    """, (cliente_id, marca_fogo, marca, modelo, medida, ciclo_map[vida]))
                    st.success("Pneu registrado no estoque!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    # --- RELATÓRIO DE ESTOQUE E SUCATA ---
    st.divider()
    st.subheader("Inventário Atual")
    
    filtro_status = st.multiselect("Filtrar Status", ["ESTOQUE", "MONTADO", "RECAPAGEM", "SUCATA"], default=["ESTOQUE", "RECAPAGEM"])
    
    if filtro_status:
        # Tive que fazer uma gambiarra com tuple(filtro_status) para o SQL aceitar IN
        placeholders = ', '.join(['%s'] * len(filtro_status))
        query = f"""
            SELECT marca_fogo, marca, modelo, status, posicao_atual, ciclo_atual 
            FROM pneus 
            WHERE cliente_id = %s AND status IN ({placeholders})
        """
        # Junta os parametros: cliente_id + lista de status
        params = [cliente_id] + filtro_status
        
        pneus = run_query(query, tuple(params))
        
        if pneus:
            st.dataframe(pd.DataFrame(pneus), use_container_width=True)
        else:
            st.info("Nenhum pneu encontrado com esses filtros.")