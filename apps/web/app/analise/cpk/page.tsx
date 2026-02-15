'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'
import Link from 'next/link'
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'

ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend
)

export default function CPKPage() {
    const router = useRouter()
    const [loading, setLoading] = useState(true)
    const [data, setData] = useState<any>(null)
    const [error, setError] = useState('')

    useEffect(() => {
        const load = async () => {
            try {
                const profile = await getSessionProfile()
                if (!profile?.clienteId) {
                    router.push('/login')
                    return
                }

                // Call RPC
                const { data: cpkData, error: rpcError } = await supabase
                    .rpc('rpc_tirecontrol_calcular_cpk', { p_cliente_id: profile.clienteId })

                if (rpcError) throw rpcError
                if (!cpkData.ok) throw new Error(cpkData.error || 'Erro desconhecido')

                setData(cpkData)
            } catch (e: any) {
                setError(e.message)
            } finally {
                setLoading(false)
            }
        }
        load()
    }, [router])

    if (loading) return <div className="p-12 text-center text-gray-500">Carregando análise estatística...</div>

    if (error) return (
        <div className="p-8">
            <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded mb-4">
                <h3 className="font-bold">Erro na Análise</h3>
                <p>{error}</p>
                <button onClick={() => window.location.reload()} className="mt-2 text-sm underline">Tentar Novamente</button>
            </div>
        </div>
    )

    // Prepare Chart Data (Histogram - simplified)
    // In a real app we would bin the 'dados_vida' array. For now let's just plot the values if small, or bin them.
    // Let's create mock bins for the demo if 'dados_vida' is raw numbers.
    const rawLife = data.dados_vida as number[] || []

    // Simple binning (0-10, 10-20, etc.)
    const bins = [0, 12, 24, 36, 48, 60, 72]
    const binCounts = bins.map((b, i) => {
        if (i === bins.length - 1) return 0
        const top = bins[i + 1]
        return rawLife.filter(v => v >= b && v < top).length
    })

    const chartData = {
        labels: bins.slice(0, -1).map((b, i) => `${b}-${bins[i + 1]}m`),
        datasets: [
            {
                label: 'Pneus por Faixa de Vida (Meses)',
                data: binCounts,
                backgroundColor: 'rgba(53, 162, 235, 0.5)',
            },
        ],
    }

    const options = {
        responsive: true,
        plugins: {
            legend: { position: 'top' as const },
            title: { display: true, text: 'Distribuição de Vida Útil da Frota' },
        },
    }

    return (
        <div className="p-8 max-w-6xl mx-auto font-sans bg-gray-50 min-h-screen">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-2">
                    📊 Análise de CPK (Capacidade do Processo)
                </h1>
                <Link href="/relatorios" className="text-blue-600 hover:underline">Ver Relatórios Gerais →</Link>
            </div>

            {/* ERROR / INFO */}
            {data.quantidade < 5 && (
                <div className="bg-yellow-50 text-yellow-800 p-3 rounded mb-6 text-sm border border-yellow-200">
                    ⚠️ Atenção: Poucos dados ({data.quantidade} pneus) podem gerar um índice CPK pouco confiável.
                </div>
            )}

            {/* KPI CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className={`p-6 rounded-xl shadow-sm border-l-4 ${data.status === 'Excelente' ? 'bg-green-50 border-green-500' :
                        data.status === 'Adequado' ? 'bg-blue-50 border-blue-500' :
                            data.status === 'Atenção' ? 'bg-orange-50 border-orange-500' :
                                'bg-red-50 border-red-500'
                    }`}>
                    <div className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">Índice CPK</div>
                    <div className="text-4xl font-bold text-gray-800">{Number(data.cpk).toFixed(2)}</div>
                    <div className="mt-2 text-sm font-medium px-2 py-0.5 rounded-full inline-block bg-white shadow-sm border">
                        {data.status}
                    </div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                    <div className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">Média de Vida</div>
                    <div className="text-3xl font-bold text-gray-800">{Number(data.media).toFixed(1)} <span className="text-sm font-normal text-gray-400">meses</span></div>
                    <div className="text-xs text-gray-400 mt-2">Alvo: 36-48 meses</div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                    <div className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">Desvio Padrão</div>
                    <div className="text-3xl font-bold text-gray-800">{Number(data.desvio).toFixed(1)}</div>
                    <div className="text-xs text-gray-400 mt-2">Variabilidade do processo</div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                    <div className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">Amostra</div>
                    <div className="text-3xl font-bold text-gray-800">{data.quantidade}</div>
                    <div className="text-xs text-green-600 mt-2">Pneus Ativos</div>
                </div>
            </div>

            {/* MAIN CONTENT GRID */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* CHARTS */}
                <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <Bar options={options} data={chartData} />
                </div>

                {/* RECOMMENDATIONS */}
                <div className="space-y-6">
                    <div className="bg-blue-900 text-white p-6 rounded-xl shadow-lg">
                        <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                            🤖 Recomendação do Sistema
                        </h3>
                        <p className="text-blue-100 leading-relaxed text-sm mb-4">
                            {data.recomendacao}
                        </p>
                        <div className="text-xs text-blue-300 pt-4 border-t border-blue-800">
                            Baseado na análise estatística de {data.quantidade} pneus ativos.
                        </div>
                    </div>

                    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                        <h4 className="font-bold text-gray-700 mb-4 text-sm uppercase">O que é CPK?</h4>
                        <ul className="space-y-3 text-sm text-gray-600">
                            <li className="flex gap-2">
                                <span className="font-bold text-green-600">≥ 1.33</span>
                                <span>Excelente (Processo muito capaz)</span>
                            </li>
                            <li className="flex gap-2">
                                <span className="font-bold text-blue-600">≥ 1.00</span>
                                <span>Adequado (Aceitável)</span>
                            </li>
                            <li className="flex gap-2">
                                <span className="font-bold text-orange-500">≥ 0.67</span>
                                <span>Atenção (Fora de controle)</span>
                            </li>
                            <li className="flex gap-2">
                                <span className="font-bold text-red-500">&lt; 0.67</span>
                                <span>Crítico (Melhoria urgente)</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    )
}
