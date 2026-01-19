import streamlit as st
import pandas as pd
from database import run_query

def get_cor_status(km_vida):
    """Define a cor do pneu baseado no uso (Regra de Negócio Pág 15)"""
    # Lógica simplificada: > 50k km = Alerta. No futuro faremos por meta de CPK.
    if km_vida < 40000:
        return "🟢", "success" # Verde
    elif km_vida < 70000:
        return "🟡", "warning" # Amarelo
    else:
        return "🔴", "error"   # Vermelho

def render_frota():
    st.title("🚛 Minha Frota e Diagrama Visual")

    # 1. SELETOR DE CAMINHÃO (Para ver o diagrama)
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    
    if not dados_user:
        st.error("Usuário sem cliente vinculado.")
        return

    cliente_id = dados_user[0]['cliente_id']
    
    # Busca caminhões para o selectbox
    caminhoes = run_query("SELECT id, placa, modelo, config_eixos FROM caminhoes WHERE cliente_id = %s ORDER BY placa", (cliente_id,))
    
    if not caminhoes:
        st.warning("Nenhum caminhão cadastrado. Cadastre um na aba abaixo.")
    else:
        opcoes_caminhoes = {c['placa']: c for c in caminhoes}
        placa_selecionada = st.selectbox("Selecione o Veículo para Inspecionar", list(opcoes_caminhoes.keys()))
        
        caminhao = opcoes_caminhoes[placa_selecionada]
        
        # --- DIAGRAMA VISUAL (Baseado na Pág 7 do PDF) ---
        st.divider()
        st.subheader(f"Diagrama de Eixos: {caminhao['modelo']} ({caminhao['config_eixos']})")
        
        # Busca pneus montados neste caminhão
        pneus_montados = run_query("""
            SELECT id, marca_fogo, marca, medida, posicao_atual, km_vida_total 
            FROM pneus 
            WHERE caminhao_atual_id = %s
        """, (caminhao['id'],))
        
        # Mapeia posição -> dados do pneu para fácil acesso
        mapa_pneus = {p['posicao_atual']: p for p in pneus_montados} if pneus_montados else {}

        def card_pneu(posicao_codigo, label):
            pneu = mapa_pneus.get(posicao_codigo)
            with st.container(border=True):
                st.caption(label)
                if pneu:
                    icone, cor = get_cor_status(pneu['km_vida_total'])
                    st.markdown(f"**{pneu['marca_fogo']}**")
                    st.markdown(f"{icone} {pneu['marca']}")
                    st.caption(f"{pneu['km_vida_total']} km")
                else:
                    st.markdown("🚫 *Vazio*")

        # Layout Visual (Simulando o Caminhão de Cima)
        col_esq, col_meio, col_dir = st.columns([1, 2, 1])
        
        with col_meio:
            st.markdown("### ⬆️ FRENTE (Cabine)")
        
        # Eixo Dianteiro
        c1, c2, c3 = st.columns([1, 0.5, 1])
        with c1: card_pneu('FL', 'Dianteiro Esq')
        with c3: card_pneu('FR', 'Dianteiro Dir')
        
        st.write("") # Espaçamento
        
        # Eixo Tração / Traseiro (Depende da config, vamos fazer padrão 4 pneus atrás por enquanto)
        st.markdown("### ⬇️ TRAÇÃO / TRASEIRA")
        c4, c5, c6, c7 = st.columns([1, 1, 1, 1])
        with c4: card_pneu('TL_OUT', 'Tração Esq Fora')
        with c5: card_pneu('TL_IN', 'Tração Esq Dentro')
        with c6: card_pneu('TR_IN', 'Tração Dir Dentro')
        with c7: card_pneu('TR_OUT', 'Tração Dir Fora')

    # --- ABA DE CADASTRO (Mantida para inserir novos) ---
    st.divider()
    with st.expander("➕ Cadastrar Novo Caminhão no Sistema"):
        with st.form("form_caminhao"):
            c1, c2, c3 = st.columns(3)
            placa_input = c1.text_input("Placa").upper()
            modelo_input = c2.text_input("Modelo")
            eixos_input = c3.selectbox("Eixos", ["4x2", "6x2", "6x4"])
            
            if st.form_submit_button("Salvar Veículo"):
                try:
                    run_query(
                        "INSERT INTO caminhoes (cliente_id, placa, modelo, config_eixos) VALUES (%s, %s, %s, %s)",
                        (cliente_id, placa_input, modelo_input, eixos_input)
                    )
                    st.success("Cadastrado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")