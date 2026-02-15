import streamlit as st
from datetime import datetime, timedelta
import base64
import os
import requests

from database import (
    run_query,
    executar_acao_tirar_pneu,
    executar_acao_colocar_pneu,
    executar_acao_trocar_posicao,
    executar_acao_enviar_recapagem,
    diagnosticar_consistencia,
    reconciliar_inconsistencias_seguras,
)
import frota

POSICOES_PADRAO = [
    "FL", "FR", "TL_OUT", "TL_IN", "TR_IN", "TR_OUT", "RL_OUT", "RL_IN", "RR_IN", "RR_OUT"
]
ACOES_LABEL = {
    "escanear": "Escanear pneu",
    "tirar": "Tirar pneu",
    "colocar": "Colocar pneu",
    "trocar": "Trocar posicao",
    "recapagem": "Enviar recapagem",
    "frota": "Ver frota",
}
ACOES_POR_ROLE = {
    "admin": ["escanear", "tirar", "colocar", "trocar", "recapagem", "frota"],
    "gerente": ["escanear", "tirar", "colocar", "trocar", "recapagem", "frota"],
    "borracheiro": ["escanear", "tirar", "colocar", "trocar", "recapagem", "frota"],
    "operador": ["escanear", "tirar", "colocar", "trocar"],
    "motorista": ["escanear", "tirar", "colocar", "trocar"],
}
SCAN_API_URL = os.getenv("SUPABASE_SCAN_FUNCTION_URL", os.getenv("TYRECONTROL_SCAN_API_URL", "http://localhost:8000/api/scan/pneu"))
SCAN_API_KEY = os.getenv("SUPABASE_ANON_KEY", os.getenv("TYRECONTROL_SCAN_API_KEY", ""))


def _render_stepper(passos, etapa_atual):
    linhas = []
    for idx, passo in enumerate(passos, start=1):
        if idx == etapa_atual:
            linhas.append(f"**{idx}. {passo}**")
        else:
            linhas.append(f"{idx}. {passo}")
    st.markdown(" | ".join(linhas))


def _buscar_pneu(cliente_id, marca_fogo):
    if not marca_fogo:
        return None
    res = run_query(
        """
        SELECT p.id, p.marca_fogo, p.status, p.caminhao_atual_id, p.posicao_atual, p.km_vida_total,
               c.placa
        FROM pneus p
        LEFT JOIN caminhoes c ON c.id = p.caminhao_atual_id
        WHERE p.cliente_id = %s AND UPPER(p.marca_fogo) = UPPER(%s)
        LIMIT 1
        """,
        (cliente_id, marca_fogo.strip()),
    )
    return res[0] if res else None


def _listar_caminhoes(cliente_id):
    return run_query(
        "SELECT id, placa, km_atual FROM caminhoes WHERE cliente_id = %s ORDER BY placa",
        (cliente_id,),
    ) or []


def _set_acao(acao):
    st.session_state["acao_atual"] = acao

def _registrar_scan_context(pneu):
    scans = st.session_state.get("scans_recentes", {})
    scans[pneu["marca_fogo"].upper()] = datetime.now().isoformat()
    st.session_state["scans_recentes"] = scans
    st.session_state["ultimo_scan"] = pneu["marca_fogo"].upper()

def _scan_valido_para(codigo):
    if not codigo:
        return False
    scans = st.session_state.get("scans_recentes", {})
    ts_raw = scans.get(codigo.strip().upper())
    if not ts_raw:
        return False
    try:
        ts = datetime.fromisoformat(ts_raw)
    except Exception:
        return False
    return ts >= datetime.now() - timedelta(minutes=10)

def _render_hint_scan_obrigatorio(codigo):
    if _scan_valido_para(codigo):
        return True
    st.warning("Escaneie este pneu primeiro na acao `Escanear pneu`.")
    if st.button("Ir para Escanear", key=f"go_scan_{codigo or 'vazio'}"):
        _set_acao("escanear")
        st.rerun()
    return False

