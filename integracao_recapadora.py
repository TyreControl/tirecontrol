import streamlit as st
import pandas as pd
from database import run_query
from datetime import datetime

def criar_ordem_recapagem(recapadora_nome, usuario_id, cliente_id):
    """Cria uma nova ordem de recapagem"""
    try:
        ordem_id = f"REC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        query = """
        INSERT INTO ordens_recapagem 
        (ordem_id, recapadora_nome, status, data_criacao, usuario_responsavel, cliente_id)
        VALUES (%s, %s, 'enviado', %s, %s, %s)
        """
        
        params = (ordem_id, recapadora_nome, datetime.now(), usuario_id, cliente_id)
        
        return run_query(query, params), ordem_id
    except Exception as e:
        st.error(f"Erro ao criar ordem: {e}")
        return False, None

def adicionar_pneu_ordem(ordem_id, pneu_id):
    """Adiciona um pneu a uma ordem de recapagem"""
    try:
        query = """
        INSERT INTO ordens_recapagem_pneus (ordem_id, pneu_id, data_adicionada)
        VALUES (%s, %s, %s)
        """
        
        params = (ordem_id, pneu_id, datetime.now())
        
        return run_query(query, params)
    except Exception as e:
        st.error(f"Erro ao adicionar pneu à ordem: {e}")
        return False

def atualizar_status_ordem(ordem_id, novo_status):
    """Atualiza o status de uma ordem"""
    try:
        query = """
        UPDATE ordens_recapagem 
        SET status = %s, data_ultima_atualizacao = %s
        WHERE ordem_id = %s
        """
        
        params = (novo_status, datetime.now(), ordem_id)
        
        return run_query(query, params)
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
        return False

def obter_ordens(cliente_id, status=None):
    """Obtém ordens de recapagem do cliente"""
    try:
        if status:
            query = """
            SELECT * FROM ordens_recapagem
            WHERE cliente_id = %s AND status = %s
            ORDER BY data_criacao DESC
            """
            params = (cliente_id, status)
        else:
            query = """
            SELECT * FROM ordens_recapagem
            WHERE cliente_id = %s
            ORDER BY data_criacao DESC
            """
            params = (cliente_id,)
        
        return run_query(query, params)
    except Exception as e:
        st.error(f"Erro ao obter ordens: {e}")
        return []

def obter_pneus_ordem(ordem_id):
    """Obtém pneus de uma ordem específica"""
    try:
        query = """
        SELECT p.id, p.marca_fogo, p.marca, p.medida, p.ciclo_atual
        FROM pneus p
        INNER JOIN ordens_recapagem_pneus orp ON p.id = orp.pneu_id
        WHERE orp.ordem_id = %s
        """
        
        return run_query(query, (ordem_id,))
    except Exception as e:
        st.error(f"Erro ao obter pneus da ordem: {e}")
        return []

def render_integracao_recapadora():
    """Interface Streamlit para integração com recapadora"""
    st.title("🏭 Integração com Recapadora")
    
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
    
    # Tabs para operações
    tab1, tab2, tab3 = st.tabs(["Nova Ordem", "Ordens Ativas", "Histórico"])
    
    with tab1:
        st.subheader("📝 Criar Nova Ordem de Recapagem")
        
        with st.form("form_nova_ordem"):
            recapadora = st.selectbox(
                "Selecione a Recapadora",
                ["RecaPro", "RecaBrasil", "RecaFast", "Outra"]
            )
            
            if recapadora == "Outra":
                recapadora = st.text_input("Nome da Recapadora")
            
            # Buscar pneus disponíveis para recapagem
            query_pneus = """
            SELECT id, marca_fogo, marca, medida, ciclo_atual 
            FROM pneus 
            WHERE cliente_id = %s AND status = 'ESTOQUE'
            ORDER BY marca_fogo
            """
            
            pneus_disponveis = run_query(query_pneus, (cliente_id,))
            
            if not pneus_disponveis:
                st.warning("Nenhum pneu disponível para recapagem")
            else:
                opcoes_pneus = {
                    f"{p['marca_fogo']} - {p['marca']} {p['medida']}": p['id']
                    for p in pneus_disponveis
                }
                
                pneus_selecionados = st.multiselect(
                    "Selecione os pneus para recapagem",
                    opcoes_pneus.keys()
                )
                
                data_entrega = st.date_input(
                    "Data de entrega esperada",
                    help="Quando você espera ter os pneus de volta"
                )
                
                if st.form_submit_button("✓ Criar Ordem"):
                    if not recapadora:
                        st.error("Selecione uma recapadora")
                    elif not pneus_selecionados:
                        st.error("Selecione pelo menos um pneu")
                    else:
                        # Criar ordem
                        sucesso, ordem_id = criar_ordem_recapagem(
                            recapadora, usuario_id, cliente_id
                        )
                        
                        if sucesso and ordem_id:
                            # Adicionar pneus
                            for pneu_label in pneus_selecionados:
                                pneu_id = opcoes_pneus[pneu_label]
                                adicionar_pneu_ordem(ordem_id, pneu_id)
                                
                                # Atualizar status do pneu
                                query_update = """
                                UPDATE pneus 
                                SET status = 'RECAPAGEM' 
                                WHERE id = %s
                                """
                                run_query(query_update, (pneu_id,))
                            
                            # Atualizar data de entrega
                            query_data = """
                            UPDATE ordens_recapagem 
                            SET data_entrega_esperada = %s 
                            WHERE ordem_id = %s
                            """
                            run_query(query_data, (data_entrega, ordem_id))
                            
                            st.success(f"✓ Ordem criada: {ordem_id}")
                        else:
                            st.error("Erro ao criar ordem")
    
    with tab2:
        st.subheader("📦 Ordens Ativas")
        
        ordens_ativas = obter_ordens(cliente_id, status='enviado')
        ordens_ativas.extend(obter_ordens(cliente_id, status='em_processo') or [])
        
        if not ordens_ativas:
            st.info("Nenhuma ordem ativa")
        else:
            for ordem in ordens_ativas:
                with st.expander(
                    f"Ordem {ordem['ordem_id']} - {ordem['recapadora_nome']} ({ordem['status']})"
                ):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.caption("Recapadora")
                        st.write(ordem['recapadora_nome'])
                        
                        st.caption("Data de Criação")
                        st.write(ordem['data_criacao'])
                    
                    with col2:
                        st.caption("Status")
                        novo_status = st.selectbox(
                            "Atualizar Status",
                            ["enviado", "em_processo", "pronto", "entregue", "cancelado"],
                            index=["enviado", "em_processo", "pronto", "entregue", "cancelado"].index(ordem['status']),
                            key=f"status_{ordem['ordem_id']}"
                        )
                        
                        if novo_status != ordem['status']:
                            if st.button(f"Atualizar", key=f"update_{ordem['ordem_id']}"):
                                if atualizar_status_ordem(ordem['ordem_id'], novo_status):
                                    st.success("Status atualizado!")
                                    st.rerun()
                    
                    st.divider()
                    
                    st.caption("Pneus na Ordem")
                    pneus_ordem = obter_pneus_ordem(ordem['ordem_id'])
                    
                    if pneus_ordem:
                        df_pneus = pd.DataFrame([
                            {
                                'Marca de Fogo': p['marca_fogo'],
                                'Marca': p['marca'],
                                'Medida': p['medida'],
                                'Ciclo': p['ciclo_atual']
                            }
                            for p in pneus_ordem
                        ])
                        st.dataframe(df_pneus, use_container_width=True)
                    else:
                        st.warning("Nenhum pneu associado")
    
    with tab3:
        st.subheader("📊 Histórico de Ordens")
        
        todas_ordens = obter_ordens(cliente_id)
        
        if not todas_ordens:
            st.info("Nenhuma ordem no histórico")
        else:
            df_ordens = pd.DataFrame([
                {
                    'Ordem ID': o['ordem_id'],
                    'Recapadora': o['recapadora_nome'],
                    'Status': o['status'],
                    'Data Criação': o['data_criacao'],
                    'Data Entrega Esperada': o['data_entrega_esperada']
                }
                for o in todas_ordens
            ])
            
            st.dataframe(df_ordens, use_container_width=True)
