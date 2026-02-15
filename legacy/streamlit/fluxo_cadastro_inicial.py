import streamlit as st

from database import run_query, executar_acao_colocar_pneu

POSICOES_BASE = [
    "FL", "FR", "TL_OUT", "TL_IN", "TR_IN", "TR_OUT", "RL_OUT", "RL_IN", "RR_IN", "RR_OUT"
]


def _listar_caminhoes(cliente_id):
    return run_query(
        """
        SELECT id, placa, modelo, km_atual, config_eixos
        FROM caminhoes
        WHERE cliente_id = %s
        ORDER BY placa
        """,
        (cliente_id,),
    ) or []


def _posicoes_por_config(config_eixos):
    texto = (config_eixos or "").strip().lower()
    if "toco" in texto:
        return ["FL", "FR", "TL_OUT", "TL_IN", "TR_IN", "TR_OUT"]
    return POSICOES_BASE


def _buscar_pneu(cliente_id, marca_fogo):
    dados = run_query(
        """
        SELECT id, marca_fogo, status
        FROM pneus
        WHERE cliente_id = %s AND UPPER(marca_fogo) = UPPER(%s)
        LIMIT 1
        """,
        (cliente_id, marca_fogo),
    ) or []
    return dados[0] if dados else None


def _garantir_pneu_em_estoque(cliente_id, marca_fogo, marca, medida):
    pneu = _buscar_pneu(cliente_id, marca_fogo)
    if pneu:
        return True, pneu["id"], None

    ok = run_query(
        """
        INSERT INTO pneus (cliente_id, marca_fogo, marca, medida, status, ciclo_atual, km_vida_total)
        VALUES (%s, %s, %s, %s, 'ESTOQUE', 0, 0)
        """,
        (cliente_id, marca_fogo.strip().upper(), (marca or "").strip() or None, (medida or "").strip() or None),
    )
    if not ok:
        return False, None, "Falha ao criar pneu em estoque."

    pneu = _buscar_pneu(cliente_id, marca_fogo)
    if not pneu:
        return False, None, "Pneu criado mas nao localizado em seguida."
    return True, pneu["id"], None


def _render_cadastro_caminhao(cliente_id):
    st.subheader("1) Cadastrar caminhao")
    with st.form("form_caminhao"):
        c1, c2, c3 = st.columns(3)
        placa = c1.text_input("Placa").strip().upper()
        modelo = c2.text_input("Modelo").strip()
        km_atual = c3.number_input("KM atual", min_value=0, value=0, step=100)

        config = st.selectbox("Configuracao de eixos", ["truck", "toco"], index=0)
        salvar = st.form_submit_button("Salvar caminhao")

        if salvar:
            if not placa:
                st.error("Informe a placa.")
                return
            existe = run_query(
                "SELECT id FROM caminhoes WHERE cliente_id = %s AND UPPER(placa) = UPPER(%s)",
                (cliente_id, placa),
            )
            if existe:
                st.warning("Ja existe caminhao com essa placa para este cliente.")
                return

            ok = run_query(
                """
                INSERT INTO caminhoes (cliente_id, placa, modelo, km_atual, ativo, config_eixos)
                VALUES (%s, %s, %s, %s, TRUE, %s)
                """,
                (cliente_id, placa, modelo or None, int(km_atual), config),
            )
            if ok:
                st.success("Caminhao cadastrado.")
                st.rerun()
            else:
                st.error("Nao foi possivel cadastrar caminhao.")


def _render_carga_inicial(cliente_id, user_id, user_role):
    st.subheader("2) Carga inicial por posicao")
    caminhoes = _listar_caminhoes(cliente_id)
    if not caminhoes:
        st.info("Cadastre ao menos um caminhao para iniciar a carga.")
        return

    mapa = {c["placa"]: c for c in caminhoes}
    placa = st.selectbox("Caminhao", list(mapa.keys()), key="ci_placa")
    cam = mapa[placa]
    posicoes = _posicoes_por_config(cam.get("config_eixos"))

    st.caption("Digite a marca de fogo de cada pneu fisicamente montado e confirme.")
    posicao = st.selectbox("Posicao", posicoes, key="ci_pos")
    c1, c2 = st.columns(2)
    marca_fogo = c1.text_input("Marca de fogo", key="ci_mf").strip().upper()
    marca = c2.text_input("Marca (opcional)", key="ci_marca").strip()
    medida = st.text_input("Medida (opcional)", key="ci_medida").strip()

    if st.button("Confirmar carga dessa posicao", key="btn_ci_confirmar"):
        if not marca_fogo:
            st.error("Informe a marca de fogo.")
            return

        ocupado = run_query(
            """
            SELECT p.marca_fogo
            FROM pneus p
            WHERE p.caminhao_atual_id = %s AND p.posicao_atual = %s AND p.status = 'MONTADO'
            """,
            (cam["id"], posicao),
        ) or []
        if ocupado:
            st.error(f"Posicao ocupada por {ocupado[0]['marca_fogo']}.")
            return

        ok, _, err = _garantir_pneu_em_estoque(cliente_id, marca_fogo, marca, medida)
        if not ok:
            st.error(err or "Falha ao preparar pneu para carga.")
            return

        ok_montar, msg = executar_acao_colocar_pneu(
            cliente_id=cliente_id,
            user_id=user_id,
            user_role=user_role,
            marca_fogo=marca_fogo,
            caminhao_id=cam["id"],
            posicao=posicao,
        )
        if ok_montar:
            st.success(msg)
        else:
            st.error(msg)


def render_cadastro_inicial():
    cliente_id = st.session_state.get("cliente_id")
    user_id = st.session_state.get("user_id")
    user_role = st.session_state.get("user_role", "operador")
    role_key = str(user_role).lower()

    if role_key not in ["admin", "gerente", "borracheiro"]:
        st.error("Tela disponivel apenas para perfis de oficina/gestao.")
        return
    if not cliente_id or not user_id:
        st.error("Sessao invalida. Faca login novamente.")
        return

    st.title("Cadastro Inicial da Operacao")
    st.caption("Fluxo recomendado: cadastrar caminhao -> mapear pneus por posicao.")
    _render_cadastro_caminhao(cliente_id)
    st.divider()
    _render_carga_inicial(cliente_id, user_id, user_role)
