import streamlit as st
import pandas as pd
import numpy as np
from database import run_query
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

def calcular_cpk_frota(cliente_id):
    """
    Calcula o CPK (Capability Process Index) da frota baseado na vida útil dos pneus.
    CPK mede se o processo (gestão de pneus) está dentro de limites aceitáveis.
    """
    try:
        # Buscar todos os pneus ativos da frota
        query = """
        SELECT 
            id, marca_fogo, months_alive, ciclo_atual, 
            km_vida_total, status, posicao_atual
        FROM pneus 
        WHERE cliente_id = %s AND status IN ('MONTADO', 'ESTOQUE')
        """
        pneus = run_query(query, (cliente_id,))
        
        if not pneus or len(pneus) == 0:
            return None, "Sem dados de pneus para calcular CPK"
        
        # Extrair dados para cálculo
        dados_vida = [p['months_alive'] if p['months_alive'] else 0 for p in pneus]
        
        # Limites de especificação (em meses)
        limite_inferior = 36  # Mínimo aceitável
        limite_superior = 48  # Máximo recomendado
        
        # Cálculos estatísticos
        media = np.mean(dados_vida)
        desvio = np.std(dados_vida)
        
        if desvio == 0:
            cpk = 0
        else:
            # CPK = min(CPK_superior, CPK_inferior)
            cpk_superior = (limite_superior - media) / (3 * desvio)
            cpk_inferior = (media - limite_inferior) / (3 * desvio)
            cpk = min(cpk_superior, cpk_inferior)
        
        # Classificação do CPK
        if cpk >= 1.33:
            status = "Excelente"
            recomendacao = "Processo sob controle. Continue monitorando."
        elif cpk >= 1.0:
            status = "Adequado"
            recomendacao = "Processo aceitável. Monitore rotineiramente."
        elif cpk >= 0.67:
            status = "Atenção"
            recomendacao = "Processo fora dos limites. Implemente melhorias."
        else:
            status = "Crítico"
            recomendacao = "Processo muito fora dos limites. Ação imediata necessária."
        
        # Registrar no histórico
        registrar_cpk_historico(cpk, media, desvio, len(pneus), status, recomendacao)
        
        return {
            'cpk': round(cpk, 2),
            'media': round(media, 2),
            'desvio': round(desvio, 2),
            'quantidade': len(pneus),
            'status': status,
            'recomendacao': recomendacao,
            'limite_inferior': limite_inferior,
            'limite_superior': limite_superior
        }, None
        
    except Exception as e:
        return None, f"Erro ao calcular CPK: {str(e)}"