def _render_fluxo_obvio():
    st.caption("Fluxo: escolha acao -> escaneie -> confirme")
    acao_atual = st.session_state.get("acao_atual")
    if not acao_atual:
        if st.button("Comecar em Escanear", key="btn_comecar_agora"):
            _set_acao("escanear")
            st.rerun()
    else:
        st.caption(f"Acao ativa: {ACOES_LABEL.get(acao_atual, acao_atual)}")


def _render_topo_acoes(acoes_permitidas):
    st.subheader("O que aconteceu com o pneu?")
    acoes_ordenadas = ["escanear", "trocar", "tirar", "colocar", "recapagem", "frota"]
    acoes = [a for a in acoes_ordenadas if a in acoes_permitidas]
    if not acoes:
        st.error("Nenhuma acao disponivel para este perfil.")
        return

    for i in range(0, len(acoes), 3):
        linha = acoes[i:i + 3]
        cols = st.columns(len(linha))
        for col, acao in zip(cols, linha):
            if col.button(ACOES_LABEL[acao], use_container_width=True, key=f"acao_{acao}"):
                _set_acao(acao)

def _render_operacao(cliente_id, user_id, role, acoes_permitidas):
    _render_fluxo_obvio()
    _render_topo_acoes(acoes_permitidas)

    if st.session_state.get("acao_atual") not in acoes_permitidas:
        st.session_state["acao_atual"] = acoes_permitidas[0]

    acao = st.session_state.get("acao_atual", "escanear")

    if acao == "escanear":
        _render_escanear(cliente_id, user_id, role)
    elif acao == "tirar":
        _render_tirar(cliente_id, user_id, role)
    elif acao == "colocar":
        _render_colocar(cliente_id, user_id, role)
    elif acao == "trocar":
        _render_trocar(cliente_id, user_id, role)
    elif acao == "recapagem":
        _render_recapagem(cliente_id, user_id, role)
    elif acao == "frota":
        frota.render_frota()

def _render_gestao(cliente_id, user_id, role):
    st.subheader("Gestao")
    _render_consistencia(cliente_id, user_id, role)
    st.divider()
    _render_perguntas_gestor(cliente_id)

