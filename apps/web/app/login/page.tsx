'use client'

import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async () => {
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError(error.message)
      return
    }
    router.push('/')
  }

  const handleSignup = async () => {
    setError(null)
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) {
      setError(error.message)
      return
    }

    if (data.user) {
      await supabase.from('profiles').upsert({
        id: data.user.id,
        role: 'operador',
        cliente_id: null,
      })
    }
    alert('Conta criada. Faca login.')
  }

  return (
    <main style={{ padding: 40, maxWidth: 420 }}>
      <h1>TireControl - Login</h1>

      <input
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        style={{ display: 'block', marginBottom: 10, width: '100%' }}
      />

      <input
        type="password"
        placeholder="Senha"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        style={{ display: 'block', marginBottom: 10, width: '100%' }}
      />

      {error && <p style={{ color: 'red' }}>{error}</p>}

      <button onClick={handleLogin}>Entrar</button>
      <button onClick={handleSignup} style={{ marginLeft: 10 }}>
        Criar conta
      </button>
    </main>
  )
}

