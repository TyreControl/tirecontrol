import streamlit as st
from streamlit_option_menu import option_menu
import login
import frota
import pneus
import movimentacoes

st.set_page_config(page_title="Tyre Control - Gestão Profissional", page_icon="🚚", layout="wide")

# CSS
try:
    with open('style.css') as f: st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except: pass

if not st.session_state.get('logged_in'):
    login.render_login_page()
    st.stop()

with st.sidebar:
    st.title("Tyre Control 🚚")
    st.write(f"Gestor: **{st.session_state.get('user_name')}**")
    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()

selected = option_menu(
    menu_title=None,
    options=["Minha Frota", "Oficina Central", "Gestão de Ativos"],
    icons=["truck", "tools", "archive"],
    default_index=0,
    orientation="horizontal",
)

if selected == "Minha Frota":
    frota.render_frota()
elif selected == "Oficina Central":
    movimentacoes.render_movimentacoes()
elif selected == "Gestão de Ativos":
    pneus.render_pneus()