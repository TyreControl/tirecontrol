import { useDraggable, useDroppable } from '@dnd-kit/core'

interface DroppablePositionProps {
    id: string
    tire?: any
    onClick?: () => void
    disabled?: boolean
}

export function DroppablePosition({ id, tire, onClick, disabled }: DroppablePositionProps) {
    const { setNodeRef: setDropRef, isOver } = useDroppable({
        id,
        disabled: !!disabled,
    })

    const { attributes, listeners, setNodeRef: setDragRef, transform, isDragging } = useDraggable({
        id: tire?.id ?? `empty-${id}`,
        data: tire,
        disabled: !tire || !!disabled,
    })

    const dragStyle = transform
        ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
        : undefined

    return (
        <div
            ref={setDropRef}
            onClick={!disabled ? onClick : undefined}
            className={[
                'relative w-24 h-32 rounded-lg border-2 transition-all flex flex-col items-center justify-center p-2',
                tire ? 'border-blue-500 bg-blue-50' : 'border-dashed border-gray-300 bg-gray-50',
                isOver ? 'border-green-500 bg-green-50 scale-105' : '',
                !tire && !disabled ? 'cursor-pointer hover:border-gray-400' : '',
            ].join(' ')}
        >
            <div className="absolute -top-3 bg-gray-800 text-white text-[10px] px-2 py-0.5 rounded-full">
                {id}
            </div>

            {tire ? (
                <div
                    ref={setDragRef}
                    style={dragStyle}
                    {...listeners}
                    {...attributes}
                    className={`w-full flex flex-col items-center ${disabled ? '' : 'cursor-grab active:cursor-grabbing'} ${isDragging ? 'opacity-70' : ''}`}
                >
                    <div className="text-2xl mb-1">T</div>
                    <div className="font-bold text-xs text-center break-all">{tire.marca_fogo}</div>
                    <div className={`text-[10px] px-1 rounded mt-1 ${tire.sulco_atual < 3 ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                        {tire.sulco_atual}mm
                    </div>
                </div>
            ) : (
                <span className="text-gray-300 text-xs">Vazio</span>
            )}
        </div>
    )
}
