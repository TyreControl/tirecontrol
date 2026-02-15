import { supabase } from './supabase'

export async function getSessionProfile() {
    const { data: { session } } = await supabase.auth.getSession()

    if (!session) return null

    // For now, assuming user metadata contains clienteId or linking nicely
    // If not, we fetch from 'usuarios' table
    const { data: usuario } = await supabase
        .from('usuarios')
        .select('cliente_id')
        .eq('id', session.user.id)
        .single()

    if (usuario) {
        return {
            userId: session.user.id,
            email: session.user.email,
            clienteId: usuario.cliente_id
        }
    }

    return null
}
