"""
TYRECONTROL API - FastAPI Backend
Arquivo: api.py
Objetivo: Fornecer endpoints para integração com recapadoras, fornecedores e sistemas externos
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import json

load_dotenv()

app = FastAPI(
    title="TyreControl API",
    version="1.0.0",
    description="API para gestão de pneus e integração com terceiros"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== DATABASE CONNECTION ====================

def get_db_connection():
    """Obtém conexão com Supabase PostgreSQL"""
    try:
        conn = psycopg2.connect(
            os.getenv("SUPABASE_URL"),
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

# ==================== PYDANTIC MODELS ====================

class TireModel(BaseModel):
    tire_id: str
    brand: str
    size: str
    condition: str

class RecappingOrderModel(BaseModel):
    tire_ids: List[str]
    recapper_name: str
    notes: Optional[str] = None

class RecappingStatusModel(BaseModel):
    status: str  # em_processo, pronto, entregue
    observation: Optional[str] = None

class AlertaModel(BaseModel):
    tipo: str
    pneu_id: Optional[str] = None
    veiculo_id: Optional[str] = None
    mensagem: str
    acao: str
    severidade: str

# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Verifica se a API está rodando"""
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# ==================== ENDPOINTS DE RODÍZIO ====================

@app.post("/api/operacoes/rodicao/sugerir")
async def sugerir_rodicio(veiculo_id: str):
    """
    Sugere rodízio automático baseado em desgaste
    
    Input: veiculo_id
    Output: Lista de sugestões de troca
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    try:
        with conn.cursor() as cur:
            # Pneus montados
            cur.execute("""
                SELECT id, marca_fogo, km_vida_total, ciclo_atual, posicao_atual
                FROM pneus 
                WHERE caminhao_atual_id = %s AND status = 'MONTADO'
                ORDER BY km_vida_total DESC
            """, (veiculo_id,))
            pneus_montados = cur.fetchall()
            
            # Pneus em repouso
            cur.execute("""
                SELECT id, marca_fogo, km_vida_total, ciclo_atual
                FROM pneus 
                WHERE status = 'ESTOQUE' AND caminhao_atual_id IS NULL
                LIMIT 5
            """)
            pneus_repouso = cur.fetchall()
        
        if not pneus_montados or not pneus_repouso:
            raise HTTPException(status_code=400, detail="Pneus insuficientes para rodízio")
        
        # Calcular sugestões
        sugestoes = []
        for pneu_montado in pneus_montados[:2]:  # Top 2 mais desgastados
            for pneu_repouso in pneus_repouso:
                economia = (
                    (pneu_montado['km_vida_total'] - pneu_repouso['km_vida_total']) / 
                    pneu_montado['km_vida_total'] * 100
                ) if pneu_montado['km_vida_total'] > 0 else 0
                
                if economia > 5:  # Mínimo 5% de economia
                    sugestoes.append({
                        "trocar_de": pneu_montado['marca_fogo'],
                        "trocar_para": pneu_repouso['marca_fogo'],
                        "posicao": pneu_montado['posicao_atual'],
                        "economia_percentual": round(economia, 1)
                    })
                    break
        
        return {
            "status": "success",
            "sugestoes": sugestoes,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.post("/api/operacoes/rodicao/executar")
async def executar_rodicio(veiculo_id: str, rodicio_id: str):
    """
    Executa um rodízio após aprovação
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    try:
        with conn.cursor() as cur:
            # Buscar detalhes do rodízio
            cur.execute("""
                SELECT * FROM ordens_rodicio 
                WHERE id = %s AND veiculo_id = %s
            """, (rodicio_id, veiculo_id))
            
            rodicio = cur.fetchone()
            if not rodicio:
                raise HTTPException(status_code=404, detail="Rodízio não encontrado")
            
            # Marcar como completo
            cur.execute("""
                UPDATE ordens_rodicio 
                SET status = 'completo', data_conclusao = NOW()
                WHERE id = %s
            """, (rodicio_id,))
            
            conn.commit()
        
        return {
            "status": "success",
            "rodicio_id": rodicio_id,
            "mensagem": "Rodízio executado com sucesso"
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# ==================== ENDPOINTS DE RECAPAGEM ====================

@app.post("/api/recapagem/enviar")
async def enviar_recapagem(pedido: RecappingOrderModel):
    """
    Envia pneus para recapagem
    
    Input: tire_ids, recapper_name
    Output: ordem_id
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    try:
        with conn.cursor() as cur:
            ordem_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Criar ordem
            cur.execute("""
                INSERT INTO ordens_recapagem 
                (ordem_id, recapadora, status, data_criacao, data_entrega_esperada, notas)
                VALUES (%s, %s, 'enviado', NOW(), NOW() + INTERVAL '14 days', %s)
            """, (ordem_id, pedido.recapper_name, pedido.notes))
            
            # Marcar pneus como em recapagem
            for tire_id in pedido.tire_ids:
                cur.execute("""
                    UPDATE pneus 
                    SET status = 'RECAPAGEM', caminhao_atual_id = NULL, posicao_atual = NULL
                    WHERE id = %s
                """, (tire_id,))
            
            conn.commit()
        
        return {
            "status": "success",
            "ordem_id": ordem_id,
            "tires_sent": len(pedido.tire_ids),
            "recapper": pedido.recapper_name,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.get("/api/recapagem/ordem/{ordem_id}/status")
async def rastrear_ordem(ordem_id: str):
    """
    Consulta status de uma ordem de recapagem
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM ordens_recapagem 
                WHERE ordem_id = %s
            """, (ordem_id,))
            
            ordem = cur.fetchone()
            if not ordem:
                raise HTTPException(status_code=404, detail="Ordem não encontrada")
            
            # Contar pneus
            cur.execute("""
                SELECT COUNT(*) as total FROM pneus 
                WHERE status = 'RECAPAGEM'
            """)
            count = cur.fetchone()['total']
        
        dias_decorridos = (datetime.now() - ordem['data_criacao']).days
        dias_totais = (ordem['data_entrega_esperada'] - ordem['data_criacao']).days
        percentual = min((dias_decorridos / dias_totais * 100) if dias_totais > 0 else 0, 100)
        
        return {
            "ordem_id": ordem_id,
            "status": ordem['status'],
            "recapadora": ordem['recapadora'],
            "pneus_total": count,
            "data_envio": ordem['data_criacao'].isoformat(),
            "data_esperada": ordem['data_entrega_esperada'].isoformat(),
            "dias_decorridos": dias_decorridos,
            "percentual_progresso": round(percentual, 1)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.put("/api/recapagem/ordem/{ordem_id}/status")
async def atualizar_status_recapagem(ordem_id: str, dados: RecappingStatusModel):
    """
    Webhook: Recapadora atualiza status
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE ordens_recapagem 
                SET status = %s, data_ultima_atualizacao = NOW()
                WHERE ordem_id = %s
            """, (dados.status, ordem_id))
            
            # Se concluído, liberar pneus
            if dados.status == 'concluido':
                cur.execute("""
                    UPDATE pneus 
                    SET status = 'ESTOQUE'
                    WHERE status = 'RECAPAGEM'
                """)
            
            conn.commit()
        
        return {
            "status": "atualizado",
            "ordem_id": ordem_id,
            "novo_status": dados.status
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# ==================== ENDPOINTS DE CPK ====================

@app.get("/api/relatorios/cpk")
async def get_cpk_report(cliente_id: str):
    """
    Calcula CPK (Capability Process Index) da frota
    
    CPK > 1.67: Excelente
    CPK > 1.33: Adequado
    CPK > 1.0:  Atenção
    CPK < 1.0:  Crítico
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT km_vida_total, ciclo_atual
                FROM pneus 
                WHERE cliente_id = %s AND status = 'MONTADO'
            """, (cliente_id,))
            
            tires = cur.fetchall()
        
        if not tires:
            raise HTTPException(status_code=400, detail="Sem pneus montados para análise")
        
        # Calcular estatísticas
        vidas = [t['km_vida_total'] for t in tires]
        media = sum(vidas) / len(vidas)
        desvio = (sum((x - media) ** 2 for x in vidas) / len(vidas)) ** 0.5
        
        # Limites
        USL = 70000  # Upper Spec Limit
        LSL = 12000  # Lower Spec Limit
        
        # CPK
        if desvio == 0:
            cpk = float('inf')
        else:
            cpk_superior = (USL - media) / (3 * desvio)
            cpk_inferior = (media - LSL) / (3 * desvio)
            cpk = min(cpk_superior, cpk_inferior)
        
        # Status
        if cpk > 1.67:
            status = "EXCELENTE"
            recomendacao = "Continue o processo atual. Manter padrão."
        elif cpk > 1.33:
            status = "ADEQUADO"
            recomendacao = "Monitorar mensalmente. Tudo dentro do esperado."
        elif cpk > 1.0:
            status = "ATENÇÃO"
            recomendacao = "Revisar procedimentos. Aumentar frequência rodízio."
        else:
            status = "CRÍTICO"
            recomendacao = "AÇÃO IMEDIATA! Processo fora de controle."
        
        percentual_dentro_spec = (
            sum(1 for v in vidas if LSL <= v <= USL) / len(vidas) * 100
        )
        
        return {
            "cpk": round(cpk, 2),
            "media": round(media, 1),
            "desvio": round(desvio, 1),
            "status": status,
            "recomendacao": recomendacao,
            "minimo": LSL,
            "maximo": USL,
            "percentual_dentro_spec": round(percentual_dentro_spec, 1),
            "total_tires": len(tires)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# ==================== ENDPOINTS DE ALERTAS ====================

@app.get("/api/alertas")
async def get_alertas(cliente_id: str):
    """
    Retorna lista de alertas do sistema
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    alertas = []
    
    try:
        with conn.cursor() as cur:
            # ALERTA 1: Pneus muito velhos (> 48 meses)
            cur.execute("""
                SELECT id, marca_fogo, ciclo_atual, km_vida_total
                FROM pneus 
                WHERE cliente_id = %s AND status = 'MONTADO' AND ciclo_atual > 4
                ORDER BY ciclo_atual DESC
            """, (cliente_id,))
            
            pneus_velhos = cur.fetchall()
            for p in pneus_velhos:
                alertas.append({
                    "id": f"VELHO_{p['id']}",
                    "tipo": "PNEU_ENVELHECIDO",
                    "severidade": "CRITICO",
                    "pneu_id": p['marca_fogo'],
                    "mensagem": f"Pneu com {p['ciclo_atual']} ciclos. Limite recomendado: 4",
                    "acao": "Enviar para recapagem ou sucata"
                })
            
            # ALERTA 2: Muitos ciclos sem rodízio
            cur.execute("""
                SELECT id, marca_fogo, posicao_atual
                FROM pneus 
                WHERE cliente_id = %s AND status = 'MONTADO'
                ORDER BY id DESC LIMIT 10
            """, (cliente_id,))
            
            pneus_sem_rodizio = cur.fetchall()
            for p in pneus_sem_rodizio[:2]:
                alertas.append({
                    "id": f"RODIZIO_{p['id']}",
                    "tipo": "RODIZIO_ATRASADO",
                    "severidade": "ALTO",
                    "pneu_id": p['marca_fogo'],
                    "mensagem": f"Pneu na posição {p['posicao_atual']} por muito tempo",
                    "acao": "Incluir em próximo rodízio"
                })
        
        # Ordenar por severidade
        ordem_severidade = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2}
        alertas.sort(key=lambda x: ordem_severidade.get(x['severidade'], 3))
        
        return {
            "alertas": alertas,
            "total": len(alertas),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.post("/api/alertas/{alerta_id}/resolver")
async def resolver_alerta(alerta_id: str):
    """
    Marca alerta como resolvido
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Conexão com banco falhou")
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO alertas_log (alerta_id, resolvido, data_resolucao)
                VALUES (%s, TRUE, NOW())
                ON CONFLICT (alerta_id) DO UPDATE 
                SET resolvido = TRUE, data_resolucao = NOW()
            """, (alerta_id,))
            
            conn.commit()
        
        return {
            "status": "resolvido",
            "alerta_id": alerta_id
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

# ==================== ENDPOINTS DE VALIDAÇÃO ====================

@app.post("/api/validacao/pneu")
async def validar_pneu(dados: dict):
    """
    Valida dados antes de cadastrar um pneu
    """
    required_fields = ['marca_fogo', 'tamanho', 'marca']
    
    for field in required_fields:
        if field not in dados or dados[field] is None:
            raise HTTPException(status_code=400, detail=f"Campo obrigatório faltando: {field}")
    
    tamanhos_validos = ['295/80R22.5', '275/80R22.5', '11.00R22', '12R22.5']
    if dados['tamanho'] not in tamanhos_validos:
        raise HTTPException(status_code=400, detail=f"Tamanho inválido")
    
    return {
        "status": "validado",
        "dados": dados
    }

# ==================== RUN ====================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
