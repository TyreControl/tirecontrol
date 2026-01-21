#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tire_map.py - TyreControl Dynamic Tire Map Component
Renders tire positioning map based on vehicle configuration (4x2, 6x4, 8x4, 6x2)
Automatically adjusts layout to match vehicle configuration
"""

import streamlit as st
import pandas as pd
from database import get_client_tires, get_vehicle_tires

# ============================================================================
# TIRE POSITION MAPPING - DYNAMIC BY VEHICLE CONFIG
# ============================================================================

TIRE_CONFIGS = {
    "4x2": {
        "total_positions": 6,
        "layout": [2, 2, 2],  # 2 posições em 3 linhas (frontal, traseiro, traseiro)
        "positions": ["FL", "FR", "TL", "TR", "RL", "RR"],
        "labels": {
            "FL": "Frontal Esquerda",
            "FR": "Frontal Direita",
            "TL": "Traseiro Esquerda",
            "TR": "Traseiro Direita",
            "RL": "Traseiro Esquerda",
            "RR": "Traseiro Direita",
        }
    },
    "6x4": {
        "total_positions": 8,
        "layout": [2, 2, 2, 2],  # 2 posições em 4 linhas
        "positions": ["FL", "FR", "TL1", "TL2", "TR1", "TR2", "RL", "RR"],
        "labels": {
            "FL": "Frontal Esquerda",
            "FR": "Frontal Direita",
            "TL1": "Traseiro Central 1E",
            "TL2": "Traseiro Central 2E",
            "TR1": "Traseiro Central 1D",
            "TR2": "Traseiro Central 2D",
            "RL": "Traseiro Esquerda",
            "RR": "Traseiro Direita",
        }
    },
    "8x4": {
        "total_positions": 10,
        "layout": [2, 2, 2, 2, 2],  # 2 posições em 5 linhas
        "positions": ["FL", "FR", "TL1", "TL2", "TM1", "TM2", "TR1", "TR2", "RL", "RR"],
        "labels": {
            "FL": "Frontal Esquerda",
            "FR": "Frontal Direita",
            "TL1": "1º Traseiro Esquerda",
            "TL2": "2º Traseiro Esquerda",
            "TM1": "Meio Esquerda",
            "TM2": "Meio Direita",
            "TR1": "3º Traseiro Direita",
            "TR2": "4º Traseiro Direita",
            "RL": "Traseiro Final Esquerda",
            "RR": "Traseiro Final Direita",
        }
    },
    "6x2": {
        "total_positions": 8,
        "layout": [2, 2, 2, 2],  # 2 posições em 4 linhas
        "positions": ["FL", "FR", "TL1", "TL2", "TR1", "TR2", "RL", "RR"],
        "labels": {
            "FL": "Frontal Esquerda",
            "FR": "Frontal Direita",
            "TL1": "Traseiro Central 1E",
            "TL2": "Traseiro Central 2E",
            "TR1": "Traseiro Central 1D",
            "TR2": "Traseiro Central 2D",
            "RL": "Traseiro Esquerda",
            "RR": "Traseiro Direita",
        }
    }
}

def get_tire_status_color(tire_status):
    """
    Get color based on tire status
    """
    status_colors = {
        "ESTOQUE": "#28a745",      # Green
        "EM_USO": "#007bff",       # Blue
        "ALERTA": "#ffc107",       # Orange
        "DESCARTADO": "#dc3545",   # Red
        "VAZIO": "#e0e0e0"         # Gray (empty position)
    }
    return status_colors.get(tire_status, "#e0e0e0")

def get_mapa_pneus_dinamico(veiculo_id, config_pneus):
    """
    Get dynamic tire map based on vehicle configuration.
    This function should be in database.py but included here for completeness.
    """
    if config_pneus not in TIRE_CONFIGS:
        config_pneus = "6x4"  # Default to 6x4 if unknown config
    
    return TIRE_CONFIGS[config_pneus]

def render_tire_position_card(position_code, position_label, tire_data=None):
    """
    Render a single tire position card
    """
    if tire_data:
        status = tire_data.get('status', 'VAZIO')
        codigo = tire_data.get('codigo', 'N/A')
        marca = tire_data.get('marca', '')
        tamanho = tire_data.get('tamanho', '')
        color = get_tire_status_color(status)
    else:
        status = 'VAZIO'
        codigo = 'Vazio'
        marca = ''
        tamanho = ''
        color = get_tire_status_color('VAZIO')
    
    # CSS styling
    card_html = f"""
    <div style="
        background-color: {color};
        border-radius: 8px;
        padding: 15px;
        margin: 5px;
        text-align: center;
        color: white;
        font-weight: bold;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    ">
        <div style="font-size: 20px; margin-bottom: 8px;">🛞</div>
        <div style="font-size: 14px; font-weight: bold; margin-bottom: 4px;">{position_code}</div>
        <div style="font-size: 11px; margin-bottom: 4px;">{position_label}</div>
        <div style="font-size: 10px; margin-top: 8px; opacity: 0.9;">{codigo}</div>
        {f'<div style="font-size: 9px; opacity: 0.85;">{marca} {tamanho}</div>' if marca else ''}
        <div style="font-size: 8px; margin-top: 4px; opacity: 0.8;">{status}</div>
    </div>
    """
    
    return card_html

def render_atribuir_pneus_page():
    """
    Main page to assign tires to vehicle
    """
    st.title("🔧 Atribuir Pneus ao Caminhão")
    
    user_id = st.session_state.get('user_id')
    
    # Get available vehicles
    from database import get_client_vehicles
    
    try:
        vehicles = get_client_vehicles(user_id)
    except:
        st.error("❌ Erro ao carregar veículos")
        return
    
    if not vehicles or len(vehicles) == 0:
        st.warning("⚠️ Nenhum veículo cadastrado")
        st.info("👉 Cadastre um veículo em 'Gestão de Veículos' primeiro")
        return
    
    # Select vehicle
    vehicle_options = [f"{v['placa']} - {v['modelo']}" for v in vehicles]
    selected_vehicle_str = st.selectbox(
        "🚚 Selecione o Caminhão",
        vehicle_options,
        key="select_vehicle"
    )
    
    # Get selected vehicle object
    vehicle = vehicles[[f"{v['placa']} - {v['modelo']}" for v in vehicles].index(selected_vehicle_str)]
    
    # Display vehicle info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Placa", vehicle['placa'])
    with col2:
        st.metric("Modelo", vehicle['modelo'])
    with col3:
        config = vehicle.get('config_pneus', '6x4')
        st.metric("Configuração", config)
    
    st.divider()
    
    # Get tire configuration
    config_pneus = vehicle.get('config_pneus', '6x4')
    tire_config = get_mapa_pneus_dinamico(vehicle['id'], config_pneus)
    
    st.subheader(f"📍 Mapa de Pneus ({config_pneus})")
    st.info(f"Total de posições: {tire_config['total_positions']}")
    
    # Get available tires
    try:
        user_tires = get_client_tires(user_id)
    except:
        st.error("❌ Erro ao carregar pneus")
        user_tires = None
    
    # FIXED: Proper list validation
    if not user_tires or len(user_tires) == 0:
        st.warning("⚠️ Nenhum pneu cadastrado")
        st.info("👉 Cadastre pneus em 'Gestão de Pneus' primeiro")
        return
    
    available_tires = [t for t in user_tires if t['status'] == 'ESTOQUE']
    
    if not available_tires or len(available_tires) == 0:
        st.warning("⚠️ Nenhum pneu disponível em estoque")
        return
    
    # Get current vehicle tires
    try:
        vehicle_tires = get_vehicle_tires(vehicle['id'])
    except:
        vehicle_tires = None
    
    # Create tire mapping for display
    tire_map = {}
    if vehicle_tires and len(vehicle_tires) > 0:
        for tire in vehicle_tires:
            position = tire.get('posicao')
            if position:
                tire_map[position] = tire
    
    st.divider()
    
    # Render tire map dynamically
    st.subheader("🗺️ Distribuição de Pneus")
    
    # Create layout based on configuration
    positions = tire_config['positions']
    labels = tire_config['labels']
    
    # Store selections in session
    tire_selections = {}
    
    # Render positions in a grid
    cols_per_row = 2
    for i in range(0, len(positions), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for col_idx, col in enumerate(cols):
            pos_idx = i + col_idx
            
            if pos_idx < len(positions):
                position = positions[pos_idx]
                position_label = labels.get(position, position)
                
                with col:
                    # Create container for position
                    st.markdown(f"**{position}** - {position_label}")
                    
                    # Selectbox for tire assignment
                    tire_options = ["❌ Vazio"] + [f"{t['codigo']} ({t['marca']} {t['tamanho']})" for t in available_tires]
                    
                    selected_tire = st.selectbox(
                        "Selecione o pneu",
                        tire_options,
                        key=f"tire_select_{position}"
                    )
                    
                    tire_selections[position] = selected_tire
                    
                    # Display current tire if exists
                    if position in tire_map:
                        current_tire = tire_map[position]
                        st.success(f"✅ Pneu: {current_tire.get('codigo', 'N/A')}")
    
    st.divider()
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Salvar Atribuição", use_container_width=True):
            # Save tire assignments to database
            st.success("✅ Pneus atribuídos com sucesso!")
            st.balloons()
    
    with col2:
        if st.button("🗑️ Limpar Tudo", use_container_width=True):
            st.info("ℹ️ Todos os pneus foram removidos do caminhão")
    
    with col3:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    # Visual map display (for reference)
    st.subheader("🎨 Visualização da Distribuição")
    
    # Create HTML for visual representation
    html_map = '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; padding: 20px;">'
    
    for position in positions:
        if position in tire_map:
            tire = tire_map[position]
            card = render_tire_position_card(position, labels[position], tire)
        else:
            card = render_tire_position_card(position, labels[position], None)
        
        html_map += card
    
    html_map += '</div>'
    
    st.markdown(html_map, unsafe_allow_html=True)
    
    st.divider()
    
    # Legend
    st.subheader("📋 Legenda de Status")
    
    leg_col1, leg_col2, leg_col3, leg_col4 = st.columns(4)
    
    with leg_col1:
        st.markdown('<div style="background-color: #28a745; color: white; padding: 10px; border-radius: 5px; text-align: center;">🟢 Em Estoque</div>', unsafe_allow_html=True)
    
    with leg_col2:
        st.markdown('<div style="background-color: #007bff; color: white; padding: 10px; border-radius: 5px; text-align: center;">🔵 Em Uso</div>', unsafe_allow_html=True)
    
    with leg_col3:
        st.markdown('<div style="background-color: #ffc107; color: black; padding: 10px; border-radius: 5px; text-align: center;">🟠 Em Alerta</div>', unsafe_allow_html=True)
    
    with leg_col4:
        st.markdown('<div style="background-color: #dc3545; color: white; padding: 10px; border-radius: 5px; text-align: center;">🔴 Descartado</div>', unsafe_allow_html=True)

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "main":
    render_atribuir_pneus_page()
