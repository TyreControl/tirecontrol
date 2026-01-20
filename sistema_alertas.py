"""
SISTEMA DE ALERTAS INTELIGENTES
Arquivo: sistema_alertas.py
Objetivo: Monitorar frota e gerar alertas proativos
"""

import streamlit as st
import pandas as pd
from database import run_query
from datetime import datetime
from enum import Enum

class AlertSeveridade(Enum):
    CRITICO = 1
    ALTO = 2
    MEDIO = 3
    BAIXO = 4

class SistemaAlertas:
    
    @staticmethod
    def verificar_alertas(cliente_id):
        """Verifica todas as condições de alerta"""
        
        alertas = []
        
        # ⚠️  ALERTA 1: Pneu muito velho (> 4 ciclos)
        pneus_velhos = run_query("""
            SELECT id, marca_fogo, ciclo_atual, caminhao_atual_id, posicao_atual
            FROM pneus 
            WHERE cliente_id = %s AND status = 'MONTADO' AND ciclo_atual > 4
        """, (cliente_id,))
        
        if pneus_velhos:
            for p in pneus_velhos:
                alertas.append({
                    'id': f"VELHO_{p['id']}",
                    'tipo': 'PNEU_ENVELHECIDO',
                    'severidade': AlertSeveridade.CRITICO,
                    'pneu_id': p['marca_fogo'],
                    'veiculo_id': p['caminhao_atual_id'],
                    'posicao': p['posicao_atual'],
                    'mensagem': f"Pneu {p['marca_fogo']} tem {p['ciclo_atual']} ciclos. Limite recomendado: 4",
                    'acao': 'Enviar para recapagem ou sucata HOJE',
                    'data_criacao': datetime.now(),
                    'criado_por': 'SISTEMA'
                })
        
        # ⚠️  ALERTA 2: Muitos pneus montados no mesmo caminhão (fora de padrão)
        veiculos = run_query("""
            SELECT DISTINCT caminhao_atual_id FROM pneus 
            WHERE cliente_id = %s AND status = 'MONTADO'
        """, (cliente_id,))
        
        if veiculos:
            for v in veiculos:
                count = run_query("""
                    SELECT COUNT(*) as total FROM pneus 
                    WHERE caminhao_atual_id = %s AND status = 'MONTADO'
                """, (v['caminhao_atual_id'],))
                
                if count and count[0]['total'] > 8:
                    alertas.append({
                        'id': f"RODIZIO_{v['caminhao_atual_id']}",
                        'tipo': 'RODIZIO_ATRASADO',
                        'severidade': AlertSeveridade.ALTO,
                        'pneu_id': None,
                        'veiculo_id': v['caminhao_atual_id'],
                        'posicao': None,
                        'mensagem': f"Veículo {v['caminhao_atual_id']} sem rodízio há muitos ciclos",
                        'acao': 'Incluir em próximo rodízio',
                        'data_criacao': datetime.now(),
                        'criado_por': 'SISTEMA'
                    })
        
        # ⚠️  ALERTA 3: Pneu em recapagem > 30 dias
        pneus_recapagem_atrasada = run_query("""
            SELECT id, marca_fogo, data_envio
            FROM ordens_recapagem
            WHERE cliente_id = %s AND status = 'enviado' 
            AND (NOW() - data_envio) > INTERVAL '30 days'
        """, (cliente_id,))
        
        if pneus_recapagem_atrasada:
            for p in pneus_recapagem_atrasada:
                dias = (datetime.now() - p['data_envio']).days
                alertas.append({
                    'id': f"RECAP_{p['id']}",
                    'tipo': 'RECAPAGEM_ATRASADA',
                    'severidade': AlertSeveridade.MEDIO,
                    'pneu_id': p['marca_fogo'],
                    'veiculo_id': None,
                    'posicao': None,
                    'mensagem': f"Pneu {p['marca_fogo']} em recapagem há {dias} dias",
                    'acao': 'Contactar recapadora para status',
                    'data_criacao': datetime.now(),
                    'criado_por': 'SISTEMA'
                })
        
        # ⚠️  ALERTA 4: CPK frota < 1.0 (critério grave)
        from analise_cpk import calcular_cpk_frota
        cpk_data = calcular_cpk_frota(cliente_id)
        
        if cpk_data and cpk_data['cpk'] < 1.0:
            alertas.append({
                'id': 'CPK_CRITICO',
                'tipo': 'CPK_CRITICO',
                'severidade': AlertSeveridade.CRITICO,
                'pneu_id': None,
                'veiculo_id': None,
                'posicao': None,
                'mensagem': f"CPK da frota = {cpk_data['cpk']}. PROCESSO FORA DE CONTROLE!",
                'acao': 'URGENTE: Revisar procedimentos de manutenção e rodízio',
                'data_criacao': datetime.now(),
                'criado_por': 'SISTEMA_CPK'
            })
        
        # Ordenar por severidade
        alertas.sort(key=lambda x: x['severidade'].value)
        
        return alertas
    
    @staticmethod
    def salvar_alerta(alerta):
        """Salva alerta no banco (para histórico)"""
        try:
            run_query("""
                INSERT INTO alertas_log 
                (alert_id, tipo, severidade, pneu_id, veiculo_id, mensagem, acao, data_criacao, criado_por, resolvido)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
            """, (
                alerta['id'],
                alerta['tipo'],
                alerta['severidade'].name,
                alerta['pneu_id'],
                alerta['veiculo_id'],
                alerta['mensagem'],
                alerta['acao'],
                alerta['data_criacao'],
                alerta['criado_por']
            ))
            return True
        except Exception as e:
            print(f"Erro ao salvar alerta: {e}")
            return False
    
    @staticmethod
    def marcar_resolvido(alert_id):
        """Marca alerta como resolvido"""
        try:
            run_query("""
                UPDATE alertas_log 
                SET resolvido = TRUE, data_resolucao = NOW()
                WHERE alert_id = %s
            """, (alert_id,))
            return True
        except Exception as e:
            print(f"Erro ao resolver alerta: {e}")
            return False

