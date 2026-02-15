'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'
import {
    Chart as ChartJS,
    ArcElement,
    Tooltip,
    Legend,
    CategoryScale,
    LinearScale,
    BarElement
} from 'chart.js'
import { Pie, Bar } from 'react-chartjs-2'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement)

export default function ReportsPage() {
    const [report, setReport] = useState<any>(null)
    const [period, setPeriod] = useState(30)
    const [dataStatus, setDataStatus] = useState<any>(null)

    useEffect(() => {
        loadReport()
    }, [period])

    async function loadReport() {
        const profile = await getSessionProfile()
        if (!profile) return

        const { data } = await supabase.rpc('rpc_tirecontrol_relatorio_geral', {
            p_cliente_id: profile.clienteId,
            p_periodo_dias: period
        })

        if (data) {
            setReport(data)
            setDataStatus({
                labels: ['Montados', 'Estoque', 'Recapagem', 'Sucata'],
                datasets: [{
                    data: [data.total_montados, data.total_estoque, data.total_recapagem, data.total_sucata],
                    backgroundColor: ['#2563eb', '#16a34a', '#d97706', '#dc2626']
                }]
            })
        }
    }

    if (!dataStatus) return <div className="p-8">Carregando relatório...</div>

    return (
        <div className="p-8 max-w-6xl mx-auto font-sans bg-gray-50 min-h-screen">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold text-gray-800">📈 Relatórios Gerenciais</h1>
                <div className="flex gap-2 bg-white p-1 rounded-lg border shadow-sm">
                    {[7, 30, 90].map(d => (
                        <button
                            key={d}
                            onClick={() => setPeriod(d)}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${period === d ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-50'}`}
                        >
                            {d} dias
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h3 className="text-lg font-bold text-gray-700 mb-4">Distribuição da Frota</h3>
                    <div className="w-64 mx-auto">
                        <Pie data={dataStatus} />
                    </div>
                </div>

                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h3 className="text-lg font-bold text-gray-700 mb-4">Custos Estimados ({period} dias)</h3>
                    <div className="text-5xl font-bold text-gray-800 mt-8">
                        R$ {report?.custo_estimado?.toLocaleString()}
                    </div>
                    <p className="text-gray-400 mt-2">Baseado em recapagens e compras no período.</p>
                </div>
            </div>
        </div>
    )
}
