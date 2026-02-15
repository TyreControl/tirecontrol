import streamlit as st
from datetime import datetime
from database import run_query, registrar_evento_operacional


def render_movimentacoes():
    st.title("Central de Oficina")

    user_id = st.session_state["user_id"]
    dados_user = run_query("SELECT cliente_id FROM usuarios WHERE id = %s", (user_id,))
    if not dados_user:
        return
    cliente_id = dados_user[0]["cliente_id"]

    caminhoes = run_query(
        "SELECT id, placa, km_atual FROM caminhoes WHERE cliente_id = %s ORDER BY placa",
        (cliente_id,),
    )
    opcoes_cam = {c["placa"]: c for c in caminhoes}

    col_cam, col_km = st.columns([2, 1])
    with col_cam:
        placa = st.selectbox("Veiculo em Manutencao", list(opcoes_cam.keys()))
        cam = opcoes_cam[placa]
    with col_km:
        novo_km = st.number_input("Hodometro Atual", value=cam["km_atual"])
        if novo_km != cam["km_atual"]:
            if st.button("Atualizar KM"):
                run_query("UPDATE caminhoes SET km_atual = %s WHERE id = %s", (novo_km, cam["id"]))
                st.success("KM atualizado")
                st.rerun()

    st.divider()

    tab_montar, tab_baixar, tab_rodizio = st.tabs(
        ["Montar", "Desmontar", "Rodizio"]
    )

    with tab_montar:
        st.subheader("Instalar Pneu do Estoque")
        pneus_estoque = run_query(
            "SELECT id, marca_fogo, marca, medida FROM pneus WHERE cliente_id = %s AND status = 'ESTOQUE'",
            (cliente_id,),
        )

        if not pneus_estoque:
            st.warning("Estoque vazio")
        else:
            with st.form("form_montar"):
                col_p, col_pos = st.columns(2)
                pneu_escolhido = col_p.selectbox(
                    "Pneu disponivel",
                    [f"{p['marca_fogo']} ({p['medida']})" for p in pneus_estoque],
                )
                posicao_alvo = col_pos.selectbox(
                    "Posicao alvo",
                    ["FL", "FR", "TL_OUT", "TL_IN", "TR_IN", "TR_OUT", "RL_OUT", "RL_IN", "RR_IN", "RR_OUT"],
                )

                if st.form_submit_button("Executar Montagem"):
                    ocupado = run_query(
                        "SELECT id FROM pneus WHERE caminhao_atual_id = %s AND posicao_atual = %s",
                        (cam["id"], posicao_alvo),
                    )
                    if ocupado:
                        st.error(f"Posicao {posicao_alvo} ja ocupada")
                    else:
                        pneu_id = next(p["id"] for p in pneus_estoque if p["marca_fogo"] in pneu_escolhido)

                        run_query(
                            "UPDATE pneus SET status='MONTADO', caminhao_atual_id=%s, posicao_atual=%s WHERE id=%s",
                            (cam["id"], posicao_alvo, pneu_id),
                        )
                        run_query(
                            """
                            INSERT INTO movimentacoes (pneu_id, tipo_movimento, destino_caminhao_id, destino_posicao, km_momento, usuario_responsavel)
                            VALUES (%s, 'MONTAGEM', %s, %s, %s, %s)
                            """,
                            (pneu_id, cam["id"], posicao_alvo, novo_km, user_id),
                        )

                        registrar_evento_operacional(
                            cliente_id=cliente_id,
                            tipo_evento="COLOCAR_PNEU",
                            usuario_id=user_id,
                            origem="OFICINA",
                            confianca=80,
                            operation_key=f"montagem:{pneu_id}:{cam['id']}:{posicao_alvo}:{int(datetime.now().timestamp())}",
                            payload={"acao": "montagem", "veiculo_id": str(cam["id"]), "posicao": posicao_alvo},
                            itens=[
                                {
                                    "pneu_id": pneu_id,
                                    "destino_caminhao_id": cam["id"],
                                    "destino_posicao": posicao_alvo,
                                    "km_momento": int(novo_km),
                                }
                            ],
                        )

                        st.success(f"Pneu montado em {posicao_alvo}")
                        st.rerun()

    with tab_baixar:
        st.subheader("Retirar Pneu do Veiculo")
        pneus_montados = run_query(
            "SELECT id, marca_fogo, posicao_atual FROM pneus WHERE caminhao_atual_id = %s",
            (cam["id"],),
        )

        if not pneus_montados:
            st.info("Caminhao sem pneus montados")
        else:
            with st.form("form_baixar"):
                col_b1, col_b2 = st.columns(2)
                pneu_alvo = col_b1.selectbox(
                    "Pneu a retirar",
                    [f"{p['posicao_atual']} - {p['marca_fogo']}" for p in pneus_montados],
                )
                destino = col_b2.selectbox(
                    "Destino fisico",
                    ["ESTOQUE (Guardar)", "RECAPAGEM (Enviar)", "SUCATA (Descarte)"],
                )
                motivo = st.text_input("Motivo tecnico")

                if st.form_submit_button("Confirmar Retirada"):
                    pneu_obj = next(p for p in pneus_montados if p["marca_fogo"] in pneu_alvo)
                    status_destino = destino.split(" ")[0]

                    run_query(
                        "UPDATE pneus SET status=%s, caminhao_atual_id=NULL, posicao_atual=NULL WHERE id=%s",
                        (status_destino, pneu_obj["id"]),
                    )
                    run_query(
                        """
                        INSERT INTO movimentacoes (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, km_momento, usuario_responsavel)
                        VALUES (%s, 'DESMONTAGEM', %s, %s, %s, %s)
                        """,
                        (pneu_obj["id"], cam["id"], pneu_obj["posicao_atual"], novo_km, user_id),
                    )

                    registrar_evento_operacional(
                        cliente_id=cliente_id,
                        tipo_evento="TIRAR_PNEU",
                        usuario_id=user_id,
                        origem="OFICINA",
                        confianca=80,
                        operation_key=f"desmontagem:{pneu_obj['id']}:{cam['id']}:{int(datetime.now().timestamp())}",
                        payload={"acao": "desmontagem", "status_destino": status_destino},
                        itens=[
                            {
                                "pneu_id": pneu_obj["id"],
                                "origem_caminhao_id": cam["id"],
                                "origem_posicao": pneu_obj["posicao_atual"],
                                "km_momento": int(novo_km),
                                "motivo": motivo or None,
                                "observacao": destino,
                            }
                        ],
                    )

                    st.success(f"Pneu enviado para {status_destino}")
                    st.rerun()

    with tab_rodizio:
        st.subheader("Rodizio de Posicoes")
        st.caption("Troca direta entre duas posicoes do mesmo veiculo")

        pneus_montados = run_query(
            "SELECT id, marca_fogo, posicao_atual FROM pneus WHERE caminhao_atual_id = %s",
            (cam["id"],),
        )

        if len(pneus_montados or []) < 2:
            st.warning("Necessario pelo menos 2 pneus montados")
        else:
            c1, c2 = st.columns(2)
            pos_a = c1.selectbox("Posicao A", [p["posicao_atual"] for p in pneus_montados])
            pos_b = c2.selectbox("Posicao B", [p["posicao_atual"] for p in pneus_montados])

            if st.button("Executar Troca"):
                if pos_a == pos_b:
                    st.error("Selecione posicoes diferentes")
                else:
                    id_a = next(p["id"] for p in pneus_montados if p["posicao_atual"] == pos_a)
                    id_b = next(p["id"] for p in pneus_montados if p["posicao_atual"] == pos_b)

                    run_query("UPDATE pneus SET posicao_atual='TEMP' WHERE id=%s", (id_a,))
                    run_query("UPDATE pneus SET posicao_atual=%s WHERE id=%s", (pos_a, id_b))
                    run_query("UPDATE pneus SET posicao_atual=%s WHERE id=%s", (pos_b, id_a))

                    run_query(
                        """
                        INSERT INTO movimentacoes (pneu_id, tipo_movimento, origem_posicao, destino_posicao, km_momento, usuario_responsavel)
                        VALUES (%s, 'RODIZIO', %s, %s, %s, %s)
                        """,
                        (id_a, pos_a, pos_b, novo_km, user_id),
                    )

                    registrar_evento_operacional(
                        cliente_id=cliente_id,
                        tipo_evento="TROCAR_POSICAO",
                        usuario_id=user_id,
                        origem="OFICINA",
                        confianca=80,
                        operation_key=f"rodizio:{cam['id']}:{id_a}:{id_b}:{int(datetime.now().timestamp())}",
                        payload={"acao": "rodizio", "veiculo_id": str(cam["id"])},
                        itens=[
                            {
                                "pneu_id": id_a,
                                "origem_caminhao_id": cam["id"],
                                "origem_posicao": pos_a,
                                "destino_caminhao_id": cam["id"],
                                "destino_posicao": pos_b,
                                "km_momento": int(novo_km),
                            },
                            {
                                "pneu_id": id_b,
                                "origem_caminhao_id": cam["id"],
                                "origem_posicao": pos_b,
                                "destino_caminhao_id": cam["id"],
                                "destino_posicao": pos_a,
                                "km_momento": int(novo_km),
                            },
                        ],
                    )

                    st.success(f"Rodizio realizado: {pos_a} <-> {pos_b}")
                    st.rerun()
