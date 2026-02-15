'use client'

import { useState, useEffect } from 'react'
import { DndContext, DragEndEvent } from '@dnd-kit/core'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'
import { TruckVisualizer } from '@/components/TruckVisualizer'

export default function RodizioPage() {
    const [loading, setLoading] = useState(true)
    const [vehicles, setVehicles] = useState<any[]>([])
    const [selectedVehicle, setSelectedVehicle] = useState<string>('')
    const [tires, setTires] = useState<any[]>([])
    const [pendingSwaps, setPendingSwaps] = useState<any[]>([])

    useEffect(() => {
        loadVehicles()
    }, [])

    useEffect(() => {
        if (selectedVehicle) loadTires(selectedVehicle)
    }, [selectedVehicle])

    async function loadVehicles() {
        const profile = await getSessionProfile()
        if (!profile) return
        const { data } = await supabase.from('caminhoes').select('*').eq('cliente_id', profile.clienteId)
        if (data) setVehicles(data)
        setLoading(false)
    }

    async function loadTires(veiculoId: string) {
        const { data } = await supabase.from('pneus').select('*').eq('veiculo_id', veiculoId)
        if (data) setTires(data)
    }

    function handleDragEnd(event: DragEndEvent) {
        const { active, over } = event
        if (!over || active.id === over.id) return

        const sourcePos = tires.find(t => t.id === active.id)?.posicao_veiculo
        const targetPos = over.id as string

        // Simple verification: if target is empty? or swapping?
        // For now, simplify logic to just swap in UI state
        // In real app, we need complex logic here

        console.log(`Swap ${sourcePos} -> ${targetPos}`)

        // Update local state for visual feedback
        const newTires = tires.map(t => {
            if (t.id === active.id) return { ...t, posicao_veiculo: targetPos }
            if (t.posicao_veiculo === targetPos) return { ...t, posicao_veiculo: sourcePos } // Swap
            return t
        })
        setTires(newTires)
        setPendingSwaps([...pendingSwaps, { pneu_id: active.id, nova_posicao: targetPos }])
    }

    async function saveRotation() {
        // Call RPC
        alert('Funcionalidade de salvar simulada! RPC seria chamado aqui.')
    }

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <h1 className="text-3xl font-bold mb-8">🚛 Rodízio Visual</h1>

            <div className="mb-8">
                <label className="block text-sm font-bold mb-2">Selecione o Veículo</label>
                <select
                    className="p-2 border rounded w-full max-w-xs"
                    value={selectedVehicle}
                    onChange={e => setSelectedVehicle(e.target.value)}
                >
                    <option value="">Selecione...</option>
                    {vehicles.map(v => (
                        <option key={v.id} value={v.id}>{v.placa} - {v.modelo}</option>
                    ))}
                </select>
            </div>

            {selectedVehicle && (
                <DndContext onDragEnd={handleDragEnd}>
                    <TruckVisualizer
                        tires={tires}
                        positions={['1E', '1D', '2E', '2D', '3E', '3D']}
                    />
                </DndContext>
            )}

            {pendingSwaps.length > 0 && (
                <div className="fixed bottom-8 right-8">
                    <button
                        onClick={saveRotation}
                        className="bg-green-600 text-white px-6 py-3 rounded-full shadow-lg font-bold hover:bg-green-700"
                    >
                        Salvar {pendingSwaps.length} Trocas
                    </button>
                </div>
            )}
        </div>
    )
}
