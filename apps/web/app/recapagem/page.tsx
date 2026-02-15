'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'

type Pneu = {
    id: string
    marca_fogo: string
    marca?: string
    medida?: string
    ciclo_atual: number
    status: string
}

type OrdemRecapagem = {
    ordem_id: string
    recapadora_nome: string
    status: string
    data_criacao: string
    data_entrega_esperada?: string
    pneus_quantidade?: number
}

export default function RecapagemPage() {
    const router = useRouter()
    const [userProfile, setUserProfile] = useState<any>(null)
    const [activeTab, setActiveTab] = useState<'nova' | 'ativas'>('nova')
    const [loading, setLoading] = useState(false)
    const [msg, setMsg] = useState<{ type: 'success' | 'error', text: string } | null>(null)

    // Data for "Nova Ordem"
    const [stockTires, setStockTires] = useState<Pneu[]>([])
    const [selectedTires, setSelectedTires] = useState<string[]>([])
    const [recapadora, setRecapadora] = useState('')
    const [customRecapadora, setCustomRecapadora] = useState('')

    // Data for "Ordens Ativas"
    const [orders, setOrders] = useState<OrdemRecapagem[]>([])
    const [expandedOrder, setExpandedOrder] = useState<string | null>(null)
    const [orderItems, setOrderItems] = useState<Pneu[]>([]) // Tires in the expanded order

    useEffect(() => {
        const init = async () => {
            const profile = await getSessionProfile()
            if (!profile?.clienteId) {
                router.replace('/')
                return
            }
            setUserProfile(profile)
            loadStockTires(profile.clienteId)
            loadOrders(profile.clienteId)
        }
        init()
    }, [router])

    const loadStockTires = async (clienteId: string) => {
        const { data } = await supabase
            .from('pneus')
            .select('*')
            .eq('cliente_id', clienteId)
            .eq('status', 'ESTOQUE')
            .order('marca_fogo')
        if (data) setStockTires(data)
    }

    const loadOrders = async (clienteId: string) => {
        const { data } = await supabase
            .from('ordens_recapagem')
            .select('*')
            .eq('cliente_id', clienteId)
            .neq('status', 'concluido')
            .order('data_criacao', { ascending: false })

        if (data) setOrders(data)
    }

    const handleCreateOrder = async () => {
        if (!userProfile) return
        const recapName = recapadora === 'Outra' ? customRecapadora : recapadora

        if (!recapName) {
            setMsg({ type: 'error', text: 'Selecione ou digite o nome da recapadora.' })
            return
        }
        if (selectedTires.length === 0) {
            setMsg({ type: 'error', text: 'Selecione pelo menos um pneu.' })
            return
        }

        setLoading(true)
        setMsg(null)

        try {
            const selectedPneus = stockTires.filter(p => selectedTires.includes(p.id))
            const codes = selectedPneus.map(p => p.marca_fogo)

            const { data, error } = await supabase.rpc('rpc_tirecontrol_enviar_recapagem', {
                p_cliente_id: userProfile.clienteId,
                p_usuario_id: userProfile.userId,
                p_recapadora: recapName,
                p_codigos: codes
            })

            if (error) throw error

            setMsg({ type: 'success', text: `Ordem ${data.ordem_id} criada com sucesso!` })

            setTimeout(() => {
                loadStockTires(userProfile.clienteId)
                loadOrders(userProfile.clienteId)
                setSelectedTires([])
                setRecapadora('')
                setCustomRecapadora('')
                setActiveTab('ativas')
            }, 1000)

        } catch (e: any) {
            setMsg({ type: 'error', text: e.message })
        } finally {
            setLoading(false)
        }
    }

    const handleViewOrder = async (orderId: string) => {
        if (expandedOrder === orderId) {
            setExpandedOrder(null)
            return
        }
        setExpandedOrder(orderId)
        setOrderItems([])

        const { data } = await supabase
            .from('ordens_recapagem_pneus')
            .select('pneu_id, pneus(*)')
            .eq('ordem_id', orderId)

        if (data) {
            const items = data.map((d: any) => d.pneus)
            setOrderItems(items)
        }
    }

    const handleReceiveOrder = async (orderId: string, items: Pneu[]) => {
        const confirm = window.confirm(`Deseja receber todos os ${items.length} pneus desta ordem de volta ao Estoque?`)
        if (!confirm) return

        setLoading(true)
        try {
            const codes = items.map(p => p.marca_fogo)

            const { error: rpcError } = await supabase.rpc('rpc_tirecontrol_retorno_recapagem', {
                p_cliente_id: userProfile.clienteId,
                p_usuario_id: userProfile.userId,
                p_codigos: codes,
                p_observacao: `Retorno da Ordem ${orderId}`
            })

            if (rpcError) throw rpcError

            const { error: updateError } = await supabase
                .from('ordens_recapagem')
                .update({ status: 'concluido', data_ultima_atualizacao: new Date().toISOString() })
                .eq('ordem_id', orderId)

            if (updateError) throw updateError

            setMsg({ type: 'success', text: 'Pneus recebidos e ordem concluída!' })
            loadOrders(userProfile.clienteId)
            loadStockTires(userProfile.clienteId)
            setExpandedOrder(null)

        } catch (e: any) {
            setMsg({ type: 'error', text: 'Erro ao receber: ' + e.message })
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="p-8 max-w-5xl mx-auto font-sans bg-gray-50 min-h-screen">
            <h1 className="text-3xl font-bold mb-8 text-gray-800 flex items-center gap-2">
                🏭 Central de Recapagem
            </h1>

            {msg && (
                <div className={`p-4 mb-6 rounded-lg text-sm font-medium ${msg.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {msg.text}
                </div>
            )}

            <div className="flex border-b border-gray-200 mb-6">
                <button
                    onClick={() => setActiveTab('nova')}
                    className={`px-6 py-3 font-medium transition-colors border-b-2 ${activeTab === 'nova' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                >
                    Nova Ordem
                </button>
                <button
                    onClick={() => setActiveTab('ativas')}
                    className={`px-6 py-3 font-medium transition-colors border-b-2 ${activeTab === 'ativas' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                >
                    Ordens Ativas ({orders.length})
                </button>
            </div>

            {activeTab === 'nova' && (
                <div className="animate-fade-in space-y-6">
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                        <h3 className="text-lg font-semibold mb-4 text-gray-700">1. Selecione a Recapadora</h3>
                        <div className="flex gap-4">
                            <select
                                className="p-3 border rounded-lg w-full max-w-md"
                                value={recapadora}
                                onChange={(e) => setRecapadora(e.target.value)}
                            >
                                <option value="">Selecione...</option>
                                <option value="RecaPro">RecaPro</option>
                                <option value="RecaBrasil">RecaBrasil</option>
                                <option value="Outra">Outra (Digitar Nome)</option>
                            </select>
                            {recapadora === 'Outra' && (
                                <input
                                    type="text"
                                    placeholder="Nome da Recapadora"
                                    className="p-3 border rounded-lg w-full max-w-md"
                                    value={customRecapadora}
                                    onChange={(e) => setCustomRecapadora(e.target.value)}
                                />
                            )}
                        </div>
                    </div>

                    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-semibold text-gray-700">2. Selecione os Pneus (Do Estoque)</h3>
                            <span className="text-sm bg-blue-100 text-blue-800 px-2 py-1 rounded">
                                {selectedTires.length} selecionados
                            </span>
                        </div>

                        {stockTires.length === 0 ? (
                            <p className="text-gray-500 py-4">Nenhum pneu em estoque disponível.</p>
                        ) : (
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-h-[400px] overflow-y-auto p-2 border rounded-lg bg-gray-50">
                                {stockTires.map(p => (
                                    <label
                                        key={p.id}
                                        className={`cursor-pointer p-4 rounded-lg border transition-all ${selectedTires.includes(p.id) ? 'bg-blue-50 border-blue-500 shadow-sm' : 'bg-white border-gray-200 hover:border-blue-300'}`}
                                    >
                                        <div className="flex justify-between items-start">
                                            <input
                                                type="checkbox"
                                                className="mt-1"
                                                checked={selectedTires.includes(p.id)}
                                                onChange={(e) => {
                                                    if (e.target.checked) setSelectedTires([...selectedTires, p.id]);
                                                    else setSelectedTires(selectedTires.filter(id => id !== p.id));
                                                }}
                                            />
                                            <span className="text-xs font-mono text-gray-400">ID: {p.id.substring(0, 6)}...</span>
                                        </div>
                                        <div className="font-bold text-lg text-gray-800 mt-2">{p.marca_fogo}</div>
                                        <div className="text-xs text-gray-500">{p.marca} {p.medida}</div>
                                        <div className="text-xs mt-2 text-blue-600 bg-blue-50 inline-block px-1 rounded">Ciclo: {p.ciclo_atual}</div>
                                    </label>
                                ))}
                            </div>
                        )}
                    </div>

                    <button
                        onClick={handleCreateOrder}
                        disabled={loading}
                        className="w-full py-4 bg-blue-600 text-white font-bold rounded-lg hover:bg-blue-700 shadow-lg transition-transform active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? 'Processando Envio...' : '🚀 Gerar Ordem de Envio'}
                    </button>
                </div>
            )}

            {activeTab === 'ativas' && (
                <div className="space-y-4 animate-fade-in">
                    {orders.length === 0 ? (
                        <div className="text-center py-12 text-gray-500 bg-white rounded-lg border border-dashed border-gray-300">
                            Nenhuma ordem de recapagem ativa no momento.
                        </div>
                    ) : (
                        orders.map(order => (
                            <div key={order.ordem_id} className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
                                <div className="p-4 flex items-center justify-between bg-gray-50 border-b border-gray-100 cursor-pointer hover:bg-gray-100 transition-colors"
                                    onClick={() => handleViewOrder(order.ordem_id)}
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="bg-orange-100 text-orange-700 p-2 rounded-lg">
                                            📦
                                        </div>
                                        <div>
                                            <div className="font-bold text-gray-800">{order.recapadora_nome}</div>
                                            <div className="text-xs text-gray-500 font-mono">{order.ordem_id} • {new Date(order.data_criacao).toLocaleDateString()}</div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${order.status === 'enviado' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
                                            {order.status}
                                        </span>
                                        <span className="text-gray-400 transform transition-transform duration-200" style={{ transform: expandedOrder === order.ordem_id ? 'rotate(180deg)' : 'rotate(0deg)' }}>
                                            ▼
                                        </span>
                                    </div>
                                </div>

                                {expandedOrder === order.ordem_id && (
                                    <div className="p-6 bg-white border-t border-gray-100">
                                        <h4 className="font-semibold text-gray-700 mb-4">Pneus nesta ordem:</h4>
                                        <div className="space-y-2 mb-6">
                                            {orderItems.length === 0 ? <p className="text-sm text-gray-400">Carregando itens...</p> :
                                                orderItems.map(item => (
                                                    <div key={item.id} className="flex justify-between items-center bg-gray-50 p-3 rounded border border-gray-100">
                                                        <div className="flex items-center gap-3">
                                                            <div className="h-8 w-8 bg-gray-200 rounded-full flex items-center justify-center text-xs font-bold text-gray-600">
                                                                {item.marca_fogo.substring(0, 2)}
                                                            </div>
                                                            <div>
                                                                <div className="font-bold text-sm">{item.marca_fogo}</div>
                                                                <div className="text-xs text-gray-500">{item.marca} - {item.medida}</div>
                                                            </div>
                                                        </div>
                                                        <div className="text-xs text-gray-400 font-mono">{item.id}</div>
                                                    </div>
                                                ))
                                            }
                                        </div>

                                        <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
                                            <button
                                                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
                                                onClick={(e) => { e.stopPropagation(); setExpandedOrder(null); }}
                                            >
                                                Fechar
                                            </button>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleReceiveOrder(order.ordem_id, orderItems); }}
                                                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-bold shadow-sm"
                                            >
                                                ✅ Receber Pneus & Concluir
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    )
}
