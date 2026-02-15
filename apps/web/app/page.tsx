'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'
import { canAccessCadastroInicial, canAccessGestao, getSessionProfile, SessionProfile } from '@/lib/auth'

export default function Home() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [profile, setProfile] = useState<SessionProfile | null>(null)

  useEffect(() => {
    const load = async () => {
      const sessionProfile = await getSessionProfile()
      if (!sessionProfile) {
        router.push('/login')
        return
      }
      setProfile(sessionProfile)
      setLoading(false)
    }

    load()
  }, [router])

  if (loading) return <p>Carregando...</p>
  if (!profile) return null

  return (
  <main style={{ padding: 40 }}>
    <h1>TireControl - Web</h1>
    <p>Perfil: <strong>{profile.role}</strong></p>
    <p>Cliente: <strong>{profile.clienteId || 'nao vinculado'}</strong></p>

    {!profile.clienteId && (
      <div style={{ marginTop: 16 }}>
        <p>Seu usuario ainda nao esta vinculado a uma empresa.</p>
        <button onClick={() => router.push('/setup')}>Configurar empresa</button>
      </div>
    )}

    {profile.clienteId && (
      <div style={{ display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' }}>
        <button onClick={() => router.push('/oficina')}>Borracharia</button>
        <button onClick={() => router.push('/trucks')}>Controle de Frota</button>
        {canAccessGestao(profile.role) && (
          <button onClick={() => router.push('/gestao')}>Painel da Gestao</button>
        )}
        {canAccessCadastroInicial(profile.role) && (
          <button onClick={() => router.push('/setup')}>Cadastro Inicial</button>
        )}
      </div>
    )}

    <button
      style={{ marginTop: 24 }}
      onClick={async () => {
        await supabase.auth.signOut()
        router.push('/login')
      }}
    >
      Logout
    </button>
  </main>
)

}
