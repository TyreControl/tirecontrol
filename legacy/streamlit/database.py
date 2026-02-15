import streamlit as st
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from datetime import datetime
import json

# Configuração do Pool de Conexões
@st.cache_resource
def init_connection_pool():
    try:
        return psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=st.secrets["SUPABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        st.error(f"Erro crítico ao conectar no banco: {e}")
        return None

def get_connection():
    """Obtém uma conexão do pool"""
    pool = init_connection_pool()
    if pool:
        return pool.getconn()
    return None

def release_connection(conn):
    """Devolve a conexão ao pool"""
    pool = init_connection_pool()
    if pool and conn:
        pool.putconn(conn)

def run_query(query, params=None):
    """Executa uma query simples e retorna resultado"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            
            if query.strip().upper().startswith("SELECT"):
                return cur.fetchall()
            else:
                conn.commit()
                return True
    except Exception as e:
        st.error(f"Erro na query: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        release_connection(conn)

def registrar_evento_operacional(
    cliente_id,
    tipo_evento,
    usuario_id=None,
    origem="OFICINA",
    confianca=80,
    operation_key=None,
    payload=None,
    itens=None,
):
    """
    Registra um evento operacional e seus itens de forma transacional.
    Retorna o UUID do evento criado.
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eventos_operacionais
                (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
                VALUES (%s, %s, 'CONFIRMADO', %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    cliente_id,
                    tipo_evento,
                    usuario_id,
                    origem,
                    confianca,
                    operation_key,
                    json.dumps(payload or {}),
                ),
            )
            evento_id = cur.fetchone()["id"]

            for item in itens or []:
                cur.execute(
                    """
                    INSERT INTO eventos_operacionais_itens
                    (
                      evento_id, pneu_id, origem_caminhao_id, origem_posicao,
                      destino_caminhao_id, destino_posicao, km_momento, motivo, observacao
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        evento_id,
                        item.get("pneu_id"),
                        item.get("origem_caminhao_id"),
                        item.get("origem_posicao"),
                        item.get("destino_caminhao_id"),
                        item.get("destino_posicao"),
                        item.get("km_momento"),
                        item.get("motivo"),
                        item.get("observacao"),
                    ),
                )

            conn.commit()
            return evento_id
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao registrar evento operacional: {e}")
        return None
    finally:
        release_connection(conn)

def _confianca_por_role(user_role):
    role = (user_role or "").lower()
    if role == "admin" or role == "gerente":
        return 100
    if role == "borracheiro":
        return 80
    return 40

def executar_acao_tirar_pneu(cliente_id, user_id, user_role, marca_fogo, motivo, status_destino):
    """Executa retirada de pneu de forma transacional e auditavel."""
    conn = get_connection()
    if not conn:
        return False, "Falha de conexao com banco"

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
                FROM pneus
                WHERE cliente_id = %s AND UPPER(marca_fogo) = UPPER(%s)
                FOR UPDATE
                """,
                (cliente_id, marca_fogo),
            )
            pneu = cur.fetchone()
            if not pneu:
                return False, "Pneu nao encontrado"
            if pneu["status"] != "MONTADO":
                return False, "Pneu nao esta montado"
            if not pneu["caminhao_atual_id"] or not pneu["posicao_atual"]:
                return False, "Pneu montado sem origem valida (inconsistencia)"

            cur.execute(
                """
                UPDATE pneus
                SET status = %s, caminhao_atual_id = NULL, posicao_atual = NULL, data_status = %s
                WHERE id = %s
                """,
                (status_destino, datetime.now(), pneu["id"]),
            )

            cur.execute(
                """
                INSERT INTO movimentacoes
                (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, km_momento, usuario_responsavel, observacao)
                VALUES (%s, 'DESMONTAGEM', %s, %s, %s, %s, %s)
                """,
                (pneu["id"], pneu["caminhao_atual_id"], pneu["posicao_atual"], 0, user_id, motivo),
            )

            operation_key = f"tirar:{pneu['id']}:{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            payload = json.dumps({"motivo": motivo, "status_destino": status_destino})
            confianca = _confianca_por_role(user_role)

            cur.execute(
                """
                INSERT INTO eventos_operacionais
                (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
                VALUES (%s, 'TIRAR_PNEU', 'CONFIRMADO', %s, 'OFICINA', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (cliente_id, user_id, confianca, operation_key, payload),
            )
            evento_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO eventos_operacionais_itens
                (evento_id, pneu_id, origem_caminhao_id, origem_posicao, motivo)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (evento_id, pneu["id"], pneu["caminhao_atual_id"], pneu["posicao_atual"], motivo),
            )

            conn.commit()
            return True, "Retirada registrada com consistencia"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao retirar pneu: {e}"
    finally:
        release_connection(conn)

def executar_acao_colocar_pneu(cliente_id, user_id, user_role, marca_fogo, caminhao_id, posicao):
    """Executa montagem de pneu de forma transacional e auditavel."""
    conn = get_connection()
    if not conn:
        return False, "Falha de conexao com banco"

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, marca_fogo, status
                FROM pneus
                WHERE cliente_id = %s AND UPPER(marca_fogo) = UPPER(%s)
                FOR UPDATE
                """,
                (cliente_id, marca_fogo),
            )
            pneu = cur.fetchone()
            if not pneu:
                return False, "Pneu nao encontrado"
            if pneu["status"] not in ["ESTOQUE", "RECAPAGEM"]:
                return False, "Pneu nao esta disponivel para montagem"

            cur.execute(
                """
                SELECT id, km_atual FROM caminhoes
                WHERE id = %s AND cliente_id = %s
                FOR UPDATE
                """,
                (caminhao_id, cliente_id),
            )
            cam = cur.fetchone()
            if not cam:
                return False, "Caminhao invalido para este cliente"

            cur.execute(
                """
                SELECT id
                FROM pneus
                WHERE caminhao_atual_id = %s AND posicao_atual = %s AND status = 'MONTADO'
                FOR UPDATE
                """,
                (caminhao_id, posicao),
            )
            ocupado = cur.fetchone()
            if ocupado:
                return False, "Posicao ocupada"

            cur.execute(
                """
                UPDATE pneus
                SET status = 'MONTADO', caminhao_atual_id = %s, posicao_atual = %s, data_status = %s
                WHERE id = %s
                """,
                (caminhao_id, posicao, datetime.now(), pneu["id"]),
            )

            cur.execute(
                """
                INSERT INTO movimentacoes
                (pneu_id, tipo_movimento, destino_caminhao_id, destino_posicao, km_momento, usuario_responsavel)
                VALUES (%s, 'MONTAGEM', %s, %s, %s, %s)
                """,
                (pneu["id"], caminhao_id, posicao, cam["km_atual"] or 0, user_id),
            )

            operation_key = f"colocar:{pneu['id']}:{caminhao_id}:{posicao}:{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            payload = json.dumps({"caminhao_id": str(caminhao_id), "posicao": posicao})
            confianca = _confianca_por_role(user_role)

            cur.execute(
                """
                INSERT INTO eventos_operacionais
                (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
                VALUES (%s, 'COLOCAR_PNEU', 'CONFIRMADO', %s, 'OFICINA', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (cliente_id, user_id, confianca, operation_key, payload),
            )
            evento_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO eventos_operacionais_itens
                (evento_id, pneu_id, destino_caminhao_id, destino_posicao, km_momento)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (evento_id, pneu["id"], caminhao_id, posicao, cam["km_atual"] or 0),
            )

            conn.commit()
            return True, "Montagem registrada com consistencia"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao montar pneu: {e}"
    finally:
        release_connection(conn)

def executar_acao_trocar_posicao(cliente_id, user_id, user_role, marca_fogo_a, marca_fogo_b):
    """Executa troca de posicao entre dois pneus no mesmo veiculo."""
    conn = get_connection()
    if not conn:
        return False, "Falha de conexao com banco"

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
                FROM pneus
                WHERE cliente_id = %s
                  AND UPPER(marca_fogo) IN (UPPER(%s), UPPER(%s))
                FOR UPDATE
                """,
                (cliente_id, marca_fogo_a, marca_fogo_b),
            )
            rows = cur.fetchall()
            if len(rows) != 2:
                return False, "Nao foi possivel localizar os dois pneus"

            p1 = rows[0]
            p2 = rows[1]
            if p1["marca_fogo"].upper() == marca_fogo_b.upper():
                p1, p2 = p2, p1

            if p1["status"] != "MONTADO" or p2["status"] != "MONTADO":
                return False, "Os dois pneus precisam estar montados"
            if p1["caminhao_atual_id"] != p2["caminhao_atual_id"]:
                return False, "Pneus em veiculos diferentes"
            if p1["posicao_atual"] == p2["posicao_atual"]:
                return False, "Pneus na mesma posicao"

            cur.execute("UPDATE pneus SET posicao_atual = 'TEMP' WHERE id = %s", (p1["id"],))
            cur.execute("UPDATE pneus SET posicao_atual = %s WHERE id = %s", (p1["posicao_atual"], p2["id"]))
            cur.execute("UPDATE pneus SET posicao_atual = %s WHERE id = %s", (p2["posicao_atual"], p1["id"]))

            cur.execute(
                """
                INSERT INTO movimentacoes
                (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, destino_posicao, km_momento, usuario_responsavel)
                VALUES (%s, 'RODIZIO', %s, %s, %s, %s, %s)
                """,
                (p1["id"], p1["caminhao_atual_id"], p1["posicao_atual"], p2["posicao_atual"], 0, user_id),
            )

            operation_key = f"trocar:{p1['id']}:{p2['id']}:{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            payload = json.dumps({"caminhao_id": str(p1["caminhao_atual_id"])})
            confianca = _confianca_por_role(user_role)

            cur.execute(
                """
                INSERT INTO eventos_operacionais
                (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
                VALUES (%s, 'TROCAR_POSICAO', 'CONFIRMADO', %s, 'OFICINA', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (cliente_id, user_id, confianca, operation_key, payload),
            )
            evento_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO eventos_operacionais_itens
                (evento_id, pneu_id, origem_caminhao_id, origem_posicao, destino_caminhao_id, destino_posicao)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (evento_id, p1["id"], p1["caminhao_atual_id"], p1["posicao_atual"], p1["caminhao_atual_id"], p2["posicao_atual"]),
            )
            cur.execute(
                """
                INSERT INTO eventos_operacionais_itens
                (evento_id, pneu_id, origem_caminhao_id, origem_posicao, destino_caminhao_id, destino_posicao)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (evento_id, p2["id"], p2["caminhao_atual_id"], p2["posicao_atual"], p2["caminhao_atual_id"], p1["posicao_atual"]),
            )

            conn.commit()
            return True, "Troca registrada com consistencia"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao trocar posicao: {e}"
    finally:
        release_connection(conn)

def executar_acao_enviar_recapagem(cliente_id, user_id, user_role, recapadora, codigos):
    """Envia lote para recapagem de forma transacional."""
    conn = get_connection()
    if not conn:
        return False, "Falha de conexao com banco", None
    try:
        codigos_limpos = [c.strip().upper() for c in codigos if c and c.strip()]
        if not codigos_limpos:
            return False, "Nenhum pneu informado", None

        with conn.cursor() as cur:
            ordem_id = f"REC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cur.execute(
                """
                INSERT INTO ordens_recapagem
                (ordem_id, recapadora_nome, status, data_criacao, usuario_responsavel, cliente_id)
                VALUES (%s, %s, 'enviado', %s, %s, %s)
                """,
                (ordem_id, recapadora, datetime.now(), user_id, cliente_id),
            )

            pneus_ok = []
            for codigo in codigos_limpos:
                cur.execute(
                    """
                    SELECT id, status
                    FROM pneus
                    WHERE cliente_id = %s AND UPPER(marca_fogo) = UPPER(%s)
                    FOR UPDATE
                    """,
                    (cliente_id, codigo),
                )
                pneu = cur.fetchone()
                if not pneu:
                    continue
                if pneu["status"] == "SUCATA":
                    continue

                cur.execute(
                    """
                    UPDATE pneus
                    SET status='RECAPAGEM', caminhao_atual_id=NULL, posicao_atual=NULL, data_status=%s
                    WHERE id=%s
                    """,
                    (datetime.now(), pneu["id"]),
                )
                cur.execute(
                    """
                    INSERT INTO ordens_recapagem_pneus (ordem_id, pneu_id, data_adicionada)
                    VALUES (%s, %s, %s)
                    """,
                    (ordem_id, pneu["id"], datetime.now()),
                )
                pneus_ok.append(pneu["id"])

            if not pneus_ok:
                conn.rollback()
                return False, "Nenhum pneu valido para recapagem", None

            operation_key = f"recapagem:{ordem_id}"
            payload = json.dumps({"ordem_id": ordem_id, "recapadora": recapadora})
            confianca = _confianca_por_role(user_role)
            cur.execute(
                """
                INSERT INTO eventos_operacionais
                (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
                VALUES (%s, 'ENVIAR_RECAPAGEM', 'CONFIRMADO', %s, 'OFICINA', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (cliente_id, user_id, confianca, operation_key, payload),
            )
            evento_id = cur.fetchone()["id"]

            for pid in pneus_ok:
                cur.execute(
                    """
                    INSERT INTO eventos_operacionais_itens (evento_id, pneu_id, motivo)
                    VALUES (%s, %s, 'ENVIAR_RECAPAGEM')
                    """,
                    (evento_id, pid),
                )

            conn.commit()
            return True, f"Lote enviado: {len(pneus_ok)} pneus | Ordem {ordem_id}", ordem_id
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao enviar recapagem: {e}", None
    finally:
        release_connection(conn)

def diagnosticar_consistencia(cliente_id):
    """Retorna diagnostico de inconsistencias de dados operacionais."""
    inconsistencias = {
        "montado_sem_vinculo": [],
        "nao_montado_com_vinculo": [],
        "posicao_duplicada_montado": [],
    }

    inconsistencias["montado_sem_vinculo"] = run_query(
        """
        SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
        FROM pneus
        WHERE cliente_id = %s
          AND status = 'MONTADO'
          AND (caminhao_atual_id IS NULL OR posicao_atual IS NULL)
        ORDER BY marca_fogo
        """,
        (cliente_id,),
    ) or []

    inconsistencias["nao_montado_com_vinculo"] = run_query(
        """
        SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
        FROM pneus
        WHERE cliente_id = %s
          AND status <> 'MONTADO'
          AND (caminhao_atual_id IS NOT NULL OR posicao_atual IS NOT NULL)
        ORDER BY marca_fogo
        """,
        (cliente_id,),
    ) or []

    inconsistencias["posicao_duplicada_montado"] = run_query(
        """
        SELECT caminhao_atual_id, posicao_atual, COUNT(*) AS total
        FROM pneus
        WHERE cliente_id = %s
          AND status = 'MONTADO'
          AND caminhao_atual_id IS NOT NULL
          AND posicao_atual IS NOT NULL
        GROUP BY caminhao_atual_id, posicao_atual
        HAVING COUNT(*) > 1
        ORDER BY total DESC
        """,
        (cliente_id,),
    ) or []

    resumo = {
        "montado_sem_vinculo": len(inconsistencias["montado_sem_vinculo"]),
        "nao_montado_com_vinculo": len(inconsistencias["nao_montado_com_vinculo"]),
        "posicao_duplicada_montado": len(inconsistencias["posicao_duplicada_montado"]),
    }
    resumo["total"] = (
        resumo["montado_sem_vinculo"]
        + resumo["nao_montado_com_vinculo"]
        + resumo["posicao_duplicada_montado"]
    )
    return {"resumo": resumo, "detalhes": inconsistencias}

def reconciliar_inconsistencias_seguras(cliente_id, user_id, user_role):
    """
    Corrige apenas inconsistencias deterministicas:
    1) status='MONTADO' sem caminhao/posicao -> volta para ESTOQUE
    2) status<>'MONTADO' com caminhao/posicao -> limpa vinculos
    Nao corrige duplicidade de posicao automaticamente.
    """
    conn = get_connection()
    if not conn:
        return False, "Falha de conexao com banco", None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
                FROM pneus
                WHERE cliente_id = %s
                  AND status = 'MONTADO'
                  AND (caminhao_atual_id IS NULL OR posicao_atual IS NULL)
                FOR UPDATE
                """,
                (cliente_id,),
            )
            corrigir_para_estoque = cur.fetchall()

            cur.execute(
                """
                SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
                FROM pneus
                WHERE cliente_id = %s
                  AND status <> 'MONTADO'
                  AND (caminhao_atual_id IS NOT NULL OR posicao_atual IS NOT NULL)
                FOR UPDATE
                """,
                (cliente_id,),
            )
            limpar_vinculos = cur.fetchall()

            if not corrigir_para_estoque and not limpar_vinculos:
                return True, "Nenhuma inconsistencia segura para corrigir", {
                    "corrigidos_para_estoque": 0,
                    "vinculos_limpos": 0,
                }

            itens_evento = []

            for p in corrigir_para_estoque:
                cur.execute(
                    """
                    UPDATE pneus
                    SET status = 'ESTOQUE', caminhao_atual_id = NULL, posicao_atual = NULL, data_status = %s
                    WHERE id = %s
                    """,
                    (datetime.now(), p["id"]),
                )
                itens_evento.append(
                    {
                        "pneu_id": p["id"],
                        "motivo": "RECONCILIACAO_MONTADO_SEM_VINCULO",
                        "observacao": f"Marca {p['marca_fogo']}",
                    }
                )

            for p in limpar_vinculos:
                cur.execute(
                    """
                    UPDATE pneus
                    SET caminhao_atual_id = NULL, posicao_atual = NULL, data_status = %s
                    WHERE id = %s
                    """,
                    (datetime.now(), p["id"]),
                )
                itens_evento.append(
                    {
                        "pneu_id": p["id"],
                        "motivo": "RECONCILIACAO_NAO_MONTADO_COM_VINCULO",
                        "observacao": f"Marca {p['marca_fogo']}",
                    }
                )

            operation_key = f"reconciliacao:{cliente_id}:{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            payload = json.dumps(
                {
                    "corrigidos_para_estoque": len(corrigir_para_estoque),
                    "vinculos_limpos": len(limpar_vinculos),
                }
            )
            confianca = _confianca_por_role(user_role)

            cur.execute(
                """
                INSERT INTO eventos_operacionais
                (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
                VALUES (%s, 'AJUSTE_GESTOR', 'CONFIRMADO', %s, 'GESTOR', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (cliente_id, user_id, confianca, operation_key, payload),
            )
            evento_id = cur.fetchone()["id"]

            for item in itens_evento:
                cur.execute(
                    """
                    INSERT INTO eventos_operacionais_itens
                    (evento_id, pneu_id, motivo, observacao)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (evento_id, item["pneu_id"], item["motivo"], item["observacao"]),
                )

            conn.commit()
            return True, "Reconciliacao segura concluida", {
                "corrigidos_para_estoque": len(corrigir_para_estoque),
                "vinculos_limpos": len(limpar_vinculos),
                "evento_id": str(evento_id),
            }
    except Exception as e:
        conn.rollback()
        return False, f"Erro na reconciliacao: {e}", None
    finally:
        release_connection(conn)

