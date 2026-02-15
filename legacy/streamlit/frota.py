import streamlit as st
import pandas as pd
from database import run_query

def get_status_visual(km_vida, ciclo):
    """Regra de Negócio Pág 10: Cores baseadas na vida útil e ciclo"""
    limite = 70000 if ciclo > 0 else 100000 # Recapado dura menos
    percentual = min(km_vida / limite, 1.0)
    
    if percentual > 0.9: return "🔴", "Crítico", "#ffcccc"
    elif percentual > 0.7: return "🟡", "Atenção", "#fff4cc"
    return "🟢", "OK", "#ccffcc"

def render_frota():
    st.title("🚛 Gestão Visual da Frota")
    
    cliente_id = st.session_state.get("cliente_id")
    if not cliente_id:
        st.error("Cliente nao definido na sessao.")
        return

    # --- MENU DE SELEÇÃO ---
    caminhoes = run_query("SELECT id, placa, modelo, config_eixos, km_atual FROM caminhoes WHERE cliente_id = %s ORDER BY placa", (cliente_id,))
    if not caminhoes:
        st.warning("Cadastre um veículo para começar.")
        return

    opcoes = {c['placa']: c for c in caminhoes}
    
    col_sel, col_detalhes = st.columns([1, 3])
    with col_sel:
        placa_sel = st.selectbox("Selecione o Veículo", list(opcoes.keys()))
        cam = opcoes[placa_sel]
        st.info(f"📍 {cam['modelo']} ({cam['config_eixos']})")
        st.metric("Hodômetro", f"{cam['km_atual']:,} km")

    # --- VISUALIZAÇÃO DO CHASSI ---
    with col_detalhes:
        st.subheader(f"Mapa de Pneus: {placa_sel}")
        
        # Busca pneus montados neste caminhão exato
        pneus = run_query("""
            SELECT id, marca_fogo, marca, medida, posicao_atual, km_vida_total, ciclo_atual, status 
            FROM pneus WHERE caminhao_atual_id = %s AND cliente_id = %s
        """, (cam['id'], cliente_id))
        
        mapa = {p['posicao_atual']: p for p in pneus} if pneus else {}

        # Função Helper para desenhar o CARD DO PNEU
        def render_posicao(pos_code, label):
            pneu = mapa.get(pos_code)
            container = st.container(border=True)
            
            if pneu:
                icone, status_txt, cor_bg = get_status_visual(pneu['km_vida_total'], pneu['ciclo_atual'])
                container.markdown(f"<div style='background-color:{cor_bg}; padding: 2px; border-radius: 4px;'><b>{pos_code}</b></div>", unsafe_allow_html=True)
                container.caption(label)
                container.markdown(f"🔥 **{pneu['marca_fogo']}**")
                container.text(f"{pneu['marca']} | {pneu['ciclo_atual']}ª Vida")
                container.progress(min(pneu['km_vida_total']/100000, 1.0)) # Barra de vida
            else:
                container.markdown(f"**{pos_code}**")
                container.caption(label)
                container.warning("Vazio")
                if container.button("➕ Mapear", key=f"map_{pos_code}"):
                    st.session_state['mapear_dados'] = {'cam_id': cam['id'], 'pos': pos_code, 'cam_placa': cam['placa']}
                    st.rerun()

        # LAYOUT DE EIXOS (Renderização fiel à posição física)
        # Eixo 1 (Direcional)
        st.markdown("### ⬆️ Eixo Direcional")
        c1, c_vazio, c2 = st.columns([1, 0.2, 1])
        with c1: render_posicao('FL', 'Frente Esquerda')
        with c2: render_posicao('FR', 'Frente Direita')

        # Eixo 2 (Tração)
        st.markdown("### ⬇️ Eixo Tração")
        c3, c4, c_vazio, c5, c6 = st.columns([1, 1, 0.2, 1, 1])
        with c3: render_posicao('TL_OUT', 'Esq. Fora')
        with c4: render_posicao('TL_IN', 'Esq. Dentro')
        with c5: render_posicao('TR_IN', 'Dir. Dentro')
        with c6: render_posicao('TR_OUT', 'Dir. Fora')

        # Eixo 3 (Truck - se houver)
        if cam['config_eixos'] in ['6x2', '6x4']:
            st.markdown("### ⬇️ Eixo Truck (3º Eixo)")
            c7, c8, c_vazio, c9, c10 = st.columns([1, 1, 0.2, 1, 1])
            with c7: render_posicao('RL_OUT', 'Esq. Fora')
            with c8: render_posicao('RL_IN', 'Esq. Dentro')
            with c9: render_posicao('RR_IN', 'Dir. Dentro')
            with c10: render_posicao('RR_OUT', 'Dir. Fora')

    # --- MODAL DE MAPEAMENTO (Inventário Inicial) ---
    if 'mapear_dados' in st.session_state:
        dados = st.session_state['mapear_dados']
        st.write("---")
        with st.form("form_mapear_rapido"):
            st.markdown(f"#### 📍 Mapeando {dados['pos']} no {dados['cam_placa']}")
            st.info("Use para cadastrar pneus que JÁ estão fisicamente no caminhão.")
            
            col_a, col_b = st.columns(2)
            mf = col_a.text_input("Marca de Fogo (DOT)").upper()
            marca = col_b.selectbox("Marca", ["Michelin", "Bridgestone", "Goodyear", "Pirelli", "Outra"])
            
            col_c, col_d = st.columns(2)
            vida = col_c.selectbox("Ciclo Atual", ["Novo (0)", "Recap 1", "Recap 2"])
            km_est = col_d.number_input("KM Estimado Já Rodado", min_value=0)
            
            if st.form_submit_button("Confirmar Posição"):
                ciclo_map = {"Novo (0)": 0, "Recap 1": 1, "Recap 2": 2}
                try:
                    run_query("""
                        INSERT INTO pneus (cliente_id, marca_fogo, marca, status, caminhao_atual_id, posicao_atual, ciclo_atual, km_vida_total)
                        VALUES (%s, %s, %s, 'MONTADO', %s, %s, %s, %s)
                    """, (cliente_id, mf, marca, dados['cam_id'], dados['pos'], ciclo_map[vida], km_est))
                    st.success("Mapeado!")
                    del st.session_state['mapear_dados']
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e} (Verifique se o Fogo já existe)")
