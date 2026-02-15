"""
TYRECONTROL API - FastAPI Backend
Objetivo: Fornecer endpoints para integracao com recapadoras e operacoes externas.
"""

from datetime import datetime
import base64
import json
import os
import re
from typing import List, Optional

import psycopg2
import psycopg2.extras
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="TyreControl API",
    version="1.1.0",
    description="API para gestao de pneus e integracao com terceiros",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_connection():
    """Obtem conexao com Supabase PostgreSQL"""
    try:
        return psycopg2.connect(
            os.getenv("SUPABASE_URL"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    except Exception as e:
        print(f"Erro de conexao: {e}")
        return None


class RecappingOrderModel(BaseModel):
    cliente_id: str
    tire_ids: List[str]
    recapper_name: str
    usuario_id: Optional[str] = None


class RecappingStatusModel(BaseModel):
    status: str
    observation: Optional[str] = None

def _extract_fire_marks_from_text(text):
    """Fallback regex parser for DOT/brand-fire marks."""
    if not text:
        return []
    candidates = re.findall(r"\b[A-Z0-9-]{6,20}\b", text.upper())
    invalid = {"DOT", "PNEU", "TIRE", "MARCA", "FOGO", "UNKNOWN", "NENHUM"}
    return [c for c in candidates if c not in invalid]

def _scan_with_openai(image_bytes, content_type):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY nao configurada")

    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{content_type};base64,{image_b64}"

    prompt = (
        "Leia esta foto de pneu e extraia a marcacao de fogo/DOT visivel. "
        "Retorne JSON estrito no formato: "
        '{"marca_fogo":"...", "dot":"...", "confidence":0.0, "raw_text":"..."} '
        "Se nao conseguir, use null em marca_fogo e dot."
    )

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    )

    output_text = getattr(response, "output_text", "") or ""
    parsed = None
    try:
        parsed = json.loads(output_text)
    except Exception:
        parsed = None

    if parsed:
        return {
            "provider": "openai",
            "marca_fogo": parsed.get("marca_fogo"),
            "dot": parsed.get("dot"),
            "confidence": float(parsed.get("confidence") or 0),
            "raw_text": parsed.get("raw_text") or output_text,
        }

    marks = _extract_fire_marks_from_text(output_text)
    return {
        "provider": "openai",
        "marca_fogo": marks[0] if marks else None,
        "dot": None,
        "confidence": 0.4 if marks else 0.0,
        "raw_text": output_text,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "1.1.0",
    }

@app.post("/api/scan/pneu")
async def scan_pneu(file: UploadFile = File(...), provider: str = "openai"):
    if not file:
        raise HTTPException(status_code=400, detail="Arquivo obrigatorio")

    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Envie um arquivo de imagem")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Imagem vazia")
    if len(image_bytes) > 6 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem muito grande (max 6MB)")

    try:
        if provider != "openai":
            raise HTTPException(status_code=400, detail="Provider de scan nao suportado")

        result = _scan_with_openai(image_bytes, content_type)
        return {
            "status": "ok",
            "result": result,
            "filename": file.filename,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha no scan: {e}")


@app.post("/api/operacoes/rodicao/sugerir")
async def sugerir_rodicio(veiculo_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, marca_fogo, km_vida_total, ciclo_atual, posicao_atual
                FROM pneus
                WHERE caminhao_atual_id = %s AND status = 'MONTADO'
                ORDER BY km_vida_total DESC
                """,
                (veiculo_id,),
            )
            pneus_montados = cur.fetchall()

            cur.execute(
                """
                SELECT id, marca_fogo, km_vida_total, ciclo_atual
                FROM pneus
                WHERE status = 'ESTOQUE' AND caminhao_atual_id IS NULL
                LIMIT 5
                """
            )
            pneus_repouso = cur.fetchall()

        if not pneus_montados or not pneus_repouso:
            raise HTTPException(status_code=400, detail="Pneus insuficientes para rodizio")

        sugestoes = []
        for pneu_montado in pneus_montados[:2]:
            for pneu_repouso in pneus_repouso:
                economia = (
                    (pneu_montado["km_vida_total"] - pneu_repouso["km_vida_total"])
                    / pneu_montado["km_vida_total"]
                    * 100
                ) if pneu_montado["km_vida_total"] > 0 else 0

                if economia > 5:
                    sugestoes.append(
                        {
                            "trocar_de": pneu_montado["marca_fogo"],
                            "trocar_para": pneu_repouso["marca_fogo"],
                            "posicao": pneu_montado["posicao_atual"],
                            "economia_percentual": round(economia, 1),
                        }
                    )
                    break

        return {
            "status": "success",
            "sugestoes": sugestoes,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.post("/api/operacoes/rodicao/executar")
async def executar_rodicio(veiculo_id: str, rodicio_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM rodizio_registro
                WHERE id = %s AND veiculo_id = %s
                """,
                (rodicio_id, veiculo_id),
            )
            rodizio = cur.fetchone()
            if not rodizio:
                raise HTTPException(status_code=404, detail="Rodizio nao encontrado")

            cur.execute(
                """
                UPDATE rodizio_registro
                SET status = 'completo'
                WHERE id = %s
                """,
                (rodicio_id,),
            )
            conn.commit()

        return {
            "status": "success",
            "rodicio_id": rodicio_id,
            "mensagem": "Rodizio executado com sucesso",
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.post("/api/recapagem/enviar")
async def enviar_recapagem(pedido: RecappingOrderModel):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    try:
        with conn.cursor() as cur:
            ordem_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            cur.execute(
                """
                INSERT INTO ordens_recapagem
                (ordem_id, recapadora_nome, status, data_criacao, data_entrega_esperada, usuario_responsavel, cliente_id)
                VALUES (%s, %s, 'enviado', NOW(), NOW() + INTERVAL '14 days', %s, %s)
                """,
                (ordem_id, pedido.recapper_name, pedido.usuario_id, pedido.cliente_id),
            )

            for tire_id in pedido.tire_ids:
                cur.execute(
                    """
                    UPDATE pneus
                    SET status = 'RECAPAGEM', caminhao_atual_id = NULL, posicao_atual = NULL
                    WHERE id = %s AND cliente_id = %s
                    """,
                    (tire_id, pedido.cliente_id),
                )
                cur.execute(
                    """
                    INSERT INTO ordens_recapagem_pneus (ordem_id, pneu_id, data_adicionada)
                    VALUES (%s, %s, NOW())
                    """,
                    (ordem_id, tire_id),
                )

            conn.commit()

        return {
            "status": "success",
            "ordem_id": ordem_id,
            "tires_sent": len(pedido.tire_ids),
            "recapper": pedido.recapper_name,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.get("/api/recapagem/ordem/{ordem_id}/status")
async def rastrear_ordem(ordem_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM ordens_recapagem
                WHERE ordem_id = %s
                """,
                (ordem_id,),
            )
            ordem = cur.fetchone()
            if not ordem:
                raise HTTPException(status_code=404, detail="Ordem nao encontrada")

            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM ordens_recapagem_pneus
                WHERE ordem_id = %s
                """,
                (ordem_id,),
            )
            count = cur.fetchone()["total"]

        dias_decorridos = (datetime.now() - ordem["data_criacao"]).days
        dias_totais = (ordem["data_entrega_esperada"] - ordem["data_criacao"]).days
        percentual = min((dias_decorridos / dias_totais * 100) if dias_totais > 0 else 0, 100)

        return {
            "ordem_id": ordem_id,
            "status": ordem["status"],
            "recapadora": ordem["recapadora_nome"],
            "pneus_total": count,
            "data_envio": ordem["data_criacao"].isoformat(),
            "data_esperada": ordem["data_entrega_esperada"].isoformat(),
            "dias_decorridos": dias_decorridos,
            "percentual_progresso": round(percentual, 1),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.put("/api/recapagem/ordem/{ordem_id}/status")
async def atualizar_status_recapagem(ordem_id: str, dados: RecappingStatusModel):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ordens_recapagem
                SET status = %s, data_ultima_atualizacao = NOW()
                WHERE ordem_id = %s
                """,
                (dados.status, ordem_id),
            )

            if dados.status == "concluido":
                cur.execute(
                    """
                    UPDATE pneus
                    SET status = 'ESTOQUE'
                    WHERE id IN (
                        SELECT pneu_id
                        FROM ordens_recapagem_pneus
                        WHERE ordem_id = %s
                    )
                    """,
                    (ordem_id,),
                )

            conn.commit()

        return {
            "status": "atualizado",
            "ordem_id": ordem_id,
            "novo_status": dados.status,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.get("/api/relatorios/cpk")
async def get_cpk_report(cliente_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT km_vida_total, ciclo_atual
                FROM pneus
                WHERE cliente_id = %s AND status = 'MONTADO'
                """,
                (cliente_id,),
            )
            tires = cur.fetchall()

        if not tires:
            raise HTTPException(status_code=400, detail="Sem pneus montados para analise")

        vidas = [t["km_vida_total"] for t in tires]
        media = sum(vidas) / len(vidas)
        desvio = (sum((x - media) ** 2 for x in vidas) / len(vidas)) ** 0.5

        usl = 70000
        lsl = 12000

        if desvio == 0:
            cpk = float("inf")
        else:
            cpk_superior = (usl - media) / (3 * desvio)
            cpk_inferior = (media - lsl) / (3 * desvio)
            cpk = min(cpk_superior, cpk_inferior)

        if cpk > 1.67:
            status = "EXCELENTE"
            recomendacao = "Continue o processo atual. Manter padrao."
        elif cpk > 1.33:
            status = "ADEQUADO"
            recomendacao = "Monitorar mensalmente. Tudo dentro do esperado."
        elif cpk > 1.0:
            status = "ATENCAO"
            recomendacao = "Revisar procedimentos. Aumentar frequencia de rodizio."
        else:
            status = "CRITICO"
            recomendacao = "ACAO IMEDIATA! Processo fora de controle."

        percentual_dentro_spec = sum(1 for v in vidas if lsl <= v <= usl) / len(vidas) * 100

        return {
            "cpk": round(cpk, 2),
            "media": round(media, 1),
            "desvio": round(desvio, 1),
            "status": status,
            "recomendacao": recomendacao,
            "minimo": lsl,
            "maximo": usl,
            "percentual_dentro_spec": round(percentual_dentro_spec, 1),
            "total_tires": len(tires),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.get("/api/alertas")
async def get_alertas(cliente_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    alertas = []

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, marca_fogo, ciclo_atual, km_vida_total
                FROM pneus
                WHERE cliente_id = %s AND status = 'MONTADO' AND ciclo_atual > 4
                ORDER BY ciclo_atual DESC
                """,
                (cliente_id,),
            )
            pneus_velhos = cur.fetchall()
            for p in pneus_velhos:
                alertas.append(
                    {
                        "id": f"VELHO_{p['id']}",
                        "tipo": "PNEU_ENVELHECIDO",
                        "severidade": "CRITICO",
                        "pneu_id": p["marca_fogo"],
                        "mensagem": f"Pneu com {p['ciclo_atual']} ciclos. Limite recomendado: 4",
                        "acao": "Enviar para recapagem ou sucata",
                    }
                )

            cur.execute(
                """
                SELECT id, marca_fogo, posicao_atual
                FROM pneus
                WHERE cliente_id = %s AND status = 'MONTADO'
                ORDER BY id DESC LIMIT 10
                """,
                (cliente_id,),
            )
            pneus_sem_rodizio = cur.fetchall()
            for p in pneus_sem_rodizio[:2]:
                alertas.append(
                    {
                        "id": f"RODIZIO_{p['id']}",
                        "tipo": "RODIZIO_ATRASADO",
                        "severidade": "ALTO",
                        "pneu_id": p["marca_fogo"],
                        "mensagem": f"Pneu na posicao {p['posicao_atual']} por muito tempo",
                        "acao": "Incluir em proximo rodizio",
                    }
                )

        ordem_severidade = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2}
        alertas.sort(key=lambda x: ordem_severidade.get(x["severidade"], 3))

        return {
            "alertas": alertas,
            "total": len(alertas),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.post("/api/alertas/{alerta_id}/resolver")
async def resolver_alerta(alerta_id: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexao com banco falhou")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alertas_log
                SET resolvido = TRUE, data_resolucao = NOW()
                WHERE alerta_id = %s OR alert_id = %s
                """,
                (alerta_id, alerta_id),
            )

            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Alerta nao encontrado")

            conn.commit()

        return {"status": "resolvido", "alerta_id": alerta_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@app.post("/api/validacao/pneu")
async def validar_pneu(dados: dict):
    required_fields = ["marca_fogo", "tamanho", "marca"]
    for field in required_fields:
        if field not in dados or dados[field] is None:
            raise HTTPException(status_code=400, detail=f"Campo obrigatorio faltando: {field}")

    tamanhos_validos = ["295/80R22.5", "275/80R22.5", "11.00R22", "12R22.5"]
    if dados["tamanho"] not in tamanhos_validos:
        raise HTTPException(status_code=400, detail="Tamanho invalido")

    return {"status": "validado", "dados": dados}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
