'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { getSessionProfile, SessionProfile } from '@/lib/auth'

const POSICOES = ['FL', 'FR', 'TL_OUT', 'TL_IN', 'TR_IN', 'TR_OUT', 'RL_OUT', 'RL_IN', 'RR_IN', 'RR_OUT']

type Caminhao = { id: string; placa: string }

async function fileToBase64(file: File): Promise<string> {
  const bytes = await file.arrayBuffer()
  let binary = ''
  const arr = new Uint8Array(bytes)
  for (let i = 0; i < arr.length; i++) binary += String.fromCharCode(arr[i])
  return btoa(binary)
}

export default function OficinaPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [ready, setReady] = useState(false)
  const [profile, setProfile] = useState<SessionProfile | null>(null)
  const [trucks, setTrucks] = useState<Caminhao[]>([])
  const [scanResult, setScanResult] = useState<{ marca_fogo: string | null; confidence?: number | null } | null>(null)
  const [manualCode, setManualCode] = useState('')
  const [msg, setMsg] = useState('')

  const [acao, setAcao] = useState<'tirar' | 'colocar' | 'trocar' | 'recapagem' | 'retorno_recapagem'>('tirar')
  const [motivo, setMotivo] = useState('recapagem')
  const [statusDestino, setStatusDestino] = useState<'RECAPAGEM' | 'SUCATA' | 'ESTOQUE'>('RECAPAGEM')
  const [truckId, setTruckId] = useState('')
  const [posicao, setPosicao] = useState(POSICOES[0])
  const [codigoB, setCodigoB] = useState('')
  const [recapadora, setRecapadora] = useState('Recapadora')
  const [loteCodigos, setLoteCodigos] = useState('')

  const codigoPrincipal = useMemo(
    () => (scanResult?.marca_fogo || manualCode).trim().toUpperCase(),
    [scanResult, manualCode]
  )

  useEffect(() => {
    const init = async () => {
      const p = await getSessionProfile()
      if (!p) {
        router.push('/login')
        return
      }
      if (!p.clienteId) {
        router.push('/setup')
        return
      }
      setProfile(p)

      const { data } = await supabase
        .from('caminhoes')
        .select('id, placa')
        .eq('cliente_id', p.clienteId)
        .order('placa', { ascending: true })
      const lista = (data || []) as Caminhao[]
      setTrucks(lista)
      if (lista.length) setTruckId(lista[0].id)
      setReady(true)
    }
    init()
  }, [router])

  const runScan = async (file: File | null) => {
    if (!file) return
    setLoading(true)
    setMsg('')
    try {
      const b64 = await fileToBase64(file)
      const { data, error } = await supabase.functions.invoke('scan-pneu', {
        body: { image_base64: b64, mime_type: file.type || 'image/jpeg' }
      })
      if (error) setMsg(error.message || 'Falha no scan')
      else setScanResult(data?.result ?? null)
    } finally {
      setLoading(false)
    }
  }

  const executarAcao = async () => {
    if (!profile?.clienteId || !profile.userId) return
    setMsg('')

    if (acao === 'tirar') {
      if (!codigoPrincipal) return setMsg('Informe ou escaneie o pneu.')
      const { error } = await supabase.rpc('rpc_tirecontrol_tirar_pneu', {
        p_cliente_id: profile.clienteId,
        p_usuario_id: profile.userId,
        p_marca_fogo: codigoPrincipal,
        p_motivo: motivo,
        p_status_destino: statusDestino
      })
      return setMsg(error ? error.message : `Retirada registrada para ${codigoPrincipal}`)
    }

    if (acao === 'colocar') {
      if (!codigoPrincipal) return setMsg('Informe ou escaneie o pneu.')
      if (!truckId) return setMsg('Selecione um caminhao.')
      const { error } = await supabase.rpc('rpc_tirecontrol_colocar_pneu', {
        p_cliente_id: profile.clienteId,
        p_usuario_id: profile.userId,
        p_marca_fogo: codigoPrincipal,
        p_caminhao_id: truckId,
        p_posicao: posicao
      })
      return setMsg(error ? error.message : `Montagem registrada para ${codigoPrincipal}`)
    }

    if (acao === 'trocar') {
      if (!codigoPrincipal || !codigoB.trim()) return setMsg('Informe os dois pneus.')
      const { error } = await supabase.rpc('rpc_tirecontrol_trocar_posicao', {
        p_cliente_id: profile.clienteId,
        p_usuario_id: profile.userId,
        p_marca_fogo_a: codigoPrincipal,
        p_marca_fogo_b: codigoB.trim().toUpperCase()
      })
      return setMsg(error ? error.message : 'Troca registrada com sucesso.')
    }

    if (acao === 'recapagem') {
      const codigos = loteCodigos
        .split(/\r?\n|,/)
        .map((c) => c.trim().toUpperCase())
        .filter(Boolean)
      if (codigoPrincipal) codigos.unshift(codigoPrincipal)
      const unicos = [...new Set(codigos)]
      if (!unicos.length) return setMsg('Informe ao menos um pneu para recapagem.')

      const { error } = await supabase.rpc('rpc_tirecontrol_enviar_recapagem', {
        p_cliente_id: profile.clienteId,
        p_usuario_id: profile.userId,
        p_recapadora: recapadora,
        p_codigos: unicos
      })
      return setMsg(error ? error.message : `Lote enviado (${unicos.length} pneus).`)
    }

    if (acao === 'retorno_recapagem') {
      const codigos = loteCodigos
        .split(/\r?\n|,/)
        .map((c) => c.trim().toUpperCase())
        .filter(Boolean)
      if (codigoPrincipal) codigos.unshift(codigoPrincipal)
      const unicos = [...new Set(codigos)]
      if (!unicos.length) return setMsg('Informe ao menos um pneu para retorno.')

      const { error } = await supabase.rpc('rpc_tirecontrol_retorno_recapagem', {
        p_cliente_id: profile.clienteId,
        p_usuario_id: profile.userId,
        p_codigos: unicos,
        p_observacao: `retorno_web_${new Date().toISOString()}`
      })
      return setMsg(error ? error.message : `Retorno registrado (${unicos.length} pneus).`)
    }
  }

  if (!ready) return <p style={{ padding: 40 }}>Carregando...</p>

  return (
    <main style={{ padding: 40 }}>
      <h1>Borracharia</h1>
      <p>Fluxo: escolha acao {'->'} escaneie {'->'} confirme</p>

      <div style={{ marginTop: 16 }}>
        <label>Acao: </label>
        <select value={acao} onChange={(e) => setAcao(e.target.value as typeof acao)}>
          <option value="tirar">Tirar pneu</option>
          <option value="colocar">Colocar pneu</option>
          <option value="trocar">Trocar posicao</option>
          <option value="recapagem">Enviar recapagem</option>
          <option value="retorno_recapagem">Retorno recapagem</option>
        </select>
      </div>

      <div style={{ marginTop: 16 }}>
        <input type="file" accept="image/*" onChange={(e) => runScan(e.target.files?.[0] || null)} />
        {loading && <p>Lendo imagem...</p>}
      </div>

      <div style={{ marginTop: 12 }}>
        <input
          placeholder="Codigo do pneu (fallback manual)"
          value={manualCode}
          onChange={(e) => setManualCode(e.target.value)}
        />
      </div>

      {scanResult?.marca_fogo && (
        <p style={{ marginTop: 10 }}>
          Reconhecido: <strong>{scanResult.marca_fogo}</strong> ({Math.round((scanResult.confidence || 0) * 100)}%)
        </p>
      )}

      {acao === 'tirar' && (
        <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
          <input placeholder="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          <select value={statusDestino} onChange={(e) => setStatusDestino(e.target.value as typeof statusDestino)}>
            <option value="RECAPAGEM">RECAPAGEM</option>
            <option value="SUCATA">SUCATA</option>
            <option value="ESTOQUE">ESTOQUE</option>
          </select>
        </div>
      )}

      {acao === 'colocar' && (
        <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
          <select value={truckId} onChange={(e) => setTruckId(e.target.value)}>
            {trucks.map((t) => (
              <option key={t.id} value={t.id}>{t.placa}</option>
            ))}
          </select>
          <select value={posicao} onChange={(e) => setPosicao(e.target.value)}>
            {POSICOES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      )}

      {acao === 'trocar' && (
        <div style={{ marginTop: 14 }}>
          <input
            placeholder="Codigo do pneu B"
            value={codigoB}
            onChange={(e) => setCodigoB(e.target.value)}
          />
        </div>
      )}

      {(acao === 'recapagem' || acao === 'retorno_recapagem') && (
        <div style={{ marginTop: 14 }}>
          {acao === 'recapagem' && (
            <input
              placeholder="Recapadora"
              value={recapadora}
              onChange={(e) => setRecapadora(e.target.value)}
            />
          )}
          <textarea
            style={{ display: 'block', width: '100%', marginTop: 10, minHeight: 100 }}
            placeholder="Codigos do lote (um por linha ou separado por virgula)"
            value={loteCodigos}
            onChange={(e) => setLoteCodigos(e.target.value)}
          />
        </div>
      )}

      <div style={{ marginTop: 18, display: 'flex', gap: 10 }}>
        <button onClick={executarAcao}>Confirmar</button>
        <button onClick={() => router.push('/rodizio')} style={{ backgroundColor: '#2563eb', color: 'white' }}>
          Rodízio Visual (Novo)
        </button>
        <button onClick={() => router.push('/')}>Voltar</button>
      </div>

      {msg && <p style={{ marginTop: 16 }}>{msg}</p>}
    </main>
  )
}