# ============ VALIDAÇÕES ============

def validar_cadastro_pneu(dados):
    """Valida dados antes de cadastrar um pneu"""
    required_fields = ['pneu_id', 'tamanho', 'veiculo_id']
    
    for field in required_fields:
        if field not in dados or dados[field] is None:
            raise ValueError(f"Campo obrigatório faltando: {field}")
    
    tamanhos_validos = ['295/80R22.5', '275/80R22.5', '11.00R22', '12R22.5', '185/65R15', '195/60R15', '225/70R15', '235/75R17']
    if dados['tamanho'] not in tamanhos_validos:
        raise ValueError(f"Tamanho inválido. Válidos: {tamanhos_validos}")
    
    existing = run_query("SELECT id FROM pneus WHERE marca_fogo = %s", (dados['pneu_id'],))
    if existing:
        raise ValueError(f"Pneu ID {dados['pneu_id']} já existe")
    
    return True

def validar_movimento(dados):
    """Valida dados de movimento de pneu"""
    required = ['pneu_id', 'acao', 'posicao_nova']
    
    for field in required:
        if field not in dados:
            raise ValueError(f"Campo faltando: {field}")
    
    acoes_validas = ['montar', 'desmontar', 'mover_repouso', 'mover_recapagem']
    if dados['acao'] not in acoes_validas:
        raise ValueError(f"Ação inválida: {dados['acao']}")
    
    posicoes_validas = ['FL', 'FR', 'TL_OUT', 'TL_IN', 'TR_IN', 'TR_OUT', 'RL_OUT', 'RL_IN', 'RR_IN', 'RR_OUT', 'REPOUSO', 'RECAPAGEM']
    if dados['posicao_nova'] not in posicoes_validas:
        raise ValueError(f"Posição inválida: {dados['posicao_nova']}")
    
    tire = run_query("SELECT id FROM pneus WHERE marca_fogo = %s", (dados['pneu_id'],))
    if not tire:
        raise ValueError(f"Pneu não encontrado: {dados['pneu_id']}")
    
    return True

