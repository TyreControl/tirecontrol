import streamlit as st
import pandas as pd
from database import run_query
from datetime import date

def render_pneus():
    st.title("🏭 Gestão de Ativos e Estoque")
    
    user_id = st.session_state['user_id']
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user: return
    cliente_id = dados_user[0]['cliente_id']

    tab_novo, tab_recap, tab_estoque = st.tabs(["📦 Entrada Nota Fiscal", "♻️ Fluxo de Recapagem", "📊 Inventário Geral"])

    # --- ENTRADA DE NOTA (NOVOS) ---
    with tab_novo:
        st.subheader("Cadastro de Pneus Novos")
        with st.form("entrada_nota"):
            c1, c2, c3 = st.columns(3)
            nf = c1.text_input("Nota Fiscal")
            fornecedor = c2.text_input("Fornecedor")
            data_nf = c3.date_input("Data Compra", value=date.today())
            
            st.divider()
            
            c4, c5, c6 = st.columns(3)
            marca = c4.selectbox("Marca", ["Michelin", "Bridgestone", "Goodyear", "Pirelli", "Continental", "Outra"])
            medida = c5.selectbox("Medida", ["295/80R22.5", "275/80R22.5", "11.00R22", "12R22.5"])
            modelo = c6.text_input("Modelo (Ex: X Multi Z)")
            
            c7, c8 = st.columns(2)
            custo = c7.number_input("Custo Unitário (R$)", min_value=0.0, step=10.0)
            qtd = c8.number_input("Quantidade", min_value=1, step=1)
            
            st.markdown("##### Identificação (Marcas de Fogo)")
            fogos_text = st.text_area(f"Digite os {qtd} códigos de fogo (um por linha):", height=150)
            
            if st.form_submit_button("Processar Entrada"):
                lista_fogos = [x.strip().upper() for x in fogos_text.split('\n') if x.strip()]
                
                if len(lista_fogos) != qtd:
                    st.error(f"Quantidade divergente! Você informou {qtd} pneus, mas digitou {len(lista_fogos)} códigos.")
                else:
                    sucesso = True
                    for fogo in lista_fogos:
                        try:
                            run_query("""
                                INSERT INTO pneus (cliente_id, marca_fogo, marca, modelo, medida, status, ciclo_atual, km_vida_total, custo_aquisicao, n_nota_fiscal, fornecedor, data_compra)
                                VALUES (%s, %s, %s, %s, %s, 'ESTOQUE', 0, 0, %s, %s, %s, %s)
                            """, (cliente_id, fogo, marca, modelo, medida, custo, nf, fornecedor, data_nf))
                        except Exception as e:
                            st.error(f"Erro ao inserir {fogo}: {e}")
                            sucesso = False
                    
                    if sucesso:
                        st.success(f"{qtd} Pneus cadastrados no estoque com sucesso!")

    # --- FLUXO RECAPAGEM ---
    with tab_recap:
        col_envio, col_retorno = st.columns(2)
        
        # COLUNA 1: ENVIAR PARA RECAPADORA
        with col_envio:
            st.subheader("📤 Enviar Carcaça")
            # Lista pneus marcados como RECAPAGEM ou SUCATA que ainda não "foram" processados
            # Simplificando: Pneus com status 'RECAPAGEM'
            pneus_recap = run_query("SELECT id, marca_fogo, marca FROM pneus WHERE cliente_id = %s AND status = 'RECAPAGEM'", (cliente_id,))
            
            if pneus_recap:
                with st.form("enviar_recap"):
                    pneu_sel = st.selectbox("Selecione a Carcaça", [f"{p['marca_fogo']} - {p['marca']}" for p in pneus_recap])
                    recapadora = st.text_input("Nome da Recapadora")
                    os = st.text_input("Número da OS/Coleta")
                    
                    if st.form_submit_button("Registrar Coleta"):
                        # Num sistema completo, mudaria status para 'EM_RECAPAGEM'
                        st.success(f"Pneu enviado para {recapadora} (OS: {os})")
            else:
                st.info("Nenhuma carcaça aguardando envio.")

        # COLUNA 2: RECEBER PRONTO
        with col_retorno:
            st.subheader("📥 Receber Pronto")
            # Assume que os mesmos pneus da lista anterior podem voltar (fluxo simplificado para MVP)
            if pneus_recap:
                with st.form("retorno_recap"):
                    pneu_chegada = st.selectbox("Pneu Retornando", [f"{p['marca_fogo']}" for p in pneus_recap])
                    custo_servico = st.number_input("Custo do Serviço (R$)", min_value=0.0)
                    banda = st.text_input("Nova Banda Aplicada")
                    
                    if st.form_submit_button("Dar Entrada no Estoque"):
                        # Aumenta Ciclo de Vida e Volta pro Estoque
                        marca_fogo_alvo = pneu_chegada
                        pneu_id = next(p['id'] for p in pneus_recap if p['marca_fogo'] == marca_fogo_alvo)
                        
                        run_query("""
                            UPDATE pneus 
                            SET status='ESTOQUE', ciclo_atual = ciclo_atual + 1, modelo = %s 
                            WHERE id = %s
                        """, (f"Recap {banda}", pneu_id))
                        
                        st.success("Pneu renovado e disponível no estoque!")
                        st.rerun()

    # --- INVENTÁRIO ---
    with tab_estoque:
        st.subheader("Posição Geral de Ativos")
        filtro = st.multiselect("Filtrar Status", ["ESTOQUE", "MONTADO", "RECAPAGEM", "SUCATA"], default=["ESTOQUE", "RECAPAGEM"])
        
        if filtro:
            # Construção dinâmica da query para o IN
            placeholders = ', '.join(['%s'] * len(filtro))
            query = f"""
                SELECT marca_fogo, marca, medida, status, ciclo_atual, posicao_atual, custo_aquisicao 
                FROM pneus WHERE cliente_id = %s AND status IN ({placeholders})
            """
            params = [cliente_id] + filtro
            dados = run_query(query, tuple(params))
            
            if dados:
                df = pd.DataFrame(dados)
                st.dataframe(df, use_container_width=True)
                st.metric("Total de Pneus Listados", len(df))