def registrar_cpk_historico(cpk_valor, media, desvio, quantidade_pneus, status, recomendacao):
    """Registra o cálculo de CPK no banco para histórico"""
    try:
        query = """
        INSERT INTO cpk_historico 
        (data_calculo, cpk_valor, media, desvio, quantidade_pneus, status, recomendacao)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            datetime.now(),
            cpk_valor,
            media,
            desvio,
            quantidade_pneus,
            status,
            recomendacao
        )
        run_query(query, params)
    except Exception as e:
        print(f"Erro ao registrar CPK no histórico: {e}")

def obter_historico_cpk(cliente_id, dias=30):
    """Obtém histórico de CPK dos últimos N dias"""
    try:
        query = """
        SELECT 
            data_calculo, cpk_valor, media, desvio, 
            quantidade_pneus, status, recomendacao
        FROM cpk_historico
        WHERE data_calculo >= NOW() - INTERVAL '%s days'
        ORDER BY data_calculo DESC
        LIMIT 10
        """
        return run_query(query, (dias,))
    except Exception as e:
        print(f"Erro ao obter histórico CPK: {e}")
        return []

def render_analise_cpk():
    """Interface Streamlit para análise de CPK da frota"""
    st.title("📊 Análise de CPK - Qualidade da Gestão de Pneus")
    
    # Obter cliente_id da sessão
    if 'usuario_id' not in st.session_state:
        st.warning("Faça login primeiro")
        return
    
    usuario_id = st.session_state['usuario_id']
    
    # Buscar cliente_id do usuário
    query_cliente = "SELECT cliente_id FROM usuarios WHERE id = %s"
    resultado = run_query(query_cliente, (usuario_id,))
    
    if not resultado:
        st.error("Usuário não encontrado")
        return
    
    cliente_id = resultado[0]['cliente_id']
    
    # Calcular CPK atual
    st.subheader("📈 CPK Atual da Frota")
    
    cpk_dados, erro = calcular_cpk_frota(cliente_id)
    
    if erro:
        st.error(f"Erro: {erro}")
        return
    
    if not cpk_dados:
        st.warning("Sem dados de pneus para calcular CPK")
        return
    
    # Exibir métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("CPK", cpk_dados['cpk'], delta="Índice")
    
    with col2:
        st.metric("Média (meses)", cpk_dados['media'])
    
    with col3:
        st.metric("Desvio Padrão", cpk_dados['desvio'])
    
    with col4:
        st.metric("Pneus Analisados", cpk_dados['quantidade'])
    
    # Status visual
    st.divider()
    
    col_status1, col_status2 = st.columns(2)
    
    with col_status1:
        # Classificação com cores
        if cpk_dados['status'] == "Excelente":
            st.success(f"✅ Status: {cpk_dados['status']}")
        elif cpk_dados['status'] == "Adequado":
            st.info(f"✓ Status: {cpk_dados['status']}")
        elif cpk_dados['status'] == "Atenção":
            st.warning(f"⚠️ Status: {cpk_dados['status']}")
        else:
            st.error(f"❌ Status: {cpk_dados['status']}")
    
    with col_status2:
        st.markdown(f"**Recomendação:** {cpk_dados['recomendacao']}")
    
    # Gráfico de distribuição
    st.subheader("📉 Distribuição de Vida Útil dos Pneus")
    
    # Buscar dados dos pneus
    query_pneus = """
    SELECT months_alive FROM pneus 
    WHERE cliente_id = %s AND status IN ('MONTADO', 'ESTOQUE')
    """
    pneus_data = run_query(query_pneus, (cliente_id,))
    
    if pneus_data:
        dados_vida = [p['months_alive'] if p['months_alive'] else 0 for p in pneus_data]
        
        # Criar histograma com Plotly
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=dados_vida,
            nbinsx=15,
            name='Distribuição',
            marker_color='rgba(0, 150, 200, 0.7)',
            showlegend=False
        ))
        
        # Adicionar linhas de limite
        fig.add_vline(
            x=cpk_dados['limite_inferior'],
            line_dash="dash",
            line_color="orange",
            annotation_text="Mín. Aceitável",
            annotation_position="top left"
        )
        
        fig.add_vline(
            x=cpk_dados['limite_superior'],
            line_dash="dash",
            line_color="red",
            annotation_text="Máx. Recomendado",
            annotation_position="top right"
        )
        
        fig.update_layout(
            title="Distribuição de Vida Útil (Meses)",
            xaxis_title="Meses de Vida",
            yaxis_title="Quantidade de Pneus",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Histórico de CPK
    st.subheader("📋 Histórico de CPK")
    
    historico = obter_historico_cpk(cliente_id)
    
    if historico:
        df_historico = pd.DataFrame([
            {
                'Data': p['data_calculo'],
                'CPK': round(p['cpk_valor'], 2),
                'Média': round(p['media'], 2),
                'Desvio': round(p['desvio'], 2),
                'Status': p['status'],
                'Recomendação': p['recomendacao']
            }
            for p in historico
        ])
        
        st.dataframe(df_historico, use_container_width=True)
        
        # Gráfico de evolução do CPK
        fig_evolucao = px.line(
            df_historico,
            x='Data',
            y='CPK',
            title='Evolução do CPK',
            markers=True
        )
        
        st.plotly_chart(fig_evolucao, use_container_width=True)
    else:
        st.info("Nenhum histórico disponível ainda")
    
    # Interpretação do CPK
    st.subheader("ℹ️ Interpretação do CPK")
    
    with st.expander("O que é CPK?"):
        st.markdown("""
        **CPK (Capability Process Index)** é um índice estatístico que mede se o processo 
        de gestão de pneus está dentro dos limites de especificação.
        
        - **CPK ≥ 1.33**: Excelente - Processo altamente capaz
        - **CPK 1.0 - 1.32**: Adequado - Processo aceitável
        - **CPK 0.67 - 0.99**: Atenção - Processo fora dos limites
        - **CPK < 0.67**: Crítico - Ação corretiva necessária
        
        **Limites utilizados:**
        - Mínimo aceitável: 36 meses
        - Máximo recomendado: 48 meses
        """)

if __name__ == "__main__":
    render_analise_cpk()
