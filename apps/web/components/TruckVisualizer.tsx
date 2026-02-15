'use client'

import { DragEvent } from 'react'
import { DroppablePosition } from './DroppablePosition'
import { TireCard, TireProps } from './TireCard'

type TruckVisualizerProps = {
    tires: TireProps[]
    onTireMove: (tireId: string, newPosition: string) => void
}

const AXLES = [
    { id: 'FRONT', positions: ['FL', 'FR'], label: 'DIANTEIRO' },
    { id: 'DRIVE', positions: ['BL_OUT', 'BL_IN', 'BR_IN', 'BR_OUT'], label: 'TRAÇÃO' },
    // Add more axles as needed or make dynamic
]

export function TruckVisualizer({ tires, onTireMove }: TruckVisualizerProps) {
    const getTireAtPosition = (pos: string) => tires.find((t) => t.posicao === pos && t.status === 'MONTADO')

    const handleDragStart = (e: DragEvent<HTMLDivElement>, tire: TireProps) => {
        e.dataTransfer.setData('tireId', tire.id)
        e.dataTransfer.effectAllowed = 'move'
    }

    const handleDrop = (e: DragEvent<HTMLDivElement>, targetPosition: string) => {
        e.preventDefault()
        const tireId = e.dataTransfer.getData('tireId')
        if (tireId) {
            onTireMove(tireId, targetPosition)
        }
    }

    return (
        <div className="flex flex-col items-center gap-8 bg-gray-50 p-6 rounded-lg border border-gray-200">
            {/* Frente do Caminhão */}
            <div className="w-40 h-10 bg-gray-300 rounded-t-lg mb-2 flex items-center justify-center text-gray-600 text-sm">
                FRENTE
            </div>

            {AXLES.map((axle) => (
                <div key={axle.id} className="relative w-full max-w-sm">
                    <div className="absolute top-1/2 left-0 w-full h-2 bg-gray-300 -z-10 transform -translate-y-1/2 rounded" />
                    <div className="flex justify-center gap-8">
                        {/* Esquerda */}
                        <div className="flex gap-2">
                            {axle.positions.filter(p => p.includes('L')).reverse().map(pos => (
                                <DroppablePosition
                                    key={pos}
                                    positionId={pos}
                                    label={pos}
                                    onDrop={handleDrop}
                                >
                                    {(() => {
                                        const tire = getTireAtPosition(pos)
                                        return tire ? <TireCard tire={tire} onDragStart={handleDragStart} /> : null
                                    })()}
                                </DroppablePosition>
                            ))}
                        </div>

                        {/* Direita */}
                        <div className="flex gap-2">
                            {axle.positions.filter(p => p.includes('R')).map(pos => (
                                <DroppablePosition
                                    key={pos}
                                    positionId={pos}
                                    label={pos}
                                    onDrop={handleDrop}
                                >
                                    {(() => {
                                        const tire = getTireAtPosition(pos)
                                        return tire ? <TireCard tire={tire} onDragStart={handleDragStart} /> : null
                                    })()}
                                </DroppablePosition>
                            ))}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    )
}
