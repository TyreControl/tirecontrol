'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'

type Suggestion = {
    trocar_de: {
        id: string
        marca_fogo: string
        posicao_atual: string
        desgaste_score: number
        km_vida_total: number
    }
    trocar_para: {
        id: string
        marca_fogo: string
        ciclo_atual: number
        desgaste_score: number
        km_vida_total: number
    }
    economia_percentual: number
    reason: string
}

type Truck = {
    id: string
    placa: string
}

export default function RodizioPage() {
    const router = useRouter()
    const [loading, setLoading] = useState(false)
    const [trucks, setTrucks] = useState<Truck[]>([])
    const [selectedTruckId, setSelectedTruckId] = useState('')
    const [suggestions, setSuggestions] = useState<Suggestion[]>([])
    const [executing, setExecuting] = useState(false)
    const [result, setResult] = useState<any>(null)
    const [error, setError] = useState('')
    const [userProfile, setUserProfile] = useState<any>(null)

    // AI Analysis State
    const [analyzing, setAnalyzing] = useState(false)
    const [analysisResult, setAnalysisResult] = useState<string>('')

    useEffect(() => {
        const init = async () => {
            setLoading(true)
            try {
                const profile = await getSessionProfile()
                if (!profile?.clienteId) {
                    router.push('/login')
                    return
                }
                setUserProfile(profile)

                const { data } = await supabase
                    .from('caminhoes')
                    .select('id, placa')
                    .eq('cliente_id', profile.clienteId)
                    .order('placa')

                if (data) setTrucks(data)
            } catch (e: any) {
                setError('Erro ao carregar dados: ' + e.message)
            } finally {
                setLoading(false)
            }
        }
        init()
    }, [router])

    useEffect(() => {
        if (!selectedTruckId) {
            setSuggestions([])
            setAnalysisResult('')
            return
        }

        const fetchSuggestions = async () => {
            setLoading(true)
            setSuggestions([])
            setResult(null)
            setError('')
            setAnalysisResult('')

            try {
                const { data, error } = await supabase.functions.invoke('get-rotation-suggestions', {
                    body: { veiculo_id: selectedTruckId }
                })

                if (error) throw error
                setSuggestions(data.suggestions || [])
            } catch (e: any) {
                console.error(e)
                setError('Erro ao buscar sugestões: ' + e.message)
            } finally {
                setLoading(false)
            }
        }

        fetchSuggestions()
    }, [selectedTruckId])

    async function executeRotation() {
        if (!selectedTruckId || suggestions.length === 0 || !userProfile) return

        setExecuting(true)
        try {
            const payload = suggestions.map(s => ({
                trocar_de: s.trocar_de,
                trocar_para: s.trocar_para
            }))

            const { data, error } = await supabase.rpc('rpc_tirecontrol_executar_rodizio', {
                p_veiculo_id: selectedTruckId,
                p_usuario_id: userProfile.userId,
                p_trocas: payload
            })

            if (error) throw error
            setResult(data)
            setSuggestions([])
            setAnalysisResult('')
        } catch (e: any) {
            setError('Erro ao executar rodízio: ' + e.message)
        } finally {
            setExecuting(false)
        }
    }

    async function analyzeWithAI() {
        if (suggestions.length === 0) return

        setAnalyzing(true)
        setAnalysisResult('')

        try {
            const { data, error } = await supabase.functions.invoke('analyze-rotation', {
                body: {
                    veiculo_id: selectedTruckId,
                    changes: suggestions
                }
            })

            if (error) throw error
            setAnalysisResult(data.analysis)
        } catch (e: any) {
            setError('Erro na análise IA: ' + e.message)
        } finally {
            setAnalyzing(false)
        }
    }

    return (
        <div className="p-8 max-w-5xl mx-auto font-sans min-h-screen bg-gray-50">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-2">
                    🔄 Gerenciador de Rodízio
                </h1>
                <button onClick={() => router.push('/oficina')} className="text-sm text-blue-600 hover:underline">
                    ← Voltar para Oficina
                </button>
            </div>

            {error && (
                <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded shadow-sm">
                    <p className="font-bold">Erro</p>
                    <p>{error}</p>
                </div>
            )}

            {result ? (
                <div className="bg-white border border-green-200 p-8 rounded-2xl flex flex-col items-center text-center shadow-lg animate-fade-in mx-auto max-w-2xl">
                    <div className="text-6xl mb-4">✅</div>
                    <h2 className="text-2xl font-bold text-green-800 mb-2">Rodízio Registrado!</h2>
                    <p className="text-green-600 mb-6 font-mono text-lg bg-green-50 px-4 py-1 rounded-full">
                        ID: {result.rodizio_id}
                    </p>

                    <div className="bg-white p-4 rounded-xl shadow-inner border border-gray-100 mb-6">
                        <img
                            src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=RODIZIO_${result.rodizio_id}`}
                            alt="QR Code"
                            className="rounded-lg opacity-90 hover:opacity-100 transition-opacity"
                        />
                    </div>

                    <button
                        onClick={() => { setResult(null); setSelectedTruckId(''); }}
                        className="mt-8 px-8 py-3 bg-green-600 text-white rounded-lg font-bold hover:bg-green-700 transition-all shadow-md hover:shadow-lg active:scale-95"
                    >
                        Criar Novo Rodízio
                    </button>
                </div>
            ) : (
                <div className="space-y-8">
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                        <label className="block text-sm font-semibold text-gray-700 mb-2 uppercase tracking-wide">
                            Selecione o Veículo para Análise
                        </label>
                        <select
                            className="w-full p-4 border border-gray-200 rounded-lg text-gray-700 bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-lg"
                            value={selectedTruckId}
                            onChange={(e) => setSelectedTruckId(e.target.value)}
                            disabled={loading || executing}
                        >
                            <option value="">-- Selecione um Caminhão --</option>
                            {trucks.map(t => (
                                <option key={t.id} value={t.id}>{t.placa}</option>
                            ))}
                        </select>
                    </div>

                    {loading && (
                        <div className="text-center py-12">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                            <p className="text-gray-500 animate-pulse">Analisando pneus...</p>
                        </div>
                    )}

                    {!loading && selectedTruckId && suggestions.length === 0 && !error && (
                        <div className="text-center py-16 bg-white rounded-xl border border-dashed border-gray-300 shadow-sm">
                            <span className="text-4xl block mb-2">👍</span>
                            <h3 className="text-xl font-medium text-gray-800">Tudo Certo!</h3>
                            <p className="text-gray-500 mt-2">Nenhuma sugestão de rodízio necessária.</p>
                        </div>
                    )}

                    {suggestions.length > 0 && (
                        <div className="animate-fade-in">
                            <div className="flex justify-between items-center mb-4 px-2">
                                <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                                    <span className="bg-blue-600 text-white text-sm rounded-full w-6 h-6 flex items-center justify-center shadow-sm">
                                        {suggestions.length}
                                    </span>
                                    Sugestões Encontradas
                                </h2>

                                <button
                                    onClick={analyzeWithAI}
                                    disabled={analyzing}
                                    className="text-sm bg-purple-100 text-purple-700 px-3 py-1.5 rounded-full shadow-sm hover:bg-purple-200 border border-purple-200 font-medium flex items-center gap-2 transition-colors"
                                >
                                    {analyzing ? '✨ Analisando...' : '✨ Analisar com IA'}
                                </button>
                            </div>

                            {/* AI ANALYSIS RESULT */}
                            {analysisResult && (
                                <div className="mb-6 bg-purple-50 border border-purple-100 p-4 rounded-xl shadow-sm animate-fade-in relative">
                                    <div className="absolute top-4 left-4 text-2xl">🤖</div>
                                    <div className="ml-10">
                                        <h3 className="text-sm font-bold text-purple-800 uppercase tracking-wide mb-1">Análise Inteligente</h3>
                                        <p className="text-purple-900 text-sm leading-relaxed">
                                            {analysisResult}
                                        </p>
                                    </div>
                                </div>
                            )}

                            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2">
                                {suggestions.map((s, idx) => (
                                    <div key={idx} className="bg-white border border-gray-100 rounded-xl p-0 shadow-sm hover:shadow-lg transition-all duration-300 group overflow-hidden">
                                        <div className="bg-gray-50 p-3 border-b border-gray-100 flex justify-between items-center">
                                            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Sugestão #{idx + 1}</span>
                                            <span className="text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded font-medium">
                                                Economia: +{s.economia_percentual.toFixed(1)}%
                                            </span>
                                        </div>

                                        <div className="p-5 flex items-center justify-between gap-4">
                                            <div className="flex-1 text-center">
                                                <div className="text-xs font-bold text-red-500 mb-1 uppercase">Remover</div>
                                                <div className="text-xl font-bold text-gray-800">{s.trocar_de.marca_fogo}</div>
                                                <div className="text-xs text-gray-500 mt-1 bg-gray-100 inline-block px-2 py-0.5 rounded">
                                                    Pos: {s.trocar_de.posicao_atual}
                                                </div>
                                                <div className="text-[10px] text-gray-400 mt-1">{s.trocar_de.desgaste_score.toFixed(0)}% Gasto</div>
                                            </div>

                                            <div className="text-gray-300 text-2xl group-hover:text-blue-500 group-hover:scale-110 transition-transform">
                                                ➔
                                            </div>

                                            <div className="flex-1 text-center">
                                                <div className="text-xs font-bold text-green-500 mb-1 uppercase">Instalar</div>
                                                <div className="text-xl font-bold text-gray-800">{s.trocar_para.marca_fogo}</div>
                                                <div className="text-xs text-gray-500 mt-1 bg-gray-100 inline-block px-2 py-0.5 rounded">
                                                    Estoque
                                                </div>
                                                <div className="text-[10px] text-gray-400 mt-1">{s.trocar_para.desgaste_score.toFixed(0)}% Gasto</div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="mt-8 flex justify-end pt-6 border-t border-gray-200">
                                <button
                                    onClick={executeRotation}
                                    disabled={executing}
                                    className="w-full md:w-auto bg-gradient-to-r from-blue-600 to-blue-700 text-white px-8 py-4 rounded-xl font-bold shadow-lg hover:shadow-xl hover:translate-y-[-2px] active:translate-y-[0px] active:scale-95 transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                                >
                                    {executing ? 'Processando...' : '✅ Aprovar e Executar Trocas'}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
