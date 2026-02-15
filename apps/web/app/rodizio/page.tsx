'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { DndContext, DragEndEvent } from '@dnd-kit/core'
import { supabase } from '@/lib/supabase'
import { getSessionProfile } from '@/lib/auth'
import { TruckVisualizer } from '@/components/TruckVisualizer'

type Tire = {
    id: string
    posicao_veiculo: string | null
    [key: string]: any
}

type PendingSwap = {
    pneu_id: string
    posicao_origem: string
    nova_posicao: string
}

const VEHICLE_POSITIONS = ['1E', '1D', '2E', '2D', '3E', '3D']

function getBaselinePositions(tires: Tire[]) {
    return tires.reduce<Record<string, string>>((acc, tire) => {
        if (tire.posicao_veiculo) {
            acc[tire.id] = tire.posicao_veiculo
        }
        return acc
    }, {})
}

function buildPendingSwaps(tires: Tire[], baselinePositions: Record<string, string>): PendingSwap[] {
    return tires.reduce<PendingSwap[]>((acc, tire) => {
        const originalPosition = baselinePositions[tire.id]
        const currentPosition = tire.posicao_veiculo

        if (!originalPosition || !currentPosition || originalPosition === currentPosition) {
            return acc
        }

        acc.push({
            pneu_id: tire.id,
            posicao_origem: originalPosition,
            nova_posicao: currentPosition,
        })

        return acc
    }, [])
}

export default function RodizioPage() {
    const router = useRouter()
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const [vehicles, setVehicles] = useState<any[]>([])
    const [selectedVehicle, setSelectedVehicle] = useState<string>('')
    const [tires, setTires] = useState<Tire[]>([])
    const [baselinePositions, setBaselinePositions] = useState<Record<string, string>>({})
    const [pendingSwaps, setPendingSwaps] = useState<PendingSwap[]>([])

    useEffect(() => {
        const loadVehicles = async () => {
            setLoading(true)
            setError(null)

            const profile = await getSessionProfile()
            if (!profile?.clienteId) {
                router.replace('/')
                setLoading(false)
                return
            }

            const { data, error: vehiclesError } = await supabase
                .from('caminhoes')
                .select('*')
                .eq('cliente_id', profile.clienteId)

            if (vehiclesError) {
                setError(vehiclesError.message)
                setVehicles([])
                setLoading(false)
                return
            }

            setVehicles(data ?? [])
            setLoading(false)
        }

        void loadVehicles()
    }, [router])

    useEffect(() => {
        if (!selectedVehicle) {
            setTires([])
            setBaselinePositions({})
            setPendingSwaps([])
            setSuccess(null)
            return
        }

        const loadTires = async () => {
            setError(null)
            setSuccess(null)

            const { data, error: tiresError } = await supabase
                .from('pneus')
                .select('*')
                .eq('veiculo_id', selectedVehicle)

            if (tiresError) {
                setError(tiresError.message)
                return
            }

            const loadedTires = (data ?? []) as Tire[]
            setTires(loadedTires)
            setBaselinePositions(getBaselinePositions(loadedTires))
            setPendingSwaps([])
        }

        void loadTires()
    }, [selectedVehicle])

    function handleDragEnd(event: DragEndEvent) {
        const { active, over } = event
        if (!over) return

        const draggedId = String(active.id)
        const targetPos = String(over.id)
        if (!VEHICLE_POSITIONS.includes(targetPos)) return

        const draggedTire = tires.find(t => t.id === draggedId)
        if (!draggedTire?.posicao_veiculo || draggedTire.posicao_veiculo === targetPos) return

        const sourcePos = draggedTire.posicao_veiculo
        const targetTire = tires.find(t => t.posicao_veiculo === targetPos)

        const nextTires = tires.map(t => {
            if (t.id === draggedId) return { ...t, posicao_veiculo: targetPos }
            if (targetTire && t.id === targetTire.id) return { ...t, posicao_veiculo: sourcePos }
            return t
        })

        setTires(nextTires)
        setPendingSwaps(buildPendingSwaps(nextTires, baselinePositions))
        setSuccess(null)
    }

    async function saveRotation() {
        if (!selectedVehicle || pendingSwaps.length === 0) return

        setSaving(true)
        setError(null)
        setSuccess(null)

        try {
            const updates = await Promise.all(
                pendingSwaps.map(change =>
                    supabase
                        .from('pneus')
                        .update({ posicao_veiculo: change.nova_posicao })
                        .eq('id', change.pneu_id)
                        .eq('veiculo_id', selectedVehicle)
                )
            )

            const failedUpdate = updates.find(update => update.error)
            if (failedUpdate?.error) {
                throw failedUpdate.error
            }

            const { data: freshTires, error: reloadError } = await supabase
                .from('pneus')
                .select('*')
                .eq('veiculo_id', selectedVehicle)

            if (reloadError) throw reloadError

            const normalizedTires = (freshTires ?? []) as Tire[]
            setTires(normalizedTires)
            setBaselinePositions(getBaselinePositions(normalizedTires))
            setPendingSwaps([])
            setSuccess('Rodizio salvo com sucesso.')
        } catch (err: any) {
            setError(err.message ?? 'Erro ao salvar rodizio.')
        } finally {
            setSaving(false)
        }
    }

    if (loading) {
        return <div className="p-8 max-w-6xl mx-auto">Carregando veiculos...</div>
    }

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <h1 className="text-3xl font-bold mb-8">Rodizio Visual</h1>

            {error && (
                <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            {success && (
                <div className="mb-6 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                    {success}
                </div>
            )}

            <div className="mb-8">
                <label className="block text-sm font-bold mb-2">Selecione o Veiculo</label>
                <select
                    className="p-2 border rounded w-full max-w-xs"
                    value={selectedVehicle}
                    onChange={e => setSelectedVehicle(e.target.value)}
                    disabled={saving}
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
                        positions={VEHICLE_POSITIONS}
                    />
                </DndContext>
            )}

            {pendingSwaps.length > 0 && (
                <div className="fixed bottom-8 right-8">
                    <button
                        onClick={saveRotation}
                        disabled={saving}
                        className="bg-green-600 text-white px-6 py-3 rounded-full shadow-lg font-bold hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {saving ? 'Salvando...' : `Salvar ${pendingSwaps.length} alteracoes`}
                    </button>
                </div>
            )}
        </div>
    )
}
