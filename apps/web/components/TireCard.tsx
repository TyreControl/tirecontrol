'use client'

import { DragEvent } from 'react'

export type TireProps = {
    id: string
    marcaFogo: string
    posicao: string
    sulco?: number
    marca?: string
    status: 'MONTADO' | 'ESTOQUE'
}

type TireCardProps = {
    tire: TireProps
    onDragStart: (e: DragEvent<HTMLDivElement>, tire: TireProps) => void
}

export function TireCard({ tire, onDragStart }: TireCardProps) {
    return (
        <div
            draggable
            onDragStart={(e) => onDragStart(e, tire)}
            className="p-2 bg-blue-100 border-2 border-blue-300 rounded cursor-grab active:cursor-grabbing shadow-sm hover:shadow-md transition-all select-none"
            title={`ID: ${tire.id}`}
        >
            <div className="text-xs font-bold text-blue-900 text-center">{tire.marcaFogo}</div>
            {tire.marca && <div className="text-[10px] text-blue-700 text-center truncate">{tire.marca}</div>}
            <div className="text-[10px] text-gray-500 text-center mt-1">{tire.posicao}</div>
        </div>
    )
}
