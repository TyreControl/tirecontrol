'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'
import {
    Chart as ChartJS,
    ArcElement,
    Tooltip,
    Legend,
    CategoryScale,
    LinearScale,
    BarElement,
    Title
} from 'chart.js'
import { Pie, Bar } from 'react-chartjs-2'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title)

export default function ReportsPage() {
    const router = useRouter()
    const [loading, setLoading] = useState(true)
    const [data, setData] = useState<any>(null)
    const [period, setPeriod] = useState(30)

    useEffect(() => {
        const load = async () => {
            setLoading(true)
            const profile = await getSessionProfile()
            if (!profile?.clienteId) {
                router.push('/login')
                return
            }

            const { data: reportData, error } = await supabase
                .rpc('rpc_tirecontrol_relatorio_geral', {
                    p_cliente_id: profile.clienteId,
                    p_dias_movimentacao: period
                })

            if (data && !error) setData(reportData) // This looks like a bug in my thought trace logic or just typo. 
            // Correct logic:
            if (reportData) setData(reportData)

            setLoading(false)
        }
        load()
    }, [router, period])

    if (loading) return <div className="p-12 text-center text-gray-500">Carregando relatórios...</div>

    // Parse Data for Status Pie Chart
    const statusDist = data?.distribuicao_status || {}
    const pieData = {
        labels: Object.keys(statusDist),
        datasets: [
            {
                data: Object.values(statusDist),
                backgroundColor: [
                    '#4ade80', // green (Montado?)
                    '#3b82f6', // blue (Estoque?)
                    '#f97316', // orange (Recapagem?)
                    '#ef4444', // red (Sucata?)
                    '#94a3b8', // gray (Outros)
                ],
                borderWidth: 1,
            },
        ],
    }

    // Parse Data for Movements Bar Chart
    const moves = data?.movimentacoes || []
    const moveTypes = moves.map((m: any) => m.tipo_movimento)
    const moveCounts = moves.map((m: any) => m.qtd)

    const barData = {
        labels: moveTypes,
        datasets: [
            {
                label: 'Quantidade de Movimentações',
                data: moveCounts,
                backgroundColor: 'rgba(59, 130, 246, 0.5)',
            },
        ],
    }

    return (
        <div className="p-8 max-w-6xl mx-auto font-sans bg-gray-50 min-h-screen">
            <h1 className="text-3xl font-bold mb-8 text-gray-800 flex items-center gap-2">
                📈 Relatórios Gerenciais
            </h1>

            {/* FILTERS */}
            <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 mb-8 flex justify-between items-center">
                <span className="font-semibold text-gray-700">Período de Análise</span>
                <div className="flex gap-2">
                    {[7, 30, 90].map(d => (
                        <button
                            key={d}
                            onClick={() => setPeriod(d)}
                            className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${period === d ? 'bg-blue-600 text-white shadow-md' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                        >
                            {d} dias
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* STATUS CHART */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h3 className="text-lg font-bold text-gray-700 mb-4">Distribuição da Frota</h3>
                    <div className="h-64 flex justify-center">
                        {Object.keys(statusDist).length > 0 ?
                            <Pie data={pieData} options={{ maintainAspectRatio: false }} />
                            : <p className="text-gray-400 self-center">Sem dados de pneus.</p>
                        }
                    </div>
                </div>

                {/* MOVEMENTS CHART */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h3 className="text-lg font-bold text-gray-700 mb-4">Movimentações no Período</h3>
                    <div className="h-64 flex justify-center">
                        {moves.length > 0 ?
                            <Bar data={barData} options={{ maintainAspectRatio: false, indexAxis: 'y' as const }} />
                            : <p className="text-gray-400 self-center">Nenhuma movimentação no período.</p>
                        }
                    </div>
                </div>

                {/* COSTS CARD */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 col-span-1 md:col-span-2">
                    <h3 className="text-lg font-bold text-gray-700 mb-4">Custos Estimados</h3>
                    <div className="flex items-center gap-4">
                        <div className="text-4xl font-bold text-gray-800">
                            R$ {Number(data?.custo_estimado || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </div>
                        <div className="text-sm text-gray-500 max-w-md">
                            * Custo calculado com base nos serviços registrados no período selecionado. (Funcionalidade em desenvolvimento: requer cadastro de custos por serviço).
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