def _render_consistencia(cliente_id, user_id, user_role):
    st.markdown("### Saude dos dados operacionais")
    diagnostico = diagnosticar_consistencia(cliente_id)
    resumo = diagnostico["resumo"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", resumo["total"])
    c2.metric("Montado sem vinculo", resumo["montado_sem_vinculo"])
    c3.metric("Nao montado com vinculo", resumo["nao_montado_com_vinculo"])
    c4.metric("Posicao duplicada", resumo["posicao_duplicada_montado"])

    if resumo["total"] == 0:
        st.success("Dados consistentes no momento")
        return

    st.caption("Correcao segura atua apenas em casos deterministicos.")
    if st.button("Aplicar correcao segura", key="btn_reconciliar"):
        ok, msg, dados = reconciliar_inconsistencias_seguras(cliente_id, user_id, user_role)
        if ok:
            st.success(msg)
            if dados:
                st.write(
                    f"Ajustes: estoque={dados.get('corrigidos_para_estoque', 0)} | "
                    f"vinculos_limpos={dados.get('vinculos_limpos', 0)}"
                )
                if dados.get("evento_id"):
                    st.caption(f"Evento auditoria: {dados['evento_id']}")
        else:
            st.error(msg)


def _render_acao_recomendada_scan(cliente_id, user_id, user_role, pneu):
    st.markdown("### Proximo passo recomendado")

    status = pneu["status"]
    if status == "MONTADO":
        st.info("Pneu montado detectado. Acao recomendada: Tirar pneu.")
        c1, c2, c3 = st.columns(3)
        if c1.button("Tirar por desgaste", key=f"rec_tirar_desg_{pneu['id']}"):
            ok, msg = executar_acao_tirar_pneu(
                cliente_id=cliente_id,
                user_id=user_id,
                user_role=user_role,
                marca_fogo=pneu["marca_fogo"],
                motivo="desgaste",
                status_destino="RECAPAGEM",
            )
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        if c2.button("Tirar por dano", key=f"rec_tirar_dano_{pneu['id']}"):
            ok, msg = executar_acao_tirar_pneu(
                cliente_id=cliente_id,
                user_id=user_id,
                user_role=user_role,
                marca_fogo=pneu["marca_fogo"],
                motivo="dano",
                status_destino="SUCATA",
            )
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        if c3.button("Tirar para recapagem", key=f"rec_tirar_recap_{pneu['id']}"):
            ok, msg = executar_acao_tirar_pneu(
                cliente_id=cliente_id,
                user_id=user_id,
                user_role=user_role,
                marca_fogo=pneu["marca_fogo"],
                motivo="recapagem",
                status_destino="RECAPAGEM",
            )
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    elif status in ["ESTOQUE", "RECAPAGEM"]:
        st.info("Pneu disponivel para montagem. Acao recomendada: Colocar pneu.")
        if st.button("Ir para Colocar pneu", key=f"rec_ir_colocar_{pneu['id']}"):
            st.session_state["prefill_pneu"] = pneu["marca_fogo"]
            _set_acao("colocar")
            st.rerun()
    elif status == "SUCATA":
        st.warning("Pneu em sucata. Nao ha acao operacional recomendada.")
    else:
        st.info("Sem recomendacao automatica para este status.")

def _chamar_api_scan_pneu(file_bytes, filename, content_type):
    try:
        image_b64 = base64.b64encode(file_bytes).decode("utf-8")
        headers = {"Content-Type": "application/json"}
        if SCAN_API_KEY:
            headers["Authorization"] = f"Bearer {SCAN_API_KEY}"
            headers["apikey"] = SCAN_API_KEY
        payload = {
            "image_base64": image_b64,
            "mime_type": content_type,
            "filename": filename,
        }
        resp = requests.post(SCAN_API_URL, headers=headers, json=payload, timeout=35)
    except Exception as e:
        return False, f"Falha ao chamar API de scan: {e}", None

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        return False, f"Erro no scan ({resp.status_code}): {detail}", None

    data = resp.json()
    result = (data or {}).get("result") or {}
    marca_fogo = result.get("marca_fogo")
    return True, "Scan concluido", {
        "marca_fogo": marca_fogo,
        "confidence": result.get("confidence"),
        "raw_text": result.get("raw_text"),
    }


def _render_scan_embutido(cliente_id, key_prefix, titulo="Escanear por foto"):
    st.markdown(f"#### {titulo}")
    usar_camera = st.toggle("Usar camera agora", value=False, key=f"{key_prefix}_usar_camera")
    c1, c2 = st.columns(2)
    with c1:
        foto_camera = st.camera_input("Foto da camera", key=f"{key_prefix}_camera") if usar_camera else None
    with c2:
        foto_upload = st.file_uploader(
            "Ou envie imagem",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"{key_prefix}_upload",
        )

    if st.button("Reconhecer por foto", key=f"{key_prefix}_reconhecer"):
        file_obj = foto_camera or foto_upload
        if not file_obj:
            st.warning("Tire uma foto ou envie imagem.")
            return None

        file_bytes = file_obj.getvalue()
        content_type = getattr(file_obj, "type", None) or "image/jpeg"
        filename = getattr(file_obj, "name", None) or "scan.jpg"
        ok, msg, payload = _chamar_api_scan_pneu(file_bytes, filename, content_type)
        if not ok:
            st.error(msg)
            return None

        marca_fogo = (payload or {}).get("marca_fogo")
        conf = (payload or {}).get("confidence")
        if not marca_fogo:
            st.warning("Nao foi possivel identificar a marcacao.")
            raw = (payload or {}).get("raw_text")
            if raw:
                st.caption(f"Texto detectado: {raw[:220]}")
            return None

        pneu = _buscar_pneu(cliente_id, marca_fogo)
        if not pneu:
            st.warning(f"Codigo lido ({marca_fogo}), mas pneu nao localizado no banco.")
            return None

        _registrar_scan_context(pneu)
        st.success(f"Leitura: {pneu['marca_fogo']} (confianca {round((conf or 0)*100)}%)")
        return pneu
    return None


def _render_escanear(cliente_id, user_id, user_role):
    st.markdown("### Escanear pneu")

    st.caption("Preferencial: tire uma foto do pneu para leitura automatica da marcacao.")
    usar_camera = st.toggle("Usar camera agora", value=False, key="scan_usar_camera")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        foto_camera = st.camera_input("Foto da camera", key="scan_camera") if usar_camera else None
    with col_f2:
        foto_upload = st.file_uploader(
            "Ou envie imagem",
            type=["jpg", "jpeg", "png", "webp"],
            key="scan_upload",
        )

    codigo = st.text_input("Codigo do pneu (fallback manual)", key="scan_codigo")

    cbtn1, cbtn2 = st.columns(2)
    with cbtn1:
        reconhecer_foto = st.button("Reconhecer por foto", key="btn_reconhecer_foto")
    with cbtn2:
        reconhecer_manual = st.button("Reconhecer manual", key="btn_reconhecer_manual")

    if reconhecer_foto:
        file_obj = foto_camera or foto_upload
        if not file_obj:
            st.warning("Tire uma foto ou envie imagem para reconhecer por foto.")
        else:
            file_bytes = file_obj.getvalue()
            content_type = getattr(file_obj, "type", None) or "image/jpeg"
            filename = getattr(file_obj, "name", None) or "scan.jpg"
            ok, msg, payload = _chamar_api_scan_pneu(file_bytes, filename, content_type)
            if not ok:
                st.error(msg)
            else:
                marca_fogo = (payload or {}).get("marca_fogo")
                conf = (payload or {}).get("confidence")
                if marca_fogo:
                    st.session_state["scan_codigo"] = marca_fogo
                    st.success(f"Leitura automatica: {marca_fogo} (confianca {round((conf or 0)*100)}%)")
                    pneu = _buscar_pneu(cliente_id, marca_fogo)
                    st.session_state["scan_result"] = pneu
                    if pneu:
                        _registrar_scan_context(pneu)
                    else:
                        st.warning("Codigo lido, mas pneu nao localizado no banco.")
                else:
                    st.warning("Nao foi possivel identificar a marcacao. Use fallback manual.")
                    raw = (payload or {}).get("raw_text")
                    if raw:
                        st.caption(f"Texto detectado: {raw[:220]}")

    if reconhecer_manual:
        pneu = _buscar_pneu(cliente_id, codigo)
        st.session_state["scan_result"] = pneu
        if pneu:
            _registrar_scan_context(pneu)

    pneu = st.session_state.get("scan_result")
    if not pneu:
        return

    st.success("Pneu reconhecido")
    st.write(f"Pneu: {pneu['marca_fogo']}")
    st.write(f"Status atual: {pneu['status']}")
    st.write(f"Veiculo: {pneu['placa'] or '-'}")
    st.write(f"Posicao: {pneu['posicao_atual'] or '-'}")

    c1, c2, c3 = st.columns(3)
    if c1.button("Ir para Tirar", key="scan_tirar"):
        st.session_state["prefill_pneu"] = pneu["marca_fogo"]
        _set_acao("tirar")
        st.rerun()
    if c2.button("Ir para Colocar", key="scan_colocar"):
        st.session_state["prefill_pneu"] = pneu["marca_fogo"]
        _set_acao("colocar")
        st.rerun()
    if c3.button("Ir para Trocar", key="scan_trocar"):
        st.session_state["prefill_pneu_a"] = pneu["marca_fogo"]
        _set_acao("trocar")
        st.rerun()

    c4, c5 = st.columns(2)
    if c4.button("Definir como Pneu A", key="scan_set_a"):
        st.session_state["prefill_pneu_a"] = pneu["marca_fogo"]
        st.success("Pneu A definido")
    if c5.button("Definir como Pneu B", key="scan_set_b"):
        st.session_state["prefill_pneu_b"] = pneu["marca_fogo"]
        st.success("Pneu B definido")

    _render_acao_recomendada_scan(cliente_id, user_id, user_role, pneu)


def _render_tirar(cliente_id, user_id, user_role):
    st.markdown("### Tirar pneu")
    _render_stepper(
        ["Escaneie o pneu", "Selecione o motivo", "Confirme retirada"],
        1,
    )

    pneu_scan = _render_scan_embutido(cliente_id, "tirar", "Passo 1 - Escanear pneu")
    if pneu_scan:
        st.session_state["prefill_pneu"] = pneu_scan["marca_fogo"]

    default = st.session_state.get("prefill_pneu", "")
    codigo = st.text_input("Escaneie o pneu", value=default, key="tirar_codigo")

    pneu = _buscar_pneu(cliente_id, codigo)
    if not pneu:
        if codigo:
            st.warning("Pneu nao encontrado")
        return

    if pneu["status"] != "MONTADO":
        st.warning("Esse pneu nao esta montado")
        return
    if not _render_hint_scan_obrigatorio(pneu["marca_fogo"]):
        return

    st.info(f"Reconhecido: {pneu['marca_fogo']} em {pneu['placa']} / {pneu['posicao_atual']}")
    motivo = st.radio(
        "Motivo",
        ["desgaste", "dano", "recapagem"],
        horizontal=True,
        key="tirar_motivo",
    )

    destino_map = {
        "desgaste": "RECAPAGEM",
        "dano": "SUCATA",
        "recapagem": "RECAPAGEM",
    }
    status_destino = destino_map[motivo]

    if st.button("Confirmar retirada", key="confirmar_tirar"):
        ok, msg = executar_acao_tirar_pneu(
            cliente_id=cliente_id,
            user_id=user_id,
            user_role=user_role,
            marca_fogo=pneu["marca_fogo"],
            motivo=motivo,
            status_destino=status_destino,
        )
        if ok:
            st.success(msg)
            st.session_state["prefill_pneu"] = ""
        else:
            st.error(msg)


def _render_colocar(cliente_id, user_id, user_role):
    st.markdown("### Colocar pneu")
    _render_stepper(
        ["Escaneie o pneu", "Escolha veiculo e posicao", "Confirme montagem"],
        1,
    )
    pneu_scan = _render_scan_embutido(cliente_id, "colocar", "Passo 1 - Escanear pneu")
    if pneu_scan:
        st.session_state["prefill_pneu"] = pneu_scan["marca_fogo"]

    default = st.session_state.get("prefill_pneu", "")
    codigo = st.text_input("Escaneie o pneu", value=default, key="colocar_codigo")

    pneu = _buscar_pneu(cliente_id, codigo)
    if not pneu:
        if codigo:
            st.warning("Pneu nao encontrado")
        return

    if pneu["status"] not in ["ESTOQUE", "RECAPAGEM"]:
        st.warning("Esse pneu nao pode ser montado neste momento")
        return
    if not _render_hint_scan_obrigatorio(pneu["marca_fogo"]):
        return

    caminhoes = _listar_caminhoes(cliente_id)
    if not caminhoes:
        st.warning("Nenhum caminhao cadastrado")
        return

    mapa = {c["placa"]: c for c in caminhoes}
    placa = st.selectbox("Veiculo", list(mapa.keys()), key="colocar_placa")
    cam = mapa[placa]
    posicao = st.selectbox("Posicao", POSICOES_PADRAO, key="colocar_pos")

    ocupado = run_query(
        "SELECT id FROM pneus WHERE caminhao_atual_id=%s AND posicao_atual=%s AND status='MONTADO'",
        (cam["id"], posicao),
    )
    if ocupado:
        st.error("Posicao ocupada")
        return

    if st.button("Confirmar montagem", key="confirmar_colocar"):
        ok, msg = executar_acao_colocar_pneu(
            cliente_id=cliente_id,
            user_id=user_id,
            user_role=user_role,
            marca_fogo=pneu["marca_fogo"],
            caminhao_id=cam["id"],
            posicao=posicao,
        )
        if ok:
            st.success(msg)
            st.session_state["prefill_pneu"] = ""
        else:
            st.error(msg)


def _render_trocar(cliente_id, user_id, user_role):
    st.markdown("### Trocar posicao")
    _render_stepper(
        ["Escaneie pneu A e B", "Validar troca no mesmo veiculo", "Confirmar troca"],
        1,
    )

    col_scan_a, col_scan_b = st.columns(2)
    with col_scan_a:
        pneu_a_scan = _render_scan_embutido(cliente_id, "troca_a", "Passo 1 - Escanear pneu A")
        if pneu_a_scan:
            st.session_state["prefill_pneu_a"] = pneu_a_scan["marca_fogo"]
    with col_scan_b:
        pneu_b_scan = _render_scan_embutido(cliente_id, "troca_b", "Passo 1 - Escanear pneu B")
        if pneu_b_scan:
            st.session_state["prefill_pneu_b"] = pneu_b_scan["marca_fogo"]

    default_a = st.session_state.get("prefill_pneu_a", "")
    default_b = st.session_state.get("prefill_pneu_b", "")
    codigo_a = st.text_input("Escaneie pneu A", value=default_a, key="troca_a")
    codigo_b = st.text_input("Escaneie pneu B", value=default_b, key="troca_b")

    pneu_a = _buscar_pneu(cliente_id, codigo_a)
    pneu_b = _buscar_pneu(cliente_id, codigo_b)

    if not pneu_a or not pneu_b:
        return

    if pneu_a["status"] != "MONTADO" or pneu_b["status"] != "MONTADO":
        st.error("Os dois pneus precisam estar montados")
        return

    if pneu_a["caminhao_atual_id"] != pneu_b["caminhao_atual_id"]:
        st.error("Os pneus precisam estar no mesmo veiculo")
        return

    if pneu_a["posicao_atual"] == pneu_b["posicao_atual"]:
        st.error("Os pneus ja estao na mesma posicao")
        return
    if not _scan_valido_para(pneu_a["marca_fogo"]) or not _scan_valido_para(pneu_b["marca_fogo"]):
        st.warning("Para confirmar a troca, escaneie os dois pneus antes.")
        if st.button("Ir para Escanear", key="troca_ir_scan"):
            _set_acao("escanear")
            st.rerun()
        return

    st.info(
        f"Troca reconhecida: {pneu_a['marca_fogo']} ({pneu_a['posicao_atual']}) <-> "
        f"{pneu_b['marca_fogo']} ({pneu_b['posicao_atual']})"
    )

    if st.button("Confirmar troca", key="confirmar_troca"):
        ok, msg = executar_acao_trocar_posicao(
            cliente_id=cliente_id,
            user_id=user_id,
            user_role=user_role,
            marca_fogo_a=pneu_a["marca_fogo"],
            marca_fogo_b=pneu_b["marca_fogo"],
        )
        if ok:
            st.success(msg)
            st.session_state["prefill_pneu_a"] = ""
            st.session_state["prefill_pneu_b"] = ""
        else:
            st.error(msg)


def _render_recapagem(cliente_id, user_id, user_role):
    st.markdown("### Enviar recapagem")
    _render_stepper(
        ["Escaneie pneus do lote", "Selecionar recapadora", "Confirmar envio"],
        1,
    )

    lista_key = "recap_lote_codigos"
    if lista_key not in st.session_state:
        st.session_state[lista_key] = []

    pneu_scan = _render_scan_embutido(cliente_id, "recap", "Passo 1 - Escanear pneu do lote")
    if pneu_scan:
        cod = pneu_scan["marca_fogo"].upper()
        if cod not in st.session_state[lista_key]:
            st.session_state[lista_key].append(cod)
            st.success(f"{cod} adicionado ao lote.")

    codigos_text = st.text_area("Ou informe codigos manualmente (um por linha)", key="recap_codigos")
    recapadora = st.text_input("Recapadora", value="RecaPro", key="recap_nome")

    if st.session_state[lista_key]:
        st.caption("Lote por scan:")
        st.write(", ".join(st.session_state[lista_key]))
        if st.button("Limpar lote escaneado", key="recap_limpar_lote"):
            st.session_state[lista_key] = []
            st.rerun()

    if st.button("Enviar lote", key="enviar_lote"):
        codigos = [c.strip().upper() for c in codigos_text.splitlines() if c.strip()]
        codigos = list(dict.fromkeys(st.session_state[lista_key] + codigos))
        ok, msg, _ = executar_acao_enviar_recapagem(
            cliente_id=cliente_id,
            user_id=user_id,
            user_role=user_role,
            recapadora=recapadora,
            codigos=codigos,
        )
        if ok:
            st.success(msg)
            st.session_state[lista_key] = []
        else:
            st.error(msg)


def _render_perguntas_gestor(cliente_id):
    st.markdown("### Respostas para gestor")

    pergunta = st.selectbox(
        "Pergunta pronta",
        [
            "Quem esta errando rodizio",
            "Qual caminhao destroi pneu",
            "Qual eixo come borracha",
            "Quantos km perdi esse mes",
        ],
        key="gestor_pergunta",
    )

    if pergunta == "Quem esta errando rodizio":
        dados = run_query(
            """
            SELECT u.nome,
                   SUM(CASE WHEN m.tipo_movimento = 'DESMONTAGEM' THEN 1 ELSE 0 END) AS desmontagens,
                   SUM(CASE WHEN m.tipo_movimento = 'MONTAGEM' THEN 1 ELSE 0 END) AS montagens
            FROM movimentacoes m
            JOIN usuarios u ON u.id = m.usuario_responsavel
            JOIN pneus p ON p.id = m.pneu_id
            WHERE p.cliente_id = %s
              AND m.data_movimento >= NOW() - INTERVAL '30 days'
            GROUP BY u.nome
            ORDER BY (SUM(CASE WHEN m.tipo_movimento = 'DESMONTAGEM' THEN 1 ELSE 0 END) -
                      SUM(CASE WHEN m.tipo_movimento = 'MONTAGEM' THEN 1 ELSE 0 END)) DESC
            LIMIT 1
            """,
            (cliente_id,),
        )
        if dados:
            d = dados[0]
            diff = (d["desmontagens"] or 0) - (d["montagens"] or 0)
            if diff > 0:
                st.warning(f"{d['nome']} tem {diff} desmontagens sem fechamento no periodo.")
            else:
                st.success("Nao ha sinal forte de erro operacional no periodo.")
        else:
            st.info("Sem dados suficientes.")

    elif pergunta == "Qual caminhao destroi pneu":
        dados = run_query(
            """
            SELECT c.placa, AVG(p.km_vida_total) AS media_km
            FROM pneus p
            JOIN caminhoes c ON c.id = p.caminhao_atual_id
            WHERE p.cliente_id = %s
              AND p.status = 'MONTADO'
            GROUP BY c.placa
            ORDER BY media_km ASC
            LIMIT 1
            """,
            (cliente_id,),
        )
        if dados:
            d = dados[0]
            st.warning(f"{d['placa']} esta com menor media de vida util: {int(d['media_km'] or 0)} km.")
        else:
            st.info("Sem dados suficientes.")

    elif pergunta == "Qual eixo come borracha":
        dados = run_query(
            """
            SELECT origem_posicao, COUNT(*) AS total
            FROM movimentacoes m
            JOIN pneus p ON p.id = m.pneu_id
            WHERE p.cliente_id = %s
              AND m.tipo_movimento = 'DESMONTAGEM'
              AND origem_posicao IS NOT NULL
              AND m.data_movimento >= NOW() - INTERVAL '90 days'
            GROUP BY origem_posicao
            ORDER BY total DESC
            LIMIT 1
            """,
            (cliente_id,),
        )
        if dados:
            d = dados[0]
            st.warning(f"Posicao {d['origem_posicao']} lidera desgaste recente ({d['total']} desmontagens).")
        else:
            st.info("Sem dados suficientes.")

    elif pergunta == "Quantos km perdi esse mes":
        dados = run_query(
            """
            SELECT COALESCE(SUM(GREATEST(0, 100000 - COALESCE(p.km_vida_total, 0))), 0) AS km_perdidos
            FROM movimentacoes m
            JOIN pneus p ON p.id = m.pneu_id
            WHERE p.cliente_id = %s
              AND m.tipo_movimento = 'DESMONTAGEM'
              AND p.status = 'SUCATA'
              AND m.data_movimento >= date_trunc('month', NOW())
            """,
            (cliente_id,),
        )
        km = int((dados[0]["km_perdidos"] if dados else 0) or 0)
        st.warning(f"Perda estimada no mes: {km} km de vida util.")


def render_central_acoes():
    cliente_id = st.session_state.get("cliente_id")
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("user_role", "operador")
    role_key = str(role).lower()
    acoes_permitidas = ACOES_POR_ROLE.get(role_key, ACOES_POR_ROLE["operador"])

    if not cliente_id or not user_id:
        st.error("Sessao invalida. Faca login novamente.")
        return

    st.title("TireControl - Sistema de Acoes")
    if role_key in ["motorista", "operador"]:
        st.caption("Modo rapido: escanear -> confirmar")

    if role_key in ["admin", "gerente"]:
        modo = st.radio("Area", ["Operacao", "Gestao"], horizontal=True, key="area_modo")
        st.divider()
        if modo == "Operacao":
            _render_operacao(cliente_id, user_id, role, acoes_permitidas)
        else:
            _render_gestao(cliente_id, user_id, role)
    else:
        _render_operacao(cliente_id, user_id, role, acoes_permitidas)


def render_pagina_operacao(acao):
    cliente_id = st.session_state.get("cliente_id")
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("user_role", "operador")
    role_key = str(role).lower()
    acoes_permitidas = ACOES_POR_ROLE.get(role_key, ACOES_POR_ROLE["operador"])

    if not cliente_id or not user_id:
        st.error("Sessao invalida. Faca login novamente.")
        return
    if acao not in acoes_permitidas:
        st.error("Tela nao liberada para seu perfil.")
        return

    st.title(f"Borracharia - {ACOES_LABEL.get(acao, acao)}")
    st.caption("Fluxo: escanear -> validar -> confirmar")

    if acao == "escanear":
        _render_escanear(cliente_id, user_id, role)
    elif acao == "tirar":
        _render_tirar(cliente_id, user_id, role)
    elif acao == "colocar":
        _render_colocar(cliente_id, user_id, role)
    elif acao == "trocar":
        _render_trocar(cliente_id, user_id, role)
    elif acao == "recapagem":
        _render_recapagem(cliente_id, user_id, role)
    elif acao == "frota":
        frota.render_frota()
    else:
        st.info("Acao ainda nao implementada.")


def render_pagina_gestao():
    cliente_id = st.session_state.get("cliente_id")
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("user_role", "operador")
    role_key = str(role).lower()

    if role_key not in ["admin", "gerente"]:
        st.error("Tela disponivel apenas para gerente/admin.")
        return
    if not cliente_id or not user_id:
        st.error("Sessao invalida. Faca login novamente.")
        return

    st.title("Painel da Gestao")
    _render_consistencia(cliente_id, user_id, role)
    st.divider()
    _render_perguntas_gestor(cliente_id)
