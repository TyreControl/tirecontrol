import { DroppablePosition } from './DroppablePosition'

interface TruckVisualizerProps {
    tires: any[]
    positions: string[]
    onTireClick?: (tire: any) => void
}

export function TruckVisualizer({ tires, positions, onTireClick }: TruckVisualizerProps) {
    const getTireAtPosition = (pos: string) => tires.find(t => t.posicao_veiculo === pos)

    // Simple layout for 2-axle or 3-axle truck
    // Front Axle: 1E, 1D
    // Rear Axles: 2E/2D, 3E/3D (simplified)

    const frontAxle = positions.filter(p => p.startsWith('1'))
    const rearAxles = positions.filter(p => !p.startsWith('1'))

    return (
        <div className="bg-gray-100 p-8 rounded-xl border border-gray-300 max-w-md mx-auto">
            {/* Front Axle */}
            <div className="flex justify-between mb-12 relative">
                <div className="absolute w-full h-2 bg-gray-400 top-1/2 -z-10"></div>
                {frontAxle.map(pos => (
                    <DroppablePosition
                        key={pos}
                        id={pos}
                        tire={getTireAtPosition(pos)}
                        onClick={() => onTireClick?.(getTireAtPosition(pos))}
                    />
                ))}
            </div>

            {/* Rear Axles */}
            <div className="space-y-8">
                {/* Group by axle number for better visual */}
                {['2', '3', '4'].map(axleNum => {
                    const axlePositions = rearAxles.filter(p => p.startsWith(axleNum))
                    if (axlePositions.length === 0) return null

                    return (
                        <div key={axleNum} className="flex justify-between relative">
                            <div className="absolute w-full h-2 bg-gray-400 top-1/2 -z-10"></div>
                            {axlePositions.map(pos => (
                                <DroppablePosition
                                    key={pos}
                                    id={pos}
                                    tire={getTireAtPosition(pos)}
                                    onClick={() => onTireClick?.(getTireAtPosition(pos))}
                                />
                            ))}
                        </div>
                    )
                })}
            </div>

            <div className="mt-8 text-center text-gray-400 text-sm font-mono">
                FRENTE DO VEÍCULO ↑
            </div>
        </div>
    )
}
