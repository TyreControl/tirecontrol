'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'

export default function CPKPage() {
    const router = useRouter()
    const [stats, setStats] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const loadData = async () => {
            setLoading(true)
            setError(null)

            const profile = await getSessionProfile()
            if (!profile?.clienteId) {
                router.replace('/')
                setLoading(false)
                return
            }

            const { data, error: cpkError } = await supabase.rpc('rpc_tirecontrol_calcular_cpk', {
                p_cliente_id: profile.clienteId,
            })

            if (cpkError) {
                setStats(null)
                setError(cpkError.message)
                setLoading(false)
                return
            }

            setStats(data ?? null)
            setLoading(false)
        }

        void loadData()
    }, [router])

    if (loading) return <div className="p-8">Calculando estatisticas...</div>
    if (error) return <div className="p-8 text-red-700">Erro: {error}</div>
    if (!stats) return <div className="p-8">Sem dados para analise.</div>

    return (
        <div className="p-8 max-w-6xl mx-auto font-sans bg-gray-50 min-h-screen">
            <h1 className="text-3xl font-bold mb-8 text-gray-800">Analise de CPK (Qualidade)</h1>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div className="text-gray-500 text-sm font-medium uppercase">Indice CPK</div>
                    <div className={`text-4xl font-bold mt-2 ${stats.cpk_valor > 1.33 ? 'text-green-600' : 'text-yellow-600'}`}>
                        {stats.cpk_valor?.toFixed(2)}
                    </div>
                    <div className="text-xs text-gray-400 mt-2">Meta: {'>'} 1.33</div>
                </div>
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div className="text-gray-500 text-sm font-medium uppercase">Media Vida Util</div>
                    <div className="text-4xl font-bold mt-2 text-gray-800">
                        {Math.round(stats.media).toLocaleString()} <span className="text-lg text-gray-400 font-normal">km</span>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div className="text-gray-500 text-sm font-medium uppercase">Desvio Padrao</div>
                    <div className="text-4xl font-bold mt-2 text-gray-800">
                        {Math.round(stats.desvio).toLocaleString()}
                    </div>
                </div>
                <div className={`p-6 rounded-xl shadow-sm border border-gray-200 text-white flex flex-col justify-center ${stats.status === 'Excelente' ? 'bg-green-600' : stats.status === 'Adequado' ? 'bg-blue-600' : 'bg-yellow-600'}`}>
                    <div className="text-white/80 text-sm font-medium uppercase">Status do Processo</div>
                    <div className="text-3xl font-bold mt-1">{stats.status}</div>
                </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border mb-8">
                <h3 className="text-lg font-bold mb-4">Recomendacao Automatica</h3>
                <p className="text-gray-700">{stats.recomendacao}</p>
            </div>
        </div>
    )
}
