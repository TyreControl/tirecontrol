"""
INTEGRAÇÃO COM RECAPADORA
Arquivo: integracao_recapadora.py
Objetivo: Fluxo de envio e rastreamento de pneus para recapagem
"""

import streamlit as st
import pandas as pd
from database import run_query
from datetime import datetime, timedelta
import qrcode
import io

def enviar_pneus_recapadora(cliente_id, lista_pneus_ids, recapadora_nome, observacoes=""):
    """
    Envia lista de pneus para recapadora
    """
    
    if not lista_pneus_ids:
        raise ValueError("Lista de pneus vazia")
    
    try:
        # Step 1: Validar pneus existem
        pneus = run_query("""
            SELECT id, marca_fogo, medida FROM pneus 
            WHERE id IN ({})
        """.format(','.join(['%s'] * len(lista_pneus_ids))), 
        tuple(lista_pneus_ids))
        
        if not pneus:
            raise ValueError("Nenhum pneu encontrado")
        
        # Step 2: Criar ordem
        ordem_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        run_query("""
            INSERT INTO ordens_recapagem 
            (ordem_id, cliente_id, recapadora, status, data_criacao, data_envio, data_entrega_esperada, observacoes)
            VALUES (%s, %s, %s, 'enviado', NOW(), NOW(), NOW() + INTERVAL '14 days', %s)
        """, (ordem_id, cliente_id, recapadora_nome, observacoes))
        
        # Step 3: Atualizar status dos pneus
        for pneu_id in lista_pneus_ids:
            run_query("""
                UPDATE pneus 
                SET status = 'RECAPAGEM', caminhao_atual_id = NULL, posicao_atual = NULL
                WHERE id = %s
            """, (pneu_id,))
        
        return ordem_id, len(pneus)
    
    except Exception as e:
        raise Exception(f"Erro ao enviar recapagem: {str(e)}")

