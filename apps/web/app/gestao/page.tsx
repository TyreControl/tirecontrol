'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { canAccessGestao, getSessionProfile } from '@/lib/auth'
import { supabase } from '@/lib/supabase'

type Resumo = {
  total_pneus: number
  montados: number
  estoque: number
  recapagem: number
}

export default function GestaoPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [resumo, setResumo] = useState<Resumo>({ total_pneus: 0, montados: 0, estoque: 0, recapagem: 0 })

  useEffect(() => {
    const load = async () => {
      const profile = await getSessionProfile()
      if (!profile) {
        router.push('/login')
        return
      }
      if (!profile.clienteId) {
        router.push('/setup')
        return
      }
      if (!canAccessGestao(profile.role)) {
        router.push('/')
        return
      }

      const { data } = await supabase
        .from('pneus')
        .select('status')
        .eq('cliente_id', profile.clienteId)

      const rows = data || []
      setResumo({
        total_pneus: rows.length,
        montados: rows.filter((r) => r.status === 'MONTADO').length,
        estoque: rows.filter((r) => r.status === 'ESTOQUE').length,
        recapagem: rows.filter((r) => r.status === 'RECAPAGEM').length,
      })
      setLoading(false)
    }
    load()
  }, [router])

  if (loading) return <p style={{ padding: 40 }}>Carregando...</p>

  return (
    <main style={{ padding: 40 }}>
      <h1>Painel da Gestao</h1>
      <div style={{ display: 'flex', gap: 16, marginTop: 16 }}>
        <div>Total pneus: {resumo.total_pneus}</div>
        <div>Montados: {resumo.montados}</div>
        <div>Estoque: {resumo.estoque}</div>
        <div>Recapagem: {resumo.recapagem}</div>
      </div>
      <button style={{ marginTop: 24 }} onClick={() => router.push('/')}>
        Voltar
      </button>
    </main>
  )
}

