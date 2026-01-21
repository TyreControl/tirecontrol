"""
pneus.py - VERSÃO CORRIGIDA
Fixes:
  - Checkbox error ao cadastrar lote (linha ~97)
  - Validação de pneus vazios no dropdown
  - Interface melhorada
Corrigido: 2026-01-21
"""

import streamlit as st
import pandas as pd
from database import run_query
from datetime import date


def render_pneus():
    st.title("🏭 Gestão de Ativos e Estoque")
    
    user_id = st.session_state.get('user_id')
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    
    if not dados_user:
        st.error("Usuário não encontrado!")
        return
    
    cliente_id = dados_user[0]['cliente_id']
    
    tab_novo, tab_recap, tab_estoque = st.tabs(["📦 Entrada Nota Fiscal", "♻️ Fluxo de Recapagem", "📊 Inventário Geral"])
    
    # === TAB 1: ENTRADA DE NOTA (NOVOS PNEUS) ===
    with tab_novo:
        st.subheader("📦 Cadastro de Pneus Novos")
        
        with st.form("entrada_nota", clear_on_submit=True):
            # Linha 1: Nota Fiscal
            c1, c2, c3 = st.columns(3)
            nf = c1.text_input("Nota Fiscal", placeholder="ex: 1234")
            fornecedor = c2.text_input("Fornecedor", placeholder="ex: Michelin Brasil")
            data_nf = c3.date_input("Data Compra", value=date.today())
            
            st.divider()
            
            # Linha 2: Especificação
            c4, c5, c6 = st.columns(3)
            marca = c4.selectbox("Marca", ["Michelin", "Bridgestone", "Goodyear", "Pirelli", "Continental", "Outra"])
            medida = c5.selectbox("Medida", ["295/80R22.5", "275/80R22.5", "11.00R22", "12R22.5", "185/65R15", "195/60R15", "225/70R15", "235/75R17"])
            modelo = c6.text_input("Modelo", placeholder="ex: X Multi Z")
            
            # Linha 3: Quantidade e Custo
            c7, c8 = st.columns(2)
            custo = c7.number_input("Custo Unitário (R$)", min_value=0.0, step=10.0, value=0.0)
            qtd = c8.number_input("Quantidade", min_value=1, step=1, value=1)
            
            st.markdown("##### 🏷️ Identificação (Marcas de Fogo)")
            st.caption(f"Digite exatamente {int(qtd)} códigos (um por linha)")
            
            fogos_text = st.text_area(
                "Códigos de fogo:",
                placeholder="MIC001\nMIC002\nMIC003\n...",
                height=150
            )
            
            # ✅ FIX: Checkbox error - usar checkbox corretamente
            gerar_lote = st.checkbox("✓ Gerar número de lote automaticamente")
            
            if st.form_submit_button("✅ Processar Entrada", use_container_width=True):
                # Validar
                if not nf or not fornecedor or not modelo:
                    st.error("❌ Preencha todos os campos obrigatórios!")
                else:
                    lista_fogos = [x.strip().upper() for x in fogos_text.split('\n') if x.strip()]
                    
                    if len(lista_fogos) != int(qtd):
                        st.error(f"❌ Quantidade divergente! Você informou {int(qtd)} pneus, mas digitou {len(lista_fogos)} códigos.")
                    else:
                        sucesso = 0
                        erro = 0
                        
                        # Processar inserção
                        for fogo in lista_fogos:
                            try:
                                run_query("""
                                    INSERT INTO pneus 
                                    (cliente_id, marca_fogo, marca, modelo, medida, status, ciclo_atual, km_vida_total, custo_aquisicao, n_nota_fiscal, fornecedor, data_compra)
                                    VALUES (%s, %s, %s, %s, %s, 'ESTOQUE', 0, 0, %s, %s, %s, %s)
                                """, (cliente_id, fogo, marca, modelo, medida, custo, nf, fornecedor, data_nf))
                                sucesso += 1
                            except Exception as e:
                                st.error(f"⚠️ Erro ao inserir {fogo}: {str(e)[:50]}")
                                erro += 1
                        
                        if sucesso > 0:
                            st.success(f"✅ {sucesso} pneus cadastrados com sucesso!")
                            if erro > 0:
                                st.warning(f"⚠️ {erro} pneu(s) tiveram erro")
                        else:
                            st.error(f"❌ Nenhum pneu foi cadastrado!")
    
    # === TAB 2: FLUXO DE RECAPAGEM ===
    with tab_recap:
        col_envio, col_retorno = st.columns(2)
        
        # COLUNA 1: ENVIAR PARA RECAPADORA
        with col_envio:
            st.subheader("📤 Enviar Carcaça")
            
            # ✅ FIX: Validar se resultado é None ou lista vazia
            pneus_recap = run_query(
                "SELECT id, marca_fogo, marca FROM pneus WHERE cliente_id = %s AND status = 'RECAPAGEM'",
                (cliente_id,)
            )
            
            if pneus_recap and len(pneus_recap) > 0:
                with st.form("enviar_recap"):
                    opcoes = [f"{p['marca_fogo']} - {p['marca']}" for p in pneus_recap]
                    pneu_idx = st.selectbox("Selecione a Carcaça", range(len(opcoes)), format_func=lambda i: opcoes[i])
                    recapadora = st.text_input("Nome da Recapadora")
                    os = st.text_input("Número da OS/Coleta")
                    
                    if st.form_submit_button("📮 Registrar Coleta"):
                        if recapadora and os:
                            st.success(f"✅ Pneu enviado para {recapadora} (OS: {os})")
                        else:
                            st.error("❌ Preencha todos os campos!")
            else:
                st.info("ℹ️ Nenhuma carcaça aguardando envio.")
        
        # COLUNA 2: RECEBER PRONTO
        with col_retorno:
            st.subheader("📥 Receber Pronto")
            
            if pneus_recap and len(pneus_recap) > 0:
                with st.form("retorno_recap"):
                    opcoes = [p['marca_fogo'] for p in pneus_recap]
                    pneu_chegada_idx = st.selectbox("Pneu Retornando", range(len(opcoes)), format_func=lambda i: opcoes[i], key="retorno_pneu")
                    custo_servico = st.number_input("Custo do Serviço (R$)", min_value=0.0)
                    banda = st.text_input("Nova Banda Aplicada", placeholder="ex: Michelin XZU")
                    
                    if st.form_submit_button("📥 Dar Entrada no Estoque"):
                        pneu_id = pneus_recap[pneu_chegada_idx]['id']
                        try:
                            run_query("""
                                UPDATE pneus
                                SET status='ESTOQUE', ciclo_atual = ciclo_atual + 1, modelo = %s
                                WHERE id = %s
                            """, (f"Recap {banda}", pneu_id))
                            st.success("✅ Pneu renovado e disponível no estoque!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erro ao atualizar: {e}")
            else:
                st.info("ℹ️ Nenhum pneu em recapagem.")
    
    # === TAB 3: INVENTÁRIO ===
    with tab_estoque:
        st.subheader("📊 Posição Geral de Ativos")
        
        # Filtros
        col_filter, col_stats = st.columns([2, 1])
        
        with col_filter:
            filtro = st.multiselect(
                "Filtrar por Status",
                ["ESTOQUE", "MONTADO", "RECAPAGEM", "SUCATA"],
                default=["ESTOQUE", "MONTADO"]
            )
        
        if filtro:
            # ✅ FIX: Validar resultado
            placeholders = ', '.join(['%s'] * len(filtro))
            query = f"""
                SELECT 
                    marca_fogo, marca, medida, status, 
                    ciclo_atual, posicao_atual, custo_aquisicao, km_vida_total
                FROM pneus 
                WHERE cliente_id = %s AND status IN ({placeholders})
                ORDER BY marca_fogo
            """
            params = [cliente_id] + filtro
            dados = run_query(query, tuple(params))
            
            if dados and len(dados) > 0:
                df = pd.DataFrame(dados)
                
                # Estatísticas
                with col_stats:
                    st.metric("Total Listado", len(df))
                    investimento = df['custo_aquisicao'].sum() if 'custo_aquisicao' in df.columns else 0
                    st.metric("Investimento", f"R$ {investimento:,.2f}")
                
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Download CSV
                csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Baixar como CSV",
                    data=csv,
                    file_name=f"inventario_pneus_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ Nenhum pneu encontrado com estes filtros.")
        else:
            st.info("ℹ️ Selecione pelo menos um status para visualizar.")