# ============ LOGS E AUDITORIA ============

def registrar_log_auditoria(usuario_id, acao, tabela, registro_id, detalhes=None):
    """Registra ação de auditoria no banco (usuario_id deve ser UUID)"""
    query = """
    INSERT INTO auditoria_log (usuario_id, acao, tabela, registro_id, detalhes, data_hora)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (usuario_id, acao, tabela, registro_id, detalhes, datetime.now())
    return run_query(query, params)

# ============ OPERAÇÕES DE PNEUS ============

def get_pneu_by_id(pneu_id):
    """Retorna dados completos de um pneu"""
    query = """
    SELECT id, marca_fogo, marca, medida, status, ciclo_atual, km_vida_total, 
           months_alive, caminhao_atual_id, posicao_atual, ciclos_sem_rodizio, 
           data_status, custo_aquisicao
    FROM pneus 
    WHERE id = %s
    """
    result = run_query(query, (pneu_id,))
    return result[0] if result else None

def get_pneus_by_veiculo(veiculo_id, status=None):
    """Retorna todos os pneus de um veículo"""
    if status:
        query = """
        SELECT * FROM pneus 
        WHERE caminhao_atual_id = %s AND status = %s
        ORDER BY posicao_atual
        """
        return run_query(query, (veiculo_id, status))
    else:
        query = """
        SELECT * FROM pneus 
        WHERE caminhao_atual_id = %s
        ORDER BY posicao_atual
        """
        return run_query(query, (veiculo_id,))

def atualizar_posicao_pneu(pneu_id, nova_posicao, veiculo_id=None):
    """Atualiza posição de um pneu"""
    query = """
    UPDATE pneus 
    SET posicao_atual = %s, caminhao_atual_id = %s, data_status = %s
    WHERE id = %s
    """
    params = (nova_posicao, veiculo_id, datetime.now(), pneu_id)
    return run_query(query, params)

def atualizar_status_pneu(pneu_id, novo_status):
    """Atualiza status de um pneu"""
    query = """
    UPDATE pneus 
    SET status = %s, data_status = %s
    WHERE id = %s
    """
    params = (novo_status, datetime.now(), pneu_id)
    return run_query(query, params)

# ============ OPERAÇÕES DE ALERTAS ============

def criar_alerta(alert_id, tipo, severidade, pneu_id, mensagem, acao, criado_por):
    """Cria um novo alerta"""
    query = """
    INSERT INTO alertas_log (alert_id, tipo, severidade, pneu_id, mensagem, acao, data_criacao, criado_por, resolvido)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
    """
    params = (alert_id, tipo, severidade, pneu_id, mensagem, acao, datetime.now(), criado_por)
    return run_query(query, params)

def resolver_alerta(alert_id):
    """Marca um alerta como resolvido"""
    query = """
    UPDATE alertas_log 
    SET resolvido = TRUE, data_resolucao = %s
    WHERE alert_id = %s OR alerta_id = %s
    """
    params = (datetime.now(), alert_id, alert_id)
    return run_query(query, params)

def listar_alertas_ativos():
    """Lista todos os alertas não resolvidos"""
    query = """
    SELECT * FROM alertas_log 
    WHERE resolvido = FALSE
    ORDER BY 
        CASE 
            WHEN severidade = 'CRITICO' THEN 0
            WHEN severidade = 'ALTO' THEN 1
            WHEN severidade = 'MEDIO' THEN 2
            ELSE 3
        END,
        data_criacao DESC
    """
    return run_query(query)

# ============ OPERAÇÕES DE ORDENS ============

def criar_ordem_recapagem(ordem_id, recapadora_nome, usuario_id, cliente_id=None):
    """Cria uma nova ordem de recapagem"""
    query = """
    INSERT INTO ordens_recapagem (ordem_id, recapadora_nome, status, data_criacao, usuario_responsavel, cliente_id)
    VALUES (%s, %s, 'enviado', %s, %s, %s)
    """
    params = (ordem_id, recapadora_nome, datetime.now(), usuario_id, cliente_id)
    return run_query(query, params)

def adicionar_pneu_ordem(ordem_id, pneu_id):
    """Adiciona um pneu a uma ordem de recapagem"""
    query = """
    INSERT INTO ordens_recapagem_pneus (ordem_id, pneu_id, data_adicionada)
    VALUES (%s, %s, %s)
    """
    params = (ordem_id, pneu_id, datetime.now())
    return run_query(query, params)

def atualizar_status_ordem(ordem_id, novo_status):
    """Atualiza status de uma ordem"""
    query = """
    UPDATE ordens_recapagem 
    SET status = %s, data_ultima_atualizacao = %s
    WHERE ordem_id = %s
    """
    params = (novo_status, datetime.now(), ordem_id)
    return run_query(query, params)

def obter_ordem(ordem_id):
    """Obtém dados de uma ordem"""
    query = """
    SELECT * FROM ordens_recapagem 
    WHERE ordem_id = %s
    """
    result = run_query(query, (ordem_id,))
    return result[0] if result else None

# ============ OPERAÇÕES CPK ============

def registrar_cpk_historico(cpk_valor, media, desvio, quantidade_pneus, status, recomendacao, cliente_id=None):
    """Registra calculo de CPK no historico"""
    query = """
    INSERT INTO cpk_historico (data_calculo, cpk_valor, media, desvio, quantidade_pneus, status, recomendacao, cliente_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (datetime.now(), cpk_valor, media, desvio, quantidade_pneus, status, recomendacao, cliente_id)
    return run_query(query, params)

def obter_historico_cpk(limite=10):
    """Obtém histórico recente de CPK"""
    query = """
    SELECT * FROM cpk_historico 
    ORDER BY data_calculo DESC 
    LIMIT %s
    """
    return run_query(query, (limite,))

# ============ VIEWS ============

def obter_alertas_ativos_view():
    """Consulta view de alertas ativos (ordenados por prioridade)"""
    query = "SELECT * FROM alertas_ativos"
    return run_query(query)

def obter_pneus_em_risco_view():
    """Consulta view de pneus em risco"""
    query = "SELECT * FROM pneus_em_risco"
    return run_query(query)

def get_todos_clientes():
    """Retorna lista de todos os clientes para o Admin selecionar"""
    return run_query("SELECT id, nome_empresa, nome_fantasia FROM clientes ORDER BY nome_empresa")

def get_detalhes_cliente(cliente_id):
    """Busca dados completos de um cliente específico"""
    query = """
        SELECT id, nome_empresa, nome_fantasia, nome_responsavel, 
               contato_responsavel, data_cadastro
        FROM clientes 
        WHERE id = %s
    """
    res = run_query(query, (cliente_id,))
    return res[0] if res else None

def atualizar_dados_cliente(cliente_id, dados):
    """Atualiza cadastro da empresa"""
    try:
        query = """
            UPDATE clientes 
            SET nome_empresa=%s, nome_fantasia=%s, nome_responsavel=%s, contato_responsavel=%s
            WHERE id = %s
        """
        params = (
            dados['nome_empresa'], 
            dados['nome_fantasia'], 
            dados['nome_responsavel'], 
            dados['contato_responsavel'], 
            cliente_id
        )
        return run_query(query, params)
    except Exception as e:
        st.error(f"Erro ao atualizar cliente: {e}")
        return False

