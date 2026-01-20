import streamlit as st
import pandas as pd
from database import run_query
from datetime import datetime, timedelta

def criar_alerta(tipo, severidade, pneu_id, mensagem, acao, usuario_id):
    """Cria um novo alerta no sistema"""
    try:
        alert_id = f"{tipo}_{pneu_id}_{datetime.now().timestamp()}"
        
        query = """
        INSERT INTO alertas_log 
        (alert_id, tipo, severidade, pneu_id, mensagem, acao, criado_por, data_criacao, resolvido)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
        """
        
        params = (alert_id, tipo, severidade, pneu_id, mensagem, acao, str(usuario_id), datetime.now())
        
        return run_query(query, params)
    except Exception as e:
        st.error(f"Erro ao criar alerta: {e}")
        return False

def obter_alertas_ativos(cliente_id):
    """Obtém todos os alertas ativos (não resolvidos) do cliente"""
    try:
        query = """
        SELECT 
            id, alert_id, tipo, severidade, pneu_id, mensagem, acao, 
            data_criacao, criado_por, resolvido
        FROM alertas_log
        WHERE resolvido = FALSE
        ORDER BY 
            CASE 
                WHEN severidade = 'CRITICO' THEN 0
                WHEN severidade = 'ALTO' THEN 1
                WHEN severidade = 'MEDIO' THEN 2
                ELSE 3
            END,
            data_criacao DESC
        """
        
        return run_query(query)
    except Exception as e:
        st.error(f"Erro ao obter alertas: {e}")
        return []

def resolver_alerta(alert_id):
    """Marca um alerta como resolvido"""
    try:
        query = """
        UPDATE alertas_log 
        SET resolvido = TRUE, data_resolucao = %s
        WHERE alert_id = %s
        """
        
        params = (datetime.now(), alert_id)
        
        return run_query(query, params)
    except Exception as e:
        st.error(f"Erro ao resolver alerta: {e}")
        return False

def verificar_alertas_automaticos(cliente_id):
    """Verifica e cria alertas automáticos baseado em regras"""
    try:
        # Buscar pneus em situação crítica
        query = """
        SELECT id, marca_fogo, months_alive, ciclos_sem_rodizio, status
        FROM pneus
        WHERE cliente_id = %s AND status IN ('MONTADO', 'ESTOQUE')
        """
        
        pneus = run_query(query, (cliente_id,))
        
        if not pneus:
            return
        
        for pneu in pneus:
            pneu_id = pneu['id']
            months_alive = pneu['months_alive'] or 0
            ciclos_sem_rodizio = pneu['ciclos_sem_rodizio'] or 0
            marca = pneu['marca_fogo']
            
            # Regra 1: Pneu envelhecido (> 48 meses)
            if months_alive > 48:
                criar_alerta(
                    tipo='PNEU_ENVELHECIDO',
                    severidade='CRITICO',
                    pneu_id=pneu_id,
                    mensagem=f"Pneu {marca} com {months_alive} meses de vida",
                    acao='Enviar para recapagem HOJE',
                    usuario_id='SISTEMA'
                )
            
            # Regra 2: Pneu com aviso (36-48 meses)
            elif months_alive > 36:
                criar_alerta(
                    tipo='PNEU_ENVELHECIDO',
                    severidade='ALTO',
                    pneu_id=pneu_id,
                    mensagem=f"Pneu {marca} com {months_alive} meses de vida",
                    acao='Agendar recapagem em breve',
                    usuario_id='SISTEMA'
                )
            
            # Regra 3: Rodízio atrasado (> 4 ciclos sem rodizio)
            if ciclos_sem_rodizio > 4:
                criar_alerta(
                    tipo='RODIZIO_ATRASADO',
                    severidade='ALTO',
                    pneu_id=pneu_id,
                    mensagem=f"Pneu {marca} sem rodízio por {ciclos_sem_rodizio} ciclos",
                    acao='Agendar rodízio urgente',
                    usuario_id='SISTEMA'
                )
    except Exception as e:
        # Este except fecha o bloco try corretamente
        print(f"Erro na verificação automática: {e}")

def render_sistema_alertas():
    """Interface Streamlit para visualizar alertas"""
    st.title("⚠️ Sistema de Alertas")
    
    if 'usuario_id' not in st.session_state:
        st.warning("Faça login primeiro")
        return
    
    usuario_id = st.session_state['usuario_id']
    
    # Buscar cliente_id da sessão ou banco
    # Usamos o ID que já está na sessão (carregado no login ou no main)
    cliente_id = st.session_state.get('cliente_id')
    
    if not cliente_id:
        st.error("Cliente não configurado na sessão.")
        return
    
    # Atualizar alertas automáticos
    if st.button("🔄 Atualizar Alertas"):
        verificar_alertas_automaticos(cliente_id)
        st.success("Alertas atualizados!")
        st.rerun()
    
    # Obter e exibir alertas
    alertas = obter_alertas_ativos(cliente_id)
    
    if not alertas:
        st.info("✓ Nenhum alerta ativo no momento")
        return
    
    # Agrupar por severidade
    for alerta in alertas:
        severidade = alerta['severidade']
        
        # Escolher cor baseada em severidade
        if severidade == 'CRITICO':
            container = st.container(border=True)
            with container:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.error(f"🔴 {alerta['tipo']} - {alerta['mensagem']}")
                    st.caption(f"Ação: {alerta['acao']}")
                    st.caption(f"Data: {alerta['data_criacao']}")
                with col2:
                    if st.button("Resolver", key=f"resolve_{alerta['alert_id']}"):
                        if resolver_alerta(alerta['alert_id']):
                            st.success("Resolvido!")
                            st.rerun()
        
        elif severidade == 'ALTO':
            container = st.container(border=True)
            with container:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.warning(f"🟠 {alerta['tipo']} - {alerta['mensagem']}")
                    st.caption(f"Ação: {alerta['acao']}")
                    st.caption(f"Data: {alerta['data_criacao']}")
                with col2:
                    if st.button("Resolver", key=f"resolve_{alerta['alert_id']}"):
                        if resolver_alerta(alerta['alert_id']):
                            st.success("Resolvido!")
                            st.rerun()
        
        else:
            container = st.container(border=True)
            with container:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.info(f"🟡 {alerta['tipo']} - {alerta['mensagem']}")
                    st.caption(f"Ação: {alerta['acao']}")
                    st.caption(f"Data: {alerta['data_criacao']}")
                with col2:
                    if st.button("Resolver", key=f"resolve_{alerta['alert_id']}"):
                        if resolver_alerta(alerta['alert_id']):
                            st.success("Resolvido!")
                            st.rerun()
    
    # Estatísticas
    st.divider()
    st.subheader("📊 Resumo de Alertas")
    
    total = len(alertas)
    criticos = len([a for a in alertas if a['severidade'] == 'CRITICO'])
    altos = len([a for a in alertas if a['severidade'] == 'ALTO'])
    medios = len([a for a in alertas if a['severidade'] == 'MEDIO'])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", total)
    col2.metric("Críticos", criticos)
    col3.metric("Altos", altos)
    col4.metric("Médios", medios)