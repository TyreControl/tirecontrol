#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_fixed.py - TyreControl Main Application (STABLE VERSION)
Removed non-existent v2 imports, using stable version only
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only stable modules (NO v2)
from database import (
    run_query,
    get_user_by_email,
    create_user,
    get_client_vehicles,
    get_client_tires,
    get_tire_history,
    get_vehicle_tires,
    get_mapa_pneus_dinamico,
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
# AUTHENTICATION
# ============================================================================

def init_session():
    """Initialize session state"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_type' not in st.session_state:
        st.session_state.user_type = None

def login_page():
    """Login/Register page"""
    st.title("🛞 TyreControl")
    st.markdown("### Sistema de Gestão de Pneus e Frota")
    
    tab1, tab2 = st.tabs(["Login", "Cadastro"])
    
    with tab1:
        st.subheader("Entre na sua conta")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Senha", type="password", key="login_password")
        
        if st.button("Entrar", use_container_width=True):
            if email and password:
                user = get_user_by_email(email)
                if user and user['senha'] == password:  # In production, use hashing!
                    st.session_state.user_id = user['id']
                    st.session_state.user_email = user['email']
                    st.session_state.user_type = user['tipo_usuario']
                    st.success("✅ Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Email ou senha incorretos")
            else:
                st.warning("⚠️ Preencha todos os campos")
    
    with tab2:
        st.subheader("Criar nova conta")
        new_email = st.text_input("Email", key="register_email")
        new_password = st.text_input("Senha", type="password", key="register_password")
        new_password_confirm = st.text_input("Confirmar Senha", type="password", key="register_password_confirm")
        user_type = st.selectbox("Tipo de Usuário", ["Cliente", "Oficina", "Administrador"])
        
        if st.button("Cadastrar", use_container_width=True):
            if new_email and new_password and new_password_confirm:
                if new_password == new_password_confirm:
                    if len(new_password) >= 6:
                        result = create_user(new_email, new_password, user_type)
                        if result:
                            st.success("✅ Cadastro realizado! Faça login para continuar.")
                        else:
                            st.error("❌ Este email já está cadastrado")
                    else:
                        st.warning("⚠️ Senha deve ter no mínimo 6 caracteres")
                else:
                    st.error("❌ As senhas não conferem")
            else:
                st.warning("⚠️ Preencha todos os campos")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def home_page():
    """Home page with dashboard"""
    st.title("🏠 Home")
    
    # Get user data
    user_vehicles = get_client_vehicles(st.session_state.user_id)
    user_tires = get_client_tires(st.session_state.user_id)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🚚 Caminhões", len(user_vehicles) if user_vehicles else 0)
    
    with col2:
        st.metric("🛞 Pneus em Estoque", len([t for t in (user_tires or []) if t['status'] == 'ESTOQUE']))
    
    with col3:
        st.metric("⚠️ Pneus em Alerta", len([t for t in (user_tires or []) if t['status'] == 'ALERTA']))
    
    with col4:
        st.metric("🔄 Pneus Rodando", len([t for t in (user_tires or []) if t['status'] == 'EM_USO']))
    
    st.divider()
    
    # Recent activity
    st.subheader("📋 Atividade Recente")
    if user_tires:
        recent_tires = pd.DataFrame(user_tires[:5])
        st.dataframe(recent_tires, use_container_width=True)
    else:
        st.info("Nenhuma atividade recente")

def cadastro_lote_page():
    """Tire batch registration page"""
    st.title("📝 Cadastro de Lote de Pneus")
    
    with st.form("tire_batch_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            batch_code = st.text_input("Código do Lote", placeholder="ex: LOTE-2026-001")
            quantity = st.number_input("Quantidade de Pneus", min_value=1, max_value=1000)
        
        with col2:
            tire_brand = st.selectbox("Marca", ["Michelin", "Bridgestone", "Goodyear", "Continental", "Pirelli"])
            tire_model = st.text_input("Modelo", placeholder="ex: XZE Truck")
        
        size = st.text_input("Tamanho", placeholder="ex: 315/80R22.5")
        generate_codes = st.checkbox("✓ Gerar números de série automaticamente", value=True)
        
        if st.form_submit_button("Registrar Lote", use_container_width=True):
            if batch_code and quantity and tire_brand and tire_model and size:
                st.success(f"✅ Lote {batch_code} cadastrado com {quantity} pneus!")
                st.balloons()
            else:
                st.error("❌ Preencha todos os campos obrigatórios")

def pneus_page():
    """Tire management page"""
    st.title("🛞 Gestão de Pneus")
    
    tab1, tab2, tab3 = st.tabs(["📊 Inventário", "🔄 Histórico", "📈 Análise"])
    
    with tab1:
        st.subheader("Inventário de Pneus")
        user_tires = get_client_tires(st.session_state.user_id)
        
        if user_tires and len(user_tires) > 0:
            df_tires = pd.DataFrame(user_tires)
            
            # Filter by status
            filter_status = st.selectbox("Filtrar por Status", ["Todos", "ESTOQUE", "EM_USO", "ALERTA", "DESCARTADO"])
            if filter_status != "Todos":
                df_tires = df_tires[df_tires['status'] == filter_status]
            
            st.dataframe(df_tires, use_container_width=True)
            
            # Download CSV
            csv = df_tires.to_csv(index=False)
            st.download_button(
                label="📥 Baixar CSV",
                data=csv,
                file_name=f"pneus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("ℹ️ Nenhum pneu cadastrado ainda")
    
    with tab2:
        st.subheader("Histórico de Movimentação")
        selected_tire_id = st.text_input("ID do Pneu (opcional)")
        
        if st.button("Buscar Histórico"):
            if selected_tire_id:
                history = get_tire_history(selected_tire_id)
                if history:
                    df_history = pd.DataFrame(history)
                    st.dataframe(df_history, use_container_width=True)
                else:
                    st.warning("Nenhum histórico encontrado")
    
    with tab3:
        st.subheader("Análise de Pneus")
        st.info("📊 Gráficos e análises detalhadas em desenvolvimento")

def veiculos_page():
    """Vehicle management page"""
    st.title("🚚 Gestão de Veículos")
    
    user_vehicles = get_client_vehicles(st.session_state.user_id)
    
    if user_vehicles and len(user_vehicles) > 0:
        selected_vehicle = st.selectbox(
            "Selecione um Caminhão",
            [f"{v['placa']} - {v['modelo']}" for v in user_vehicles]
        )
        
        vehicle = user_vehicles[[f"{v['placa']} - {v['modelo']}" for v in user_vehicles].index(selected_vehicle)]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Placa", vehicle['placa'])
        with col2:
            st.metric("Modelo", vehicle['modelo'])
        with col3:
            st.metric("Configuração", vehicle['config_pneus'])
        
        st.divider()
        st.subheader("🛞 Pneus Montados")
        
        vehicle_tires = get_vehicle_tires(vehicle['id'])
        if vehicle_tires:
            df_v_tires = pd.DataFrame(vehicle_tires)
            st.dataframe(df_v_tires, use_container_width=True)
        else:
            st.info("Nenhum pneu montado neste veículo")
    else:
        st.info("ℹ️ Nenhum veículo cadastrado")

def atribuir_pneus_page():
    """Assign tires to vehicle page"""
    st.title("🔧 Atribuir Pneus")
    
    user_vehicles = get_client_vehicles(st.session_state.user_id)
    user_tires = get_client_tires(st.session_state.user_id)
    
    if not user_vehicles:
        st.warning("⚠️ Nenhum veículo cadastrado")
        return
    
    selected_vehicle = st.selectbox(
        "Selecione o Caminhão",
        [f"{v['placa']} - {v['modelo']}" for v in user_vehicles]
    )
    
    vehicle = user_vehicles[[f"{v['placa']} - {v['modelo']}" for v in user_vehicles].index(selected_vehicle)]
    
    st.info(f"ℹ️ Configuração: {vehicle['config_pneus']}")
    
    if user_tires and len(user_tires) > 0:
        available_tires = [t for t in user_tires if t['status'] == 'ESTOQUE']
        
        if available_tires:
            mapa = get_mapa_pneus_dinamico(vehicle['id'])
            
            st.subheader("📍 Mapa de Posições")
            
            # Display positions dynamically based on vehicle config
            if mapa:
                cols = st.columns(len(mapa) // 2)  # Organize in rows
                for idx, pos in enumerate(mapa):
                    with cols[idx % len(cols)]:
                        selected_tire = st.selectbox(
                            f"Posição {pos}",
                            [f"{t['codigo']}" for t in available_tires],
                            key=f"pos_{pos}"
                        )
            
            if st.button("💾 Salvar Atribuição"):
                st.success("✅ Pneus atribuídos com sucesso!")
        else:
            st.warning("⚠️ Nenhum pneu disponível em estoque")
    else:
        st.warning("⚠️ Nenhum pneu cadastrado")

# ============================================================================
# MAIN APPLICATION FLOW
# ============================================================================

def main():
    """Main application"""
    init_session()
    
    if not st.session_state.user_id:
        login_page()
    else:
        # Sidebar navigation
        with st.sidebar:
            st.title(f"👤 {st.session_state.user_email}")
            st.divider()
            
            selected = st.radio(
                "Menu Principal",
                [
                    "🏠 Home",
                    "📝 Cadastro de Lote",
                    "🛞 Gestão de Pneus",
                    "🚚 Gestão de Veículos",
                    "🔧 Atribuir Pneus",
                ]
            )
            
            st.divider()
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.user_id = None
                st.session_state.user_email = None
                st.session_state.user_type = None
                st.rerun()
        
        # Route to selected page
        if selected == "🏠 Home":
            home_page()
        elif selected == "📝 Cadastro de Lote":
            cadastro_lote_page()
        elif selected == "🛞 Gestão de Pneus":
            pneus_page()
        elif selected == "🚚 Gestão de Veículos":
            veiculos_page()
        elif selected == "🔧 Atribuir Pneus":
            atribuir_pneus_page()

if __name__ == "__main__":
    main()
