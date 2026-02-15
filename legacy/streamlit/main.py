import streamlit as st

import login
from acoes_operacionais import (
    ACOES_POR_ROLE,
    ACOES_LABEL,
    render_pagina_gestao,
    render_pagina_operacao,
)
from database import get_todos_clientes, get_detalhes_cliente
from fluxo_cadastro_inicial import render_cadastro_inicial
import frota

st.set_page_config(
    page_title="Tyre Control - Operacao por Acoes",
    page_icon="TC",
    layout="wide",
)

try:
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except Exception:
    pass

if not st.session_state.get("logged_in"):
    login.render_login_page()
    st.stop()

with st.sidebar:
    st.title("Tyre Control")

    user_role = st.session_state.get("user_role", "operador")
    role_key_sidebar = str(user_role).strip().lower()

    if role_key_sidebar == "admin":
        st.markdown("### Modo Administrador")
        clientes_db = get_todos_clientes()

        if clientes_db:
            opcoes_clientes = {c["nome_empresa"]: c["id"] for c in clientes_db}
            index_atual = 0
            current_id = st.session_state.get("cliente_id")
            ids_list = list(opcoes_clientes.values())
            if current_id in ids_list:
                index_atual = ids_list.index(current_id)

            nome_selecionado = st.selectbox(
                "Acessar cliente",
                list(opcoes_clientes.keys()),
                index=index_atual,
            )

            novo_id = opcoes_clientes[nome_selecionado]
            if novo_id != st.session_state.get("cliente_id"):
                st.session_state["cliente_id"] = novo_id
                st.rerun()
        else:
            st.error("Nenhum cliente cadastrado")
    else:
        c_id = st.session_state.get("cliente_id")
        if c_id:
            info = get_detalhes_cliente(c_id)
            nome_exibir = info["nome_fantasia"] if info and info.get("nome_fantasia") else "Minha Empresa"
            st.markdown(f"### {nome_exibir}")
        else:
            st.error("Usuario sem empresa vinculada")

    st.divider()
    st.write(f"Gestor: **{st.session_state.get('user_name')}**")

    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()

if not st.session_state.get("cliente_id"):
    st.warning("Selecione um cliente para comecar")
    st.stop()

role_key = str(st.session_state.get("user_role", "operador")).lower()
acoes_permitidas = ACOES_POR_ROLE.get(role_key, ACOES_POR_ROLE["operador"])

menu_map = {}
for acao in ["escanear", "tirar", "colocar", "trocar", "recapagem"]:
    if acao in acoes_permitidas:
        menu_map[f"Borracharia - {ACOES_LABEL[acao]}"] = ("operacao", acao)

if "frota" in acoes_permitidas or role_key in ["admin", "gerente"]:
    menu_map["Controle de Frota"] = ("frota", None)

if role_key in ["admin", "gerente"]:
    menu_map["Painel da Gestao"] = ("gestao", None)
if role_key in ["admin", "gerente", "borracheiro"]:
    menu_map["Cadastro Inicial"] = ("cadastro", None)

if not menu_map:
    st.error("Seu perfil nao possui telas liberadas.")
    st.stop()

tela = st.sidebar.radio("Telas", list(menu_map.keys()), key="tela_ativa")
tipo_tela, acao_tela = menu_map[tela]

if tipo_tela == "operacao":
    render_pagina_operacao(acao_tela)
elif tipo_tela == "frota":
    st.title("Controle de Frota")
    frota.render_frota()
elif tipo_tela == "gestao":
    render_pagina_gestao()
elif tipo_tela == "cadastro":
    render_cadastro_inicial()
