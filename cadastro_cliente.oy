import streamlit as st
from database import get_detalhes_cliente, atualizar_dados_cliente

def render_cadastro_cliente():
    st.title("🏢 Dados da Empresa")
    
    cliente_id = st.session_state.get('cliente_id')
    if not cliente_id:
        st.error("Nenhum cliente selecionado.")
        return

    dados = get_detalhes_cliente(cliente_id)
    
    if not dados:
        st.error("Cliente não encontrado na base de dados.")
        return

    with st.form("form_dados_empresa"):
        st.subheader("Informações Cadastrais")
        
        c1, c2 = st.columns(2)
        nome_empresa = c1.text_input("Razão Social", value=dados['nome_empresa'])
        nome_fantasia = c2.text_input("Nome Fantasia", value=dados['nome_fantasia'] or "")
        
        st.divider()
        
        c3, c4 = st.columns(2)
        responsavel = c3.text_input("Nome do Responsável", value=dados['nome_responsavel'] or "")
        contato = c4.text_input("Telefone/WhatsApp", value=dados['contato_responsavel'] or "")
        
        if st.form_submit_button("💾 Salvar Alterações"):
            novos_dados = {
                'nome_empresa': nome_empresa,
                'nome_fantasia': nome_fantasia,
                'nome_responsavel': responsavel,
                'contato_responsavel': contato
            }
            
            if atualizar_dados_cliente(cliente_id, novos_dados):
                st.success("Dados atualizados com sucesso!")
                st.rerun()