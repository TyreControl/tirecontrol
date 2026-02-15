import { useDroppable } from '@dnd-kit/core'

interface DroppablePositionProps {
    id: string
    tire?: any
    onClick?: () => void
    disabled?: boolean
}

export function DroppablePosition({ id, tire, onClick, disabled }: DroppablePositionProps) {
    const { setNodeRef, isOver } = useDroppable({
        id: id,
        disabled: !!tire || disabled,
    })

    return (
        <div
            ref={setNodeRef}
            onClick={!disabled ? onClick : undefined}
            className={`
        relative w-24 h-32 rounded-lg border-2 transition-all flex flex-col items-center justify-center p-2
        ${tire ? 'border-blue-500 bg-blue-50' : 'border-dashed border-gray-300 bg-gray-50'}
        ${isOver && !tire ? 'border-green-500 bg-green-50 scale-105' : ''}
        ${!tire && !disabled ? 'cursor-pointer hover:border-gray-400' : ''}
      `}
        >
            <div className="absolute -top-3 bg-gray-800 text-white text-[10px] px-2 py-0.5 rounded-full">
                {id}
            </div>

            {tire ? (
                <>
                    <div className="text-2xl mb-1">🛞</div>
                    <div className="font-bold text-xs text-center break-all">{tire.marca_fogo}</div>
                    <div className={`text-[10px] px-1 rounded mt-1 ${tire.sulco_atual < 3 ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                        }`}>
                        {tire.sulco_atual}mm
                    </div>
                </>
            ) : (
                <span className="text-gray-300 text-xs">Vazio</span>
            )}
        </div>
    )
}
