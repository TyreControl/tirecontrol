'use client'

import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'
import { getSessionProfile } from '@/lib/auth'

export default function SetupPage() {
  const router = useRouter()
  const [nomeEmpresa, setNomeEmpresa] = useState('')
  const [nomeFantasia, setNomeFantasia] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCreateClient = async () => {
    setLoading(true)
    const sessionProfile = await getSessionProfile()
    if (!sessionProfile) {
      router.push('/login')
      return
    }

    // cria cliente no schema atual
    const { data: client, error } = await supabase
      .from('clientes')
      .insert({
        nome_empresa: nomeEmpresa,
        nome_fantasia: nomeFantasia || null
      })
      .select()
      .single()

    if (error) {
      alert(error.message)
      setLoading(false)
      return
    }

    // vincula profile ao cliente
    await supabase
      .from('profiles')
      .upsert({
        id: sessionProfile.userId,
        cliente_id: client.id,
        role: 'admin'
      })

    router.push('/')
  }

  return (
    <main style={{ padding: 40, maxWidth: 400 }}>
      <h1>Cadastro Inicial da Empresa</h1>

      <input
        placeholder="Nome da empresa"
        value={nomeEmpresa}
        onChange={e => setNomeEmpresa(e.target.value)}
        style={{ width: '100%', marginBottom: 10 }}
      />

      <input
        placeholder="Nome fantasia (opcional)"
        value={nomeFantasia}
        onChange={e => setNomeFantasia(e.target.value)}
        style={{ width: '100%', marginBottom: 10 }}
      />

      <button onClick={handleCreateClient} disabled={loading}>
        Criar e vincular empresa
      </button>
    </main>
  )
}
