import streamlit as st
import pandas as pd
from database import run_query

def get_status_visual(km_vida, ciclo):
    """
    Define a cor e o ícone do pneu baseado na regra de negócio (Pág 10 - Alertas).
    Lógica: Pneus recapados têm vida útil menor estimada que novos.
    """
    limite_alerta = 60000 if ciclo > 0 else 80000
    limite_critico = 70000 if ciclo > 0 else 100000
    
    if km_vida >= limite_critico:
        return "🔴", "Troca Urgente"
    elif km_vida >= limite_alerta:
        return "🟡", "Atenção"
    else:
        return "🟢", "OK"

def render_frota():
    st.title("🚛 Monitoramento da Frota")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user: return
    cliente_id = dados_user[0]['cliente_id']

    # --- MENU SUPERIOR: LISTA OU DETALHE ---
    modo = st.radio("Modo de Visualização", ["Lista Geral", "Diagrama Visual do Caminhão"], horizontal=True)

    if modo == "Lista Geral":
        # Visão Tabela (Pág 8 - Dashboard Cliente)
        df = run_query("""
            SELECT placa, modelo, config_eixos, km_atual 
            FROM caminhoes WHERE cliente_id = %s ORDER BY placa
        """, (cliente_id,))
        
        if df:
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum caminhão cadastrado.")
            
    else:
        # --- DIAGRAMA VISUAL (Pág 7) ---
        caminhoes = run_query("SELECT id, placa, modelo, config_eixos, km_atual FROM caminhoes WHERE cliente_id = %s ORDER BY placa", (cliente_id,))
        if not caminhoes:
            st.warning("Cadastre veículos primeiro.")
            return
            
        opcoes = {c['placa']: c for c in caminhoes}
        placa_sel = st.selectbox("Selecione o Veículo", list(opcoes.keys()))
        cam = opcoes[placa_sel]

        st.divider()
        col_header, col_kpi = st.columns([2, 1])
        with col_header:
            st.subheader(f"{cam['placa']} - {cam['modelo']}")
            st.caption(f"Configuração: {cam['config_eixos']}")
        with col_kpi:
            st.metric("KM Atual (Hodômetro)", f"{cam['km_atual']:,} km")

        # Busca Pneus
        pneus = run_query("""
            SELECT id, marca_fogo, marca, medida, posicao_atual, km_vida_total, ciclo_atual, status 
            FROM pneus WHERE caminhao_atual_id = %s
        """, (cam['id'],))
        
        mapa = {p['posicao_atual']: p for p in pneus} if pneus else {}

        # Função para renderizar o card do pneu (Conforme "Painel Lateral" Pág 7)
        def render_pneu_card(pos, label):
            pneu = mapa.get(pos)
            with st.container(border=True):
                st.markdown(f"**{label}**")
                if pneu:
                    icone, status_texto = get_status_visual(pneu['km_vida_total'], pneu['ciclo_atual'])
                    st.markdown(f"🏷️ **{pneu['marca_fogo']}**")
                    st.text(f"{pneu['marca']} \n{pneu['medida']}")
                    st.markdown(f"{icone} {status_texto}")
                    st.caption(f"Rodou: {pneu['km_vida_total']} km")
                    
                    if st.button("🔍 Detalhes", key=f"btn_{pos}"):
                        st.session_state['pneu_detalhe_id'] = pneu['id']
                        st.info(f"ID Interno: {pneu['id']}") 
                        # Numa versão V2, isso abriria um modal, mas o Streamlit nativo não tem modal fácil.
                else:
                    st.markdown("🚫 *Vazio*")

        # Layout do Caminhão (Eixos)
        st.write("---")
        st.markdown("#### ⬆️ Eixo Dianteiro")
        c1, c2 = st.columns(2)
        with c1: render_pneu_card('FL', 'Frente Esquerda')
        with c2: render_pneu_card('FR', 'Frente Direita')

        st.markdown("#### ⬇️ Eixo Traseiro / Tração")
        c3, c4, c5, c6 = st.columns(4)
        with c3: render_pneu_card('TL_OUT', 'Tração Esq. Fora')
        with c4: render_pneu_card('TL_IN', 'Tração Esq. Dentro')
        with c5: render_pneu_card('TR_IN', 'Tração Dir. Dentro')
        with c6: render_pneu_card('TR_OUT', 'Tração Dir. Fora')

    # Mantive o cadastro escondido num expander para limpar a tela
    with st.expander("⚙️ Gerenciar Cadastro de Veículos"):
        with st.form("add_truck"):
            c1, c2 = st.columns(2)
            placa = c1.text_input("Placa").upper()
            modelo = c2.text_input("Modelo")
            if st.form_submit_button("Salvar"):
                try:
                    run_query("INSERT INTO caminhoes (cliente_id, placa, modelo, km_atual) VALUES (%s, %s, %s, 0)", (cliente_id, placa, modelo))
                    st.success("Salvo!")
                    st.rerun()
                except: st.error("Erro ao salvar.")