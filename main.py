#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - TyreControl Application (STABLE VERSION - ADAPTADO PARA SEU BANCO)
Usa apenas funções que existem em seu database.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only functions that exist in YOUR database.py
from database import (
    run_query,
    get_pneu_by_id,
    get_pneus_by_veiculo,
    atualizar_posicao_pneu,
    atualizar_status_pneu,
    validar_cadastro_pneu,
    validar_movimento,
    listar_alertas_ativos,
    get_todos_clientes,
    get_detalhes_cliente,
    atualizar_dados_cliente,
)

# Page config
st.set_page_config(
    page_title="TyreControl",
    page_icon="🛞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customization
st.markdown("""
    <style>
    .main { padding: 2rem; }
    .metric-card { background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; }
    .alert-error { background-color: #ffebee; border-left: 4px solid #c62828; padding: 1rem; }
    .alert-warning { background-color: #fff3e0; border-left: 4px solid #e65100; padding: 1rem; }
    .alert-success { background-color: #e8f5e9; border-left: 4px solid #2e7d32; padding: 1rem; }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session():
    """Initialize session state"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'cliente_id' not in st.session_state:
        st.session_state.cliente_id = None

# ============================================================================
# AUTHENTICATION
# ============================================================================

def login_page():
    """Simple login page"""
    st.title("🛞 TyreControl")
    st.markdown("### Sistema de Gestão de Pneus e Frota")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.info("👤 **Acesso de Demonstração**")
        role = st.selectbox("Selecione seu papel:", ["Admin", "Cliente", "Técnico"])
        
        if st.button("Entrar", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.user_role = role
            st.session_state.cliente_id = "demo-cliente"
            st.success(f"✅ Bem-vindo, {role}!")
            st.rerun()
    
    with col2:
        st.warning("⚠️ **Modo Demonstração**")
        st.write("Esta é uma versão de demonstração.")
        st.write("Use dados reais após conectar ao banco de dados.")

# ============================================================================
# PAGES
# ============================================================================

def home_page():
    """Home page with dashboard"""
    st.title("🏠 Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        # Try to get real data
        alertas = listar_alertas_ativos()
        num_alertas = len(alertas) if alertas else 0
        
        with col1:
            st.metric("⚠️ Alertas Ativos", num_alertas)
        with col2:
            st.metric("🛞 Pneus Totais", "N/A")
        with col3:
            st.metric("🚚 Caminhões", "N/A")
        with col4:
            st.metric("🔄 Rodízios", "N/A")
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar dados: {str(e)}")
        
        with col1:
            st.metric("⚠️ Alertas Ativos", 0)
        with col2:
            st.metric("🛞 Pneus Totais", "N/A")
        with col3:
            st.metric("🚚 Caminhões", "N/A")
        with col4:
            st.metric("🔄 Rodízios", "N/A")
    
    st.divider()
    
    # Alertas section
    st.subheader("🔴 Alertas Críticos")
    try:
        alertas = listar_alertas_ativos()
        if alertas and len(alertas) > 0:
            df_alertas = pd.DataFrame(alertas[:5])
            st.dataframe(df_alertas, use_container_width=True)
        else:
            st.info("✅ Nenhum alerta crítico no momento")
    except Exception as e:
        st.info("✅ Nenhum alerta crítico no momento")

def gestao_pneus_page():
    """Tire management page"""
    st.title("🛞 Gestão de Pneus")
    
    tab1, tab2, tab3 = st.tabs(["📊 Buscar Pneu", "🔧 Atualizar Status", "📈 Histórico de Alertas"])
    
    with tab1:
        st.subheader("Buscar Dados do Pneu")
        pneu_id = st.text_input("ID do Pneu", placeholder="ex: PNEU-001")
        
        if st.button("🔍 Buscar", use_container_width=True):
            if pneu_id:
                try:
                    pneu = get_pneu_by_id(pneu_id)
                    if pneu:
                        st.success("✅ Pneu encontrado!")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Marca Fogo", pneu.get('marca_fogo', 'N/A'))
                        with col2:
                            st.metric("Status", pneu.get('status', 'N/A'))
                        with col3:
                            st.metric("Posição", pneu.get('posicao_atual', 'N/A'))
                        
                        st.dataframe(pd.DataFrame([pneu]), use_container_width=True)
                    else:
                        st.warning("⚠️ Pneu não encontrado")
                except Exception as e:
                    st.error(f"❌ Erro ao buscar pneu: {str(e)}")
            else:
                st.warning("⚠️ Digite o ID do pneu")
    
    with tab2:
        st.subheader("Atualizar Status do Pneu")
        
        pneu_update_id = st.text_input("ID do Pneu a Atualizar", placeholder="ex: PNEU-001", key="pneu_update")
        novo_status = st.selectbox("Novo Status", ["NOVO", "BOM", "ALERTA", "DESCARTADO", "RECAPAGEM", "REPOUSO"])
        
        if st.button("✅ Atualizar Status", use_container_width=True):
            if pneu_update_id:
                try:
                    resultado = atualizar_status_pneu(pneu_update_id, novo_status)
                    if resultado:
                        st.success(f"✅ Status do pneu {pneu_update_id} atualizado para {novo_status}")
                    else:
                        st.warning("⚠️ Não foi possível atualizar o pneu")
                except Exception as e:
                    st.error(f"❌ Erro: {str(e)}")
            else:
                st.warning("⚠️ Digite o ID do pneu")
    
    with tab3:
        st.subheader("Alertas do Sistema")
        try:
            alertas = listar_alertas_ativos()
            if alertas and len(alertas) > 0:
                df_alertas = pd.DataFrame(alertas)
                st.dataframe(df_alertas, use_container_width=True)
                
                # Download CSV
                csv = df_alertas.to_csv(index=False)
                st.download_button(
                    label="📥 Baixar CSV",
                    data=csv,
                    file_name=f"alertas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("✅ Nenhum alerta no momento")
        except Exception as e:
            st.warning(f"⚠️ Erro ao listar alertas: {str(e)}")

def gestao_clientes_page():
    """Client management page (Admin only)"""
    if st.session_state.user_role != "Admin":
        st.warning("⚠️ Esta página é apenas para Administradores")
        return
    
    st.title("👥 Gestão de Clientes")
    
    try:
        clientes = get_todos_clientes()
        
        if clientes and len(clientes) > 0:
            # Select client
            opcoes_clientes = [f"{c['nome_empresa']} ({c['nome_fantasia']})" for c in clientes]
            cliente_selecionado_str = st.selectbox("Selecione um Cliente", opcoes_clientes)
            
            # Get selected client
            cliente_idx = opcoes_clientes.index(cliente_selecionado_str)
            cliente = clientes[cliente_idx]
            
            st.divider()
            
            # Display client details
            st.subheader(f"📋 {cliente['nome_empresa']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Nome da Empresa", cliente['nome_empresa'])
                st.metric("Nome Responsável", cliente.get('nome_responsavel', 'N/A'))
            with col2:
                st.metric("Nome Fantasia", cliente['nome_fantasia'])
                st.metric("Contato", cliente.get('contato_responsavel', 'N/A'))
            
            st.divider()
            
            # Edit client
            st.subheader("✏️ Editar Informações")
            
            with st.form("edit_cliente_form"):
                nome_empresa = st.text_input("Nome da Empresa", value=cliente['nome_empresa'])
                nome_fantasia = st.text_input("Nome Fantasia", value=cliente['nome_fantasia'])
                responsavel = st.text_input("Responsável", value=cliente.get('nome_responsavel', ''))
                contato = st.text_input("Contato", value=cliente.get('contato_responsavel', ''))
                
                if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                    try:
                        resultado = atualizar_dados_cliente(
                            cliente['id'],
                            {
                                'nome_empresa': nome_empresa,
                                'nome_fantasia': nome_fantasia,
                                'nome_responsavel': responsavel,
                                'contato_responsavel': contato
                            }
                        )
                        if resultado:
                            st.success("✅ Cliente atualizado com sucesso!")
                        else:
                            st.warning("⚠️ Erro ao atualizar cliente")
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
        else:
            st.info("ℹ️ Nenhum cliente cadastrado")
    
    except Exception as e:
        st.error(f"❌ Erro ao carregar clientes: {str(e)}")

def relatorios_page():
    """Reports page"""
    st.title("📊 Relatórios")
    
    st.info("📋 Seção de relatórios em desenvolvimento")
    
    tab1, tab2, tab3 = st.tabs(["Pneus", "Alertas", "Movimentações"])
    
    with tab1:
        st.subheader("Relatório de Pneus")
        st.write("Selecione filtros:")
        
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Status", ["Todos", "NOVO", "BOM", "ALERTA", "DESCARTADO"])
        with col2:
            marca_filter = st.text_input("Marca (opcional)")
        
        st.info("Click em 'Gerar Relatório' para ver os dados")
    
    with tab2:
        st.subheader("Relatório de Alertas")
        st.write("Alertas por tipo e severidade")
        
        col1, col2 = st.columns(2)
        with col1:
            tipo_alerta = st.selectbox("Tipo de Alerta", ["Todos", "Desgaste", "Tempo", "Manutenção"])
        with col2:
            severidade = st.selectbox("Severidade", ["Todos", "CRITICO", "ALTO", "MEDIO", "BAIXO"])
    
    with tab3:
        st.subheader("Relatório de Movimentações")
        st.write("Histórico de movimentações de pneus")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application"""
    init_session()
    
    if not st.session_state.logged_in:
        login_page()
    else:
        # Sidebar navigation
        with st.sidebar:
            st.title(f"👤 {st.session_state.user_role}")
            st.divider()
            
            selected = st.radio(
                "Menu",
                [
                    "🏠 Home",
                    "🛞 Gestão de Pneus",
                    "👥 Gestão de Clientes",
                    "📊 Relatórios",
                ]
            )
            
            st.divider()
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user_role = None
                st.session_state.cliente_id = None
                st.rerun()
        
        # Route to selected page
        if selected == "🏠 Home":
            home_page()
        elif selected == "🛞 Gestão de Pneus":
            gestao_pneus_page()
        elif selected == "👥 Gestão de Clientes":
            gestao_clientes_page()
        elif selected == "📊 Relatórios":
            relatorios_page()

if __name__ == "__main__":
    main()
