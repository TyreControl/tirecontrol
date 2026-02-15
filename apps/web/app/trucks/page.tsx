'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'
import { getSessionProfile } from '@/lib/auth'

type Caminhao = {
  id: string
  placa: string
  modelo: string | null
}

export default function TrucksPage() {
  const router = useRouter()

  const [loading, setLoading] = useState(true)
  const [trucks, setTrucks] = useState<Caminhao[]>([])
  const [plate, setPlate] = useState('')
  const [model, setModel] = useState('')
  const [clientId, setClientId] = useState<string | null>(null)

  const loadTrucks = async (cid: string) => {
    const { data } = await supabase
      .from('caminhoes')
      .select('id, placa, modelo')
      .eq('cliente_id', cid)
      .order('placa', { ascending: true })

    setTrucks((data || []) as Caminhao[])
  }

  useEffect(() => {
    const init = async () => {
      const profile = await getSessionProfile()
      if (!profile) {
        router.push('/login')
        return
      }

      if (!profile.clienteId) {
        router.push('/setup')
        return
      }

      setClientId(profile.clienteId)
      await loadTrucks(profile.clienteId)
      setLoading(false)
    }

    init()
  }, [router])

  const addTruck = async () => {
    if (!plate || !clientId) return

    const { error } = await supabase.from('caminhoes').insert({
      placa: plate.toUpperCase().trim(),
      modelo: model || null,
      cliente_id: clientId,
      ativo: true,
    })

    if (error) {
      alert(error.message)
      return
    }

    setPlate('')
    setModel('')
    await loadTrucks(clientId)
  }

  const logout = async () => {
    await supabase.auth.signOut()
    router.push('/login')
  }

  if (loading) return <p style={{ padding: 40 }}>Carregando...</p>

  return (
    <main style={{ padding: 40 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between' }}>
        <h1>Controle de Frota</h1>
        <button onClick={logout}>Logout</button>
      </header>

      <div style={{ marginTop: 20, display: 'flex', gap: 10 }}>
        <input
          placeholder="Placa do caminhao"
          value={plate}
          onChange={(e) => setPlate(e.target.value)}
        />
        <input
          placeholder="Modelo (opcional)"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
        <button onClick={addTruck}>Adicionar</button>
      </div>

      <ul style={{ marginTop: 20 }}>
        {trucks.map((truck) => (
          <li key={truck.id}>
            {truck.placa} {truck.modelo ? `- ${truck.modelo}` : ''}
          </li>
        ))}
      </ul>
    </main>
  )
}
