import streamlit as st
from database import run_query
import pandas as pd
import qrcode
import io
from datetime import datetime

def sugerir_rodizio(veiculo_id):
    """Sugere melhor rodízio baseado em desgaste"""
    
    # Passo 1: Get pneus do veículo
    pneus_ativos = run_query("""
        SELECT id, marca_fogo, km_vida_total, posicao_atual, ciclo_atual
        FROM pneus 
        WHERE caminhao_atual_id = %s AND status = 'MONTADO'
    """, (veiculo_id,))
    
    pneus_repouso = run_query("""
        SELECT id, marca_fogo, km_vida_total, ciclo_atual
        FROM pneus 
        WHERE status = 'ESTOQUE'
    """)
    
    if not pneus_ativos or not pneus_repouso:
        return []
    
    # Passo 2: Calcular desgaste score cada pneu
    def calc_score(pneu):
        limite = 70000 if pneu['ciclo_atual'] > 0 else 100000
        return (pneu['km_vida_total'] / limite) * 100
    
    for p in pneus_ativos:
        p['desgaste_score'] = calc_score(p)
    
    # Passo 3: Encontrar troca ideal
    sugestoes = []
    pneus_ativos_sorted = sorted(pneus_ativos, key=lambda x: x['desgaste_score'], reverse=True)
    
    for pneu_ativo in pneus_ativos_sorted[:2]:  # Top 2 pneus mais desgastados
        for pneu_repouso in pneus_repouso:
            score_repouso = calc_score(pneu_repouso)
            if score_repouso < pneu_ativo['desgaste_score']:
                economia = pneu_ativo['desgaste_score'] - score_repouso
                sugestoes.append({
                    'trocar_de': pneu_ativo,
                    'trocar_para': pneu_repouso,
                    'economia_percentual': economia
                })
                break
    
    return sugestoes


def gerar_qr_rodizio(rodizio_id):
    """Gera QR code para operador confirmar rodízio no campo"""
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )
    qr.add_data(f"RODIZIO_{rodizio_id}")
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return buf


def executar_rodizio_app():
    """Interface Streamlit para rodízio"""
    
    st.set_page_config(page_title="Rodízio Pneus", layout="wide")
    
    st.title("🔄 Gerenciador de Rodízio de Pneus")
    
    user_id = st.session_state.get('user_id')
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    
    if not dados_user:
        st.error("Usuário não encontrado")
        return
    
    cliente_id = dados_user[0]['cliente_id']
    
    # Seleção veículo
    veiculos = run_query("""
        SELECT id, placa 
        FROM caminhoes 
        WHERE cliente_id = %s
        ORDER BY placa
    """, (cliente_id,))
    
    if not veiculos:
        st.warning("Nenhum veículo cadastrado")
        return
    
    opcoes_veiculo = {v['placa']: v['id'] for v in veiculos}
    veiculo_placa = st.selectbox("Selecione o caminhão", list(opcoes_veiculo.keys()))
    veiculo_id = opcoes_veiculo[veiculo_placa]
    
    if veiculo_placa:
        # Gerar sugestão
        sugestoes = sugerir_rodizio(veiculo_id)
        
        if not sugestoes:
            st.warning("Nenhuma sugestão de rodízio necessária no momento")
            return
        
        st.subheader(f"💡 Sugestões de Rodízio")
        
        # Exibir sugestões
        for idx, sugestao in enumerate(sugestoes):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Trocar de",
                    sugestao['trocar_de']['marca_fogo'],
                    f"Desgaste: {sugestao['trocar_de']['desgaste_score']:.0f}%"
                )
            
            with col2:
                st.metric(
                    "Trocar para",
                    sugestao['trocar_para']['marca_fogo'],
                    f"Desgaste: {sugestao['trocar_para']['desgaste_score']:.0f}%"
                )
            
            with col3:
                st.metric(
                    "Economia esperada",
                    f"{sugestao['economia_percentual']:.1f}%",
                    "Vida útil adicional"
                )
        
        # Botão confirmar
        if st.button("✅ Aprovar Sugestão", key="approve_suggestion"):
            
            # Criar ordem de rodízio
            rodizio_id = f"ROD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Executar trocas
            for sugestao in sugestoes:
                pneu_de = sugestao['trocar_de']
                pneu_para = sugestao['trocar_para']
                
                # Atualizar pneu que sai
                run_query("""
                    UPDATE pneus 
                    SET status = 'ESTOQUE', caminhao_atual_id = NULL, posicao_atual = NULL
                    WHERE id = %s
                """, (pneu_de['id'],))
                
                # Atualizar pneu que entra
                run_query("""
                    UPDATE pneus 
                    SET status = 'MONTADO', caminhao_atual_id = %s, posicao_atual = %s
                    WHERE id = %s
                """, (veiculo_id, pneu_de['posicao_atual'], pneu_para['id']))
                
                # Registrar movimento
                run_query("""
                    INSERT INTO movimentacoes (pneu_id, tipo_movimento, origem_posicao, destino_posicao, km_momento, usuario_responsavel)
                    VALUES (%s, 'RODIZIO', %s, %s, %s, %s)
                """, (pneu_de['id'], pneu_de['posicao_atual'], pneu_para['posicao_atual'], 0, user_id))
            
            st.success(f"✅ Rodízio aprovado! ID: {rodizio_id}")
            
            # Gerar QR code
            qr_buf = gerar_qr_rodizio(rodizio_id)
            st.image(qr_buf, caption="Escaneie este QR no campo", use_column_width=True)
            
            # Instruções para operador
            st.info("""
            📱 Instruções para operador:
            1. Escaneie o QR code acima
            2. Siga a lista de trocas
            3. Confirme cada troca conforme realiza
            4. Clique "Rodízio Completo"
            """)
