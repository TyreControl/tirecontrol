import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import run_query
from datetime import datetime, timedelta

def obter_relatorio_pneus_frota(cliente_id):
    """Obtém relatório consolidado de pneus da frota"""
    try:
        query = """
        SELECT 
            p.id,
            p.marca_fogo,
            p.marca,
            p.medida,
            p.status,
            p.ciclo_atual,
            p.km_vida_total,
            p.months_alive,
            p.ciclos_sem_rodizio,
            c.placa as veiculo_placa
        FROM pneus p
        LEFT JOIN caminhoes c ON p.caminhao_atual_id = c.id
        WHERE p.cliente_id = %s
        ORDER BY p.status, p.months_alive DESC
        """
        
        return run_query(query, (cliente_id,))
    except Exception as e:
        st.error(f"Erro ao obter relatório: {e}")
        return []

def obter_movimentacoes_periodo(cliente_id, dias=30):
    """Obtém movimentações de pneus do período"""
    try:
        query = """
        SELECT 
            m.tipo_movimento,
            m.data_movimento,
            p.marca_fogo,
            p.medida,
            COUNT(*) as total
        FROM movimentacoes m
        LEFT JOIN pneus p ON m.pneu_id = p.id
        WHERE p.cliente_id = %s 
        AND m.data_movimento >= NOW() - INTERVAL '%s days'
        GROUP BY m.tipo_movimento, m.data_movimento, p.marca_fogo, p.medida
        ORDER BY m.data_movimento DESC
        """
        
        return run_query(query, (cliente_id, dias))
    except Exception as e:
        st.error(f"Erro ao obter movimentações: {e}")
        return []

def obter_custos_manutencao(cliente_id, periodo_meses=12):
    """Obtém custos de manutenção do período"""
    try:
        query = """
        SELECT 
            DATE_TRUNC('month', m.data_movimento) as mes,
            m.tipo_movimento,
            SUM(COALESCE(p.custo_servico, 0)) as custo_total,
            COUNT(*) as quantidade
        FROM movimentacoes m
        LEFT JOIN pneus p ON m.pneu_id = p.id
        WHERE p.cliente_id = %s
        AND m.data_movimento >= NOW() - INTERVAL '%s months'
        GROUP BY DATE_TRUNC('month', m.data_movimento), m.tipo_movimento
        ORDER BY mes DESC
        """
        
        return run_query(query, (cliente_id, periodo_meses))
    except Exception as e:
        st.error(f"Erro ao obter custos: {e}")
        return []

