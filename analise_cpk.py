"""
ANÁLISE CPK - CONTROLE DE QUALIDADE
Arquivo: analise_cpk.py
Objetivo: Calcular CPK e monitorar qualidade da frota
"""

import streamlit as st
import pandas as pd
import numpy as np
from database import run_query
import matplotlib.pyplot as plt
from datetime import datetime

def calcular_cpk_frota(cliente_id):
    """
    CPK = Capability Process Index
    Mede se seu processo está dentro dos limites aceitáveis
    
    CPK > 1.67: Excelente
    CPK > 1.33: Adequado
    CPK > 1.0:  Atenção
    CPK < 1.0:  Crítico
    """
    
    # Buscar todos os pneus montados
    all_tires = run_query(
        "SELECT km_vida_total, ciclo_atual FROM pneus WHERE cliente_id = %s AND status = 'MONTADO'",
        (cliente_id,)
    )
    
    if not all_tires:
        return None
    
    # Converter para numpy array
    vidas_uteis = np.array([t['km_vida_total'] for t in all_tires])
    
    # Estatísticas
    media = np.mean(vidas_uteis)
    desvio_padrao = np.std(vidas_uteis)
    
    # Limites especificados
    USL = 70000  # Upper Spec Limit (máximo desejável)
    LSL = 12000  # Lower Spec Limit (mínimo aceitável)
    
    # Cálculo CPK
    if desvio_padrao == 0:
        cpk = float('inf')
    else:
        cpk_superior = (USL - media) / (3 * desvio_padrao)
        cpk_inferior = (media - LSL) / (3 * desvio_padrao)
        cpk = min(cpk_superior, cpk_inferior)
    
    # Status
    if cpk > 1.67:
        status = "🟢 EXCELENTE"
        recomendacao = "Continue o processo atual. Manter padrão."
        cor = "#ccffcc"
    elif cpk > 1.33:
        status = "🟡 ADEQUADO"
        recomendacao = "Monitorar mensalmente. Tudo dentro do esperado."
        cor = "#fff4cc"
    elif cpk > 1.0:
        status = "🟠 ATENÇÃO"
        recomendacao = "Revisar procedimentos. Aumentar frequência rodízio."
        cor = "#ffdbcc"
    else:
        status = "🔴 CRÍTICO"
        recomendacao = "AÇÃO IMEDIATA! Processo fora de controle."
        cor = "#ffcccc"
    
    # Percentual dentro spec
    dentro_spec = np.sum((vidas_uteis >= LSL) & (vidas_uteis <= USL)) / len(vidas_uteis) * 100
    
    return {
        'cpk': round(cpk, 2),
        'media': round(media, 1),
        'desvio': round(desvio_padrao, 1),
        'status': status,
        'recomendacao': recomendacao,
        'minimo': LSL,
        'maximo': USL,
        'percentual_dentro_spec': round(dentro_spec, 1),
        'total_tires': len(vidas_uteis),
        'cor': cor,
        'vidas': vidas_uteis.tolist()
    }

def mostrar_cpk_dashboard(cliente_id):
    """Interface Streamlit com CPK"""
    
    st.set_page_config(page_title="CPK Analysis", layout="wide")
    
    st.title("📊 Análise de Qualidade (CPK)")
    st.caption("Capability Process Index - Monitoramento de Performance da Frota")
    
    cpk_data = calcular_cpk_frota(cliente_id)
    
    if not cpk_data:
        st.warning("Sem dados de pneus montados para análise")
        return
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("CPK", cpk_data['cpk'], delta=None)
    
    with col2:
        st.metric("Média vida útil", f"{cpk_data['media']:.0f} km")
    
    with col3:
        st.metric("Desvio padrão", f"{cpk_data['desvio']:.0f} km")
    
    with col4:
        st.metric("% Dentro spec", f"{cpk_data['percentual_dentro_spec']:.1f}%")
    
    # Status com cor
    st.markdown(f"""
    <div style='background-color: {cpk_data['cor']}; padding: 1rem; border-radius: 0.5rem; text-align: center;'>
        <h2>{cpk_data['status']}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.info(f"💡 {cpk_data['recomendacao']}")
    
    # Gráfico distribuição
    st.subheader("📈 Distribuição de Vida Útil dos Pneus")
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    ax.hist(cpk_data['vidas'], bins=15, edgecolor='black', color='skyblue', alpha=0.7)
    ax.axvline(cpk_data['media'], color='red', linestyle='--', linewidth=2, label=f'Média: {cpk_data["media"]:.0f} km')
    ax.axvline(cpk_data['minimo'], color='green', linestyle='--', linewidth=2, label=f'Min: {cpk_data["minimo"]} km')
    ax.axvline(cpk_data['maximo'], color='orange', linestyle='--', linewidth=2, label=f'Max: {cpk_data["maximo"]} km')
    
    ax.set_xlabel('Km de Vida Útil', fontsize=12)
    ax.set_ylabel('Quantidade Pneus', fontsize=12)
    ax.legend()
    ax.grid(alpha=0.3)
    
    st.pyplot(fig)
    
    # Análise detalhada
    st.subheader("🔍 Análise Detalhada")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.metric("Total de pneus montados", cpk_data['total_tires'])
    
    with col_b:
        st.metric("Pneus fora do spec", 
                 cpk_data['total_tires'] - int(cpk_data['total_tires'] * cpk_data['percentual_dentro_spec'] / 100))
    
    # Recomendações baseadas em CPK
    st.subheader("💼 Recomendações de Ação")
    
    if cpk_data['cpk'] < 1.0:
        st.error("""
        **CRÍTICO - Processo Fora de Controle**
        - Revisar imediatamente procedimentos de manutenção
        - Aumentar frequência de rodízios
        - Auditar qualidade de novos pneus
        - Considerar recapagem mais frequente
        """)
    elif cpk_data['cpk'] < 1.33:
        st.warning("""
        **ATENÇÃO - Processo em Limite**
        - Monitorar mensalmente as métricas
        - Aumentar frequência de rodízios
        - Revisar procedimentos de instalação
        - Planejar ações preventivas
        """)
    else:
        st.success("""
        **OK - Processo sob Controle**
        - Manter procedimentos atuais
        - Monitorar mensalmente
        - Continuar com plano de manutenção
        """)

if __name__ == "__main__":
    if 'cliente_id' not in st.session_state:
        st.error("Erro: cliente_id não configurado")
    else:
        mostrar_cpk_dashboard(st.session_state['cliente_id'])