def gerar_qr_code(texto):
    """Gera QR code para rastreamento"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )
    qr.add_data(texto)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return buf

def acompanhar_ordem_recapagem(ordem_id):
    """
    Gerente pode acompanhar status da ordem
    """
    
    ordem = run_query("""
        SELECT * FROM ordens_recapagem 
        WHERE ordem_id = %s
    """, (ordem_id,))
    
    if not ordem:
        return None
    
    ordem = ordem[0]
    
    tempo_decorrido = (datetime.now() - ordem['data_envio']).days
    tempo_previsto = (ordem['data_entrega_esperada'] - ordem['data_envio']).days
    
    percentual = min((tempo_decorrido / tempo_previsto * 100) if tempo_previsto > 0 else 0, 100)
    
    # Contar pneus
    count = run_query("""
        SELECT COUNT(*) as total FROM pneus 
        WHERE status = 'RECAPAGEM'
    """)
    
    return {
        'ordem_id': ordem['ordem_id'],
        'recapadora': ordem['recapadora'],
        'quantidade_pneus': count[0]['total'] if count else 0,
        'status': ordem['status'],
        'data_envio': ordem['data_envio'].strftime('%d/%m/%Y'),
        'data_esperada': ordem['data_entrega_esperada'].strftime('%d/%m/%Y'),
        'dias_decorridos': tempo_decorrido,
        'dias_restantes': tempo_previsto - tempo_decorrido,
        'percentual_progresso': round(percentual, 1),
        'observacoes': ordem['observacoes']
    }

def render_fluxo_recapadora(cliente_id):
    """Interface Streamlit para fluxo de recapagem"""
    
    st.set_page_config(page_title="Recapagem", layout="wide")
    
    st.title("♻️ Fluxo de Recapagem")
    st.caption("Gerenciamento de envio e rastreamento de pneus para recapagem")
    
    tab1, tab2, tab3 = st.tabs(["📤 Enviar Pneus", "📥 Receber Pronto", "📊 Acompanhar Ordens"])
    
    # TAB 1: ENVIAR PNEUS
    with tab1:
        st.subheader("Enviar Pneus para Recapagem")
        
        # Buscar pneus elegíveis
        pneus_elegíveis = run_query("""
            SELECT id, marca_fogo, marca, medida, km_vida_total, ciclo_atual, posicao_atual
            FROM pneus 
            WHERE cliente_id = %s AND status = 'MONTADO' AND ciclo_atual <= 3
            ORDER BY km_vida_total DESC
        """, (cliente_id,))
        
        if not pneus_elegíveis:
            st.info("Nenhum pneu elegível para recapagem no momento")
        else:
            with st.form("form_enviar_recap"):
                st.markdown("**Selecione os pneus para recapagem:**")
                
                pneus_selecionados = st.multiselect(
                    "Pneus",
                    options=pneus_elegíveis,
                    format_func=lambda p: f"{p['marca_fogo']} - {p['marca']} ({p['medida']}) - {p['km_vida_total']} km",
                    key="select_tires"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    recapadora = st.text_input("Nome da Recapadora (ex: Recapadora ABC)")
                with col2:
                    os_numero = st.text_input("Número da OS/Coleta (opcional)")
                
                observacoes = st.text_area("Observações (defeitos, danos, etc.)", height=100)
                
                if st.form_submit_button("📤 Enviar para Recapagem"):
                    if not pneus_selecionados:
                        st.error("Selecione pelo menos um pneu")
                    elif not recapadora:
                        st.error("Digite o nome da recapadora")
                    else:
                        try:
                            pneu_ids = [p['id'] for p in pneus_selecionados]
                            ordem_id, quantidade = enviar_pneus_recapadora(
                                cliente_id, 
                                pneu_ids, 
                                recapadora,
                                observacoes
                            )
                            
                            st.success(f"✅ {quantidade} pneus enviados com sucesso!")
                            st.info(f"**Ordem ID:** {ordem_id}")
                            
                            # Gerar QR code
                            qr_buf = gerar_qr_code(ordem_id)
                            st.image(qr_buf, caption="QR Code da Ordem", use_column_width=False, width=200)
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {str(e)}")
    
    # TAB 2: RECEBER PRONTO
    with tab2:
        st.subheader("Receber Pneus Recapados")
        
        # Buscar pneus em recapagem
        pneus_em_recap = run_query("""
            SELECT id, marca_fogo, marca, medida FROM pneus 
            WHERE cliente_id = %s AND status = 'RECAPAGEM'
            ORDER BY marca_fogo
        """, (cliente_id,))
        
        if not pneus_em_recap:
            st.info("Nenhum pneu em recapagem no momento")
        else:
            with st.form("form_receber_recap"):
                st.markdown("**Pneus retornando da recapagem:**")
                
                pneus_retorno = st.multiselect(
                    "Selecione os pneus retornados",
                    options=pneus_em_recap,
                    format_func=lambda p: f"{p['marca_fogo']} - {p['marca']} ({p['medida']})",
                    key="select_return"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    custo_servico = st.number_input("Custo Total do Serviço (R$)", min_value=0.0, step=50.0)
                with col2:
                    banda = st.selectbox(
                        "Banda Aplicada",
                        ["Banda A (Novo)", "Banda B (Premium)", "Banda C (Padrão)"]
                    )
                
                if st.form_submit_button("📥 Dar Entrada no Estoque"):
                    if not pneus_retorno:
                        st.error("Selecione pelo menos um pneu")
                    else:
                        try:
                            for pneu in pneus_retorno:
                                run_query("""
                                    UPDATE pneus 
                                    SET status = 'ESTOQUE', 
                                        ciclo_atual = ciclo_atual + 1,
                                        modelo = %s,
                                        km_vida_total = 0,
                                        caminhao_atual_id = NULL,
                                        posicao_atual = NULL
                                    WHERE id = %s
                                """, (f"Recap - {banda}", pneu['id']))
                            
                            st.success(f"✅ {len(pneus_retorno)} pneus renovados e disponíveis no estoque!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {str(e)}")
    
    # TAB 3: ACOMPANHAR ORDENS
    with tab3:
        st.subheader("Acompanhamento de Ordens")
        
        ordens = run_query("""
            SELECT ordem_id, recapadora, status, data_envio, data_entrega_esperada
            FROM ordens_recapagem
            WHERE cliente_id = %s
            ORDER BY data_envio DESC
            LIMIT 10
        """, (cliente_id,))
        
        if not ordens:
            st.info("Nenhuma ordem de recapagem registrada")
        else:
            for ordem in ordens:
                status_info = acompanhar_ordem_recapagem(ordem['ordem_id'])
                
                if status_info:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown(f"**Ordem:** {status_info['ordem_id']}")
                            st.write(f"**Recapadora:** {status_info['recapadora']}")
                        
                        with col2:
                            st.metric("Status", status_info['status'].upper())
                            st.metric("Pneus", status_info['quantidade_pneus'])
                        
                        with col3:
                            st.write(f"**Enviado:** {status_info['data_envio']}")
                            st.write(f"**Esperado:** {status_info['data_esperada']}")
                        
                        # Barra de progresso
                        st.progress(status_info['percentual_progresso'] / 100)
                        st.caption(f"Progresso: {status_info['percentual_progresso']:.0f}% "
                                  f"({status_info['dias_decorridos']} de {status_info['dias_decorridos'] + status_info['dias_restantes']} dias)")

if __name__ == "__main__":
    if 'cliente_id' not in st.session_state:
        st.error("Erro: cliente_id não configurado")
    else:
        render_fluxo_recapadora(st.session_state['cliente_id'])