def render_relatorios():
    """Interface Streamlit para relatórios"""
    st.title("📊 Relatórios e Análises")
    
    if 'usuario_id' not in st.session_state:
        st.warning("Faça login primeiro")
        return
    
    usuario_id = st.session_state['usuario_id']
    
    # Buscar cliente_id
    query_cliente = "SELECT cliente_id FROM usuarios WHERE id = %s"
    resultado = run_query(query_cliente, (usuario_id,))
    
    if not resultado:
        st.error("Usuário não encontrado")
        return
    
    cliente_id = resultado[0]['cliente_id']
    
    # Seleção de período
    col1, col2 = st.columns(2)
    
    with col1:
        dias_selecionados = st.slider(
            "Período de Análise (dias)",
            min_value=7,
            max_value=365,
            value=30,
            step=7
        )
    
    with col2:
        st.metric("Período Selecionado", f"{dias_selecionados} dias")
    
    st.divider()
    
    # Tabs para diferentes relatórios
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Frota", "Movimentações", "Custos", "Alertas"]
    )
    
    with tab1:
        st.subheader("📦 Relatório Geral da Frota")
        
        pneus = obter_relatorio_pneus_frota(cliente_id)
        
        if not pneus:
            st.info("Nenhum pneu cadastrado")
        else:
            # Estatísticas gerais
            df_pneus = pd.DataFrame([
                {
                    'Marca de Fogo': p['marca_fogo'],
                    'Marca': p['marca'],
                    'Medida': p['medida'],
                    'Status': p['status'],
                    'Ciclo': p['ciclo_atual'],
                    'KM Vida': p['km_vida_total'],
                    'Meses': p['months_alive'],
                    'Ciclos sem Rodízio': p['ciclos_sem_rodizio'],
                    'Veículo': p['veiculo_placa'] or 'N/A'
                }
                for p in pneus
            ])
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            
            total_pneus = len(df_pneus)
            pneus_montados = len(df_pneus[df_pneus['Status'] == 'MONTADO'])
            pneus_estoque = len(df_pneus[df_pneus['Status'] == 'ESTOQUE'])
            pneus_recapagem = len(df_pneus[df_pneus['Status'] == 'RECAPAGEM'])
            
            with col1:
                st.metric("Total de Pneus", total_pneus)
            
            with col2:
                st.metric("Montados", pneus_montados)
            
            with col3:
                st.metric("Estoque", pneus_estoque)
            
            with col4:
                st.metric("Recapagem", pneus_recapagem)
            
            st.divider()
            
            # Gráfico de distribuição por status
            status_count = df_pneus['Status'].value_counts()
            fig_status = px.pie(
                values=status_count.values,
                names=status_count.index,
                title='Distribuição de Pneus por Status',
                hole=0.3
            )
            st.plotly_chart(fig_status, use_container_width=True)
            
            st.divider()
            
            # Tabela de detalhes
            st.subheader("📋 Detalhes de Pneus")
            
            # Filtro por status
            status_filtro = st.multiselect(
                "Filtrar por Status",
                df_pneus['Status'].unique(),
                default=df_pneus['Status'].unique()
            )
            
            df_filtrado = df_pneus[df_pneus['Status'].isin(status_filtro)]
            
            st.dataframe(df_filtrado, use_container_width=True)
            
            # Download como CSV
            csv = df_filtrado.to_csv(index=False)
            st.download_button(
                label="📥 Baixar como CSV",
                data=csv,
                file_name=f"relatorio_pneus_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    with tab2:
        st.subheader("📊 Movimentações de Pneus")
        
        movimentacoes = obter_movimentacoes_periodo(cliente_id, dias_selecionados)
        
        if not movimentacoes:
            st.info("Nenhuma movimentação neste período")
        else:
            df_movimentacoes = pd.DataFrame([
                {
                    'Data': m['data_movimento'],
                    'Tipo': m['tipo_movimento'],
                    'Marca de Fogo': m['marca_fogo'],
                    'Total': m['total']
                }
                for m in movimentacoes
            ])
            
            # Gráfico de movimentações por tipo
            fig_mov = px.bar(
                df_movimentacoes.groupby('Tipo').size().reset_index(name='Total'),
                x='Tipo',
                y='Total',
                title='Movimentações por Tipo',
                color='Total'
            )
            st.plotly_chart(fig_mov, use_container_width=True)
            
            st.divider()
            
            # Tabela de movimentações
            st.dataframe(df_movimentacoes, use_container_width=True)
    
    with tab3:
        st.subheader("💰 Custos de Manutenção")
        
        custos = obter_custos_manutencao(cliente_id, periodo_meses=12)
        
        if not custos:
            st.info("Nenhum custo registrado")
        else:
            df_custos = pd.DataFrame([
                {
                    'Mês': c['mes'],
                    'Tipo': c['tipo_movimento'],
                    'Custo Total': c['custo_total'],
                    'Quantidade': c['quantidade']
                }
                for c in custos
            ])
            
            # Métrica de custo total
            custo_total = df_custos['Custo Total'].sum()
            st.metric("Custo Total (12 meses)", f"R$ {custo_total:,.2f}")
            
            st.divider()
            
            # Gráfico de custos por mês
            fig_custos = px.bar(
                df_custos.groupby('Mês')['Custo Total'].sum().reset_index(),
                x='Mês',
                y='Custo Total',
                title='Custos de Manutenção ao Longo do Tempo',
                markers=True
            )
            st.plotly_chart(fig_custos, use_container_width=True)
            
            st.divider()
            
            # Tabela de custos
            st.dataframe(df_custos, use_container_width=True)
    
    with tab4:
        st.subheader("⚠️ Resumo de Alertas")
        
        query_alertas = """
        SELECT 
            severidade,
            COUNT(*) as total
        FROM alertas_log
        WHERE resolvido = FALSE
        GROUP BY severidade
        """
        
        alertas = run_query(query_alertas)
        
        if alertas:
            df_alertas = pd.DataFrame([
                {'Severidade': a['severidade'], 'Total': a['total']}
                for a in alertas
            ])
            
            # Gráfico de alertas
            fig_alertas = px.bar(
                df_alertas,
                x='Severidade',
                y='Total',
                title='Alertas Ativos por Severidade',
                color='Severidade'
            )
            st.plotly_chart(fig_alertas, use_container_width=True)
        else:
            st.success("✓ Nenhum alerta ativo")
