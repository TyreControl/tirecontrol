'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    PointElement,
    LineElement
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'

ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    PointElement,
    LineElement
)

export default function CPKPage() {
    const [stats, setStats] = useState<any>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        loadData()
    }, [])

    async function loadData() {
        const profile = await getSessionProfile()
        if (!profile) return

        const { data, error } = await supabase.rpc('rpc_tirecontrol_calcular_cpk', {
            p_cliente_id: profile.clienteId
        })

        if (data) setStats(data)
        setLoading(false)
    }

    if (loading) return <div className="p-8">Calculando estatísticas...</div>
    if (!stats) return <div className="p-8">Sem dados para análise.</div>

    return (
        <div className="p-8 max-w-6xl mx-auto font-sans bg-gray-50 min-h-screen">
            <h1 className="text-3xl font-bold mb-8 text-gray-800">📊 Análise de CPK (Qualidade)</h1>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div className="text-gray-500 text-sm font-medium uppercase">Índice CPK</div>
                    <div className={`text-4xl font-bold mt-2 ${stats.cpk_valor > 1.33 ? 'text-green-600' : 'text-yellow-600'}`}>
                        {stats.cpk_valor?.toFixed(2)}
                    </div>
                    <div className="text-xs text-gray-400 mt-2">Meta: {'>'} 1.33</div>
                </div>
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div className="text-gray-500 text-sm font-medium uppercase">Média Vida Útil</div>
                    <div className="text-4xl font-bold mt-2 text-gray-800">
                        {Math.round(stats.media).toLocaleString()} <span className="text-lg text-gray-400 font-normal">km</span>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <div className="text-gray-500 text-sm font-medium uppercase">Desvio Padrão</div>
                    <div className="text-4xl font-bold mt-2 text-gray-800">
                        {Math.round(stats.desvio).toLocaleString()}
                    </div>
                </div>
                <div className={`p-6 rounded-xl shadow-sm border border-gray-200 text-white flex flex-col justify-center
                    ${stats.status === 'Excelente' ? 'bg-green-600' : stats.status === 'Adequado' ? 'bg-blue-600' : 'bg-yellow-600'}
                `}>
                    <div className="text-white/80 text-sm font-medium uppercase">Status do Processo</div>
                    <div className="text-3xl font-bold mt-1">{stats.status}</div>
                </div>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border mb-8">
                <h3 className="text-lg font-bold mb-4">Recomendação Automática</h3>
                <p className="text-gray-700">{stats.recomendacao}</p>
            </div>
        </div>
    )
}
