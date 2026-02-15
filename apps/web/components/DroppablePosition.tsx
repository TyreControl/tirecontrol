'use client'

import { DragEvent, ReactNode } from 'react'

type DroppablePositionProps = {
    positionId: string
    label: string
    children?: ReactNode
    onDrop: (e: DragEvent<HTMLDivElement>, targetPosition: string) => void
    isOver?: boolean
}

export function DroppablePosition({ positionId, label, children, onDrop }: DroppablePositionProps) {
    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
    }

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        onDrop(e, positionId)
    }

    return (
        <div
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            className={`
        w-20 h-28 border-2 border-dashed rounded flex flex-col items-center justify-center relative transition-colors
        ${children ? 'border-gray-300 bg-gray-50' : 'border-gray-400 bg-gray-100 opacity-70 hover:bg-yellow-50 hover:border-yellow-400'}
      `}
        >
            <span className="absolute -top-6 text-xs font-bold text-gray-500">{label}</span>
            {children}
        </div>
    )
}