def mostrar_alertas_dashboard(cliente_id):
    """Interface Streamlit com alertas"""
    
    st.set_page_config(page_title="Alertas", layout="wide")
    
    st.title("🚨 Alertas do Sistema")
    st.caption("Monitoramento em tempo real da frota")
    
    # Atualizar alertas
    alertas = SistemaAlertas.verificar_alertas(cliente_id)
    
    # Salvar novos alertas
    for alerta in alertas:
        SistemaAlertas.salvar_alerta(alerta)
    
    if not alertas:
        st.success("✅ Nenhum alerta. Frota operacional!")
        return
    
    # Separar por severidade
    criticos = [a for a in alertas if a['severidade'] == AlertSeveridade.CRITICO]
    altos = [a for a in alertas if a['severidade'] == AlertSeveridade.ALTO]
    medios = [a for a in alertas if a['severidade'] == AlertSeveridade.MEDIO]
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔴 CRÍTICOS", len(criticos))
    col2.metric("🟠 ALTOS", len(altos))
    col3.metric("🟡 MÉDIOS", len(medios))
    col4.metric("📊 TOTAL", len(alertas))
    
    st.divider()
    
    # Exibir alertas por severidade
    if criticos:
        st.subheader("🔴 ALERTAS CRÍTICOS (Ação Imediata)")
        for idx, alerta in enumerate(criticos):
            with st.container(border=True):
                col_info, col_acao = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**{alerta['tipo']}**")
                    st.write(f"📌 {alerta['mensagem']}")
                    st.write(f"**Ação:** {alerta['acao']}")
                    if alerta['pneu_id']:
                        st.write(f"**Pneu:** {alerta['pneu_id']}")
                
                with col_acao:
                    if st.button("✅ Resolvido", key=f"critico_{idx}"):
                        SistemaAlertas.marcar_resolvido(alerta['id'])
                        st.success("Alerta marcado!")
                        st.rerun()
    
    if altos:
        st.subheader("🟠 ALERTAS ALTOS")
        for idx, alerta in enumerate(altos):
            with st.container(border=True):
                col_info, col_acao = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**{alerta['tipo']}**")
                    st.write(f"📌 {alerta['mensagem']}")
                    st.write(f"**Ação:** {alerta['acao']}")
                
                with col_acao:
                    if st.button("✅ Resolvido", key=f"alto_{idx}"):
                        SistemaAlertas.marcar_resolvido(alerta['id'])
                        st.success("Alerta marcado!")
                        st.rerun()
    
    if medios:
        st.subheader("🟡 ALERTAS MÉDIOS")
        for idx, alerta in enumerate(medios):
            with st.expander(f"{alerta['tipo']} - {alerta['pneu_id'] or alerta['veiculo_id']}"):
                st.write(f"📌 {alerta['mensagem']}")
                st.write(f"**Ação recomendada:** {alerta['acao']}")
                
                if st.button("✅ Resolvido", key=f"medio_{idx}"):
                    SistemaAlertas.marcar_resolvido(alerta['id'])
                    st.success("Alerta marcado!")
                    st.rerun()
    
    # Histórico de alertas
    st.divider()
    st.subheader("📋 Histórico de Alertas Resolvidos")
    
    historico = run_query("""
        SELECT tipo, severidade, mensagem, data_resolucao
        FROM alertas_log
        WHERE resolvido = TRUE
        ORDER BY data_resolucao DESC
        LIMIT 10
    """)
    
    if historico:
        df_historico = pd.DataFrame(historico)
        st.dataframe(df_historico, use_container_width=True)
    else:
        st.info("Nenhum alerta resolvido ainda")

if __name__ == "__main__":
    if 'cliente_id' not in st.session_state:
        st.error("Erro: cliente_id não configurado")
    else:
        mostrar_alertas_dashboard(st.session_state['cliente_id'])
