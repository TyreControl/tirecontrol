"""
FLUXO 5 - fluxo_rodizio.py
Implementa: Sugestão + Execução de Rodízio completo
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    sugerir_rodizio_automatico,
    executar_rodizio,
    obter_historico_rodizio_veiculo,
    run_query
)

def render_rodizio():
    """Interface para sugerir e executar rodízio"""
    
    st.title("🔄 Gerenciador de Rodízio de Pneus")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    
    if not dados_user:
        st.error("Usuário não encontrado")
        return
    
    cliente_id = dados_user[0]['cliente_id']
    
    # ==================== SELEÇÃO DE VEÍCULO ====================
    query_cam = """
    SELECT id, placa, modelo, km_atual, config_eixos 
    FROM caminhoes 
    WHERE cliente_id = %s 
    ORDER BY placa
    """
    caminhoes = run_query(query_cam, (cliente_id,))
    
    if not caminhoes:
        st.warning("❌ Nenhum caminhão cadastrado")
        return
    
    opcoes = {c['placa']: c for c in caminhoes}
    placa_sel = st.selectbox("🚛 Selecione o Caminhão", list(opcoes.keys()))
    cam_sel = opcoes[placa_sel]
    
    # ==================== INFO DO CAMINHÃO ====================
    col_info1, col_info2, col_info3 = st.columns(3)
    
    with col_info1:
        st.metric("📍 Placa", cam_sel['placa'])
    
    with col_info2:
        st.metric("🛞 Config", f"{cam_sel['config_eixos']} pneus")
    
    with col_info3:
        st.metric("📊 KM Atual", f"{cam_sel['km_atual']:,} km")
    
    # ==================== GERAR SUGESTÃO ====================
    st.markdown("---")
    st.markdown("## 💡 Sugestão de Rodízio Automática")
    st.markdown("""
    O sistema analisa o desgaste de cada pneu e sugere as melhores trocas
    para maximizar a vida útil da frota.
    """)
    
    col_botoes = st.columns(3)
    
    with col_botoes[0]:
        if st.button("🔍 Gerar Sugestão de Rodízio", key="gerar_sugestao"):
            st.session_state['mostrar_sugestao'] = True
            st.session_state['sugestoes'] = None  # Reset
    
    # ==================== MOSTRAR SUGESTÃO ====================
    if st.session_state.get('mostrar_sugestao'):
        with st.spinner("⏳ Analisando desgaste dos pneus..."):
            sugestoes = sugerir_rodizio_automatico(cam_sel['id'])
        
        if sugestoes:
            st.session_state['sugestoes'] = sugestoes
            
            st.success(f"✅ Encontradas {len(sugestoes)} sugestões de troca!")
            
            # Mostrar cada sugestão em card
            for idx, sugestao in enumerate(sugestoes, 1):
                with st.expander(
                    f"**Sugestão {idx}**: Trocar {sugestao['trocar_de']['marca_fogo']} "
                    f"({sugestao['trocar_de']['desgaste_pct']}% desgastado) "
                    f"→ {sugestao['trocar_para']['marca_fogo']} (+{sugestao['economia_km']} km)",
                    expanded=(idx == 1)
                ):
                    col_de, col_seta, col_para = st.columns([3, 1, 3])
                    
                    with col_de:
                        st.markdown("### ❌ Remover")
                        st.markdown(f"""
                        **Pneu**: {sugestao['trocar_de']['marca_fogo']}
                        **Posição**: {sugestao['trocar_de']['posicao']}
                        **Desgaste**: {sugestao['trocar_de']['desgaste_pct']}%
                        **Vida**: {sugestao['trocar_de']['km_vida']} km
                        """)
                    
                    with col_seta:
                        st.markdown("<br><br>⬇️ Substituir ⬇️", unsafe_allow_html=True)
                    
                    with col_para:
                        st.markdown("### ✅ Instalar")
                        st.markdown(f"""
                        **Pneu**: {sugestao['trocar_para']['marca_fogo']}
                        **Posição**: {sugestao['trocar_de']['posicao']}
                        **Ganho**: +{sugestao['economia_km']} km
                        **Vida**: {sugestao['trocar_para']['km_vida']} km
                        """)
                    
                    st.info(f"💡 Economia esperada: **{sugestao['economia_km']} km** de vida útil adicional")
            
            # ==================== EXECUTAR RODÍZIO ====================
            st.markdown("---")
            
            col_exec1, col_exec2 = st.columns(2)
            
            with col_exec1:
                km_atual = st.number_input(
                    "KM atual do veículo",
                    value=cam_sel['km_atual'],
                    step=1000,
                    key="km_exec"
                )
            
            with col_exec2:
                motivo = st.selectbox(
                    "Motivo do Rodízio",
                    ["Rotina 8.000 km", "Rotina 16.000 km", "Desgaste Irregular", 
                     "Inspeção", "Manutenção", "Outro"],
                    key="motivo_exec"
                )
            
            if st.button("✅ EXECUTAR RODÍZIO", key="exec_rodizio", use_container_width=True):
                with st.spinner("⏳ Registrando rodízio..."):
                    sucesso = executar_rodizio(
                        veiculo_id=cam_sel['id'],
                        sugestoes=sugestoes,
                        usuario_id=user_id,
                        km_veiculo=int(km_atual),
                        motivo=motivo
                    )
                
                if sucesso:
                    st.success("✅ Rodízio executado com sucesso!")
                    st.balloons()
                    st.session_state['mostrar_sugestao'] = False
                    st.session_state['sugestoes'] = None
                    st.rerun()
                else:
                    st.error("❌ Erro ao executar rodízio")
        else:
            st.warning("ℹ️ Nenhuma sugestão de rodízio necessária no momento")
    
    # ==================== HISTÓRICO ====================
    st.markdown("---")
    st.markdown("## 📜 Histórico de Rodízios")
    
    historico = obter_historico_rodizio_veiculo(cam_sel['id'], limite=10)
    
    if historico:
        df_hist = pd.DataFrame(historico)
        
        # Formatar datas
        df_hist['data_rodizio'] = pd.to_datetime(df_hist['data_rodizio']).dt.strftime('%d/%m/%Y %H:%M')
        
        st.dataframe(
            df_hist[[
                'data_rodizio', 'km_veiculo', 'motivo'
            ]].rename(columns={
                'data_rodizio': 'Data',
                'km_veiculo': 'KM do Veículo',
                'motivo': 'Motivo'
            }),
            use_container_width=True
        )
    else:
        st.info("Nenhum rodízio registrado para este veículo")

if __name__ == "__main__":
    render_rodizio()
