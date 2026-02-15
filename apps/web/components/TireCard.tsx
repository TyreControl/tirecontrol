import { useDraggable } from '@dnd-kit/core'

interface TireCardProps {
    tire: any
}

export function TireCard({ tire }: TireCardProps) {
    const { attributes, listeners, setNodeRef, transform } = useDraggable({
        id: tire.id,
        data: tire,
    })

    const style = transform ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    } : undefined

    return (
        <div
            ref={setNodeRef}
            style={style}
            {...listeners}
            {...attributes}
            className="p-3 bg-white border border-gray-200 rounded shadow-sm hover:shadow-md cursor-grab active:cursor-grabbing"
        >
            <div className="flex items-center gap-2">
                <span className="text-xl">🛞</span>
                <div>
                    <div className="font-bold text-sm">{tire.marca_fogo}</div>
                    <div className="text-xs text-gray-500">{tire.marca} • {tire.medida}</div>
                </div>
            </div>
            <div className="mt-2 flex justify-between items-center">
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${tire.sulco_atual < 3 ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                    }`}>
                    {tire.sulco_atual} mm
                </span>
                <span className="text-xs text-gray-400">
                    {tire.km_atual} km
                </span>
            </div>
        </div>
    )
}
