import React, { useState } from 'react';
import { ChevronRight, ChevronDown, Carrot, Layers, Sliders, CheckSquare, Square, AlertCircle } from 'lucide-react';

export interface DagModifier {
  id: string;
  name: string;
  extraCostCents: number;
  isSelected?: boolean;
}

export interface DagNode {
  id: string;
  title: string;
  type: 'ingredient' | 'subrecipe' | 'modifier_group';
  sku?: string;
  quantityUsed?: string;
  mermaPercent?: number; // e.g. 5 for 5% merma
  costBase?: string; // e.g. "$22.50 / kg"
  directCostCents: number; // in cents or recalculated cost
  children?: DagNode[];
  modifiers?: DagModifier[];
  defaultExpanded?: boolean;
}

export interface DagTreeViewProps {
  rootTitle: string;
  rootSku?: string;
  nodes: DagNode[];
  totalDirectCostCents?: number;
  onModifierToggle?: (modifierId: string) => void;
}

export const DagNodeItem: React.FC<{
  node: DagNode;
  level?: number;
  onModifierToggle?: (modifierId: string) => void;
}> = ({ node, level = 0, onModifierToggle }) => {
  const [isExpanded, setIsExpanded] = useState(node.defaultExpanded ?? true);

  const formatMoney = (cents: number) => `$${(cents / 100).toFixed(2)} MXN`;

  const renderIcon = () => {
    switch (node.type) {
      case 'ingredient':
        return <Carrot size={14} className="text-emerald-600 shrink-0" />;
      case 'subrecipe':
        return <Layers size={14} className="text-amber-600 shrink-0" />;
      case 'modifier_group':
        return <Sliders size={14} className="text-violet-600 shrink-0" />;
      default:
        return <ChevronRight size={14} className="text-gray-400 shrink-0" />;
    }
  };

  const hasChildren = (node.children && node.children.length > 0) || (node.modifiers && node.modifiers.length > 0);

  return (
    <div className={`text-xs ${level > 0 ? 'ml-3 pl-3 border-l-2 border-gray-100' : ''} my-1.5`}>
      <div className="flex items-start justify-between gap-2 p-2 rounded-md hover:bg-gray-50/80 transition-colors border border-transparent hover:border-gray-200">
        <div className="flex items-start gap-1.5 flex-1 min-w-0">
          {hasChildren ? (
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-0.5 text-gray-400 hover:text-gray-600 rounded mt-0.5"
              aria-label={isExpanded ? 'Colapsar nodo' : 'Expandir nodo'}
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
          ) : (
            <span className="w-4 shrink-0" />
          )}

          <div className="mt-0.5">{renderIcon()}</div>

          <div className="flex-1 min-w-0">
            <div className="font-semibold text-gray-900 flex items-center gap-1.5 flex-wrap">
              <span>{node.title}</span>
              {node.sku && <span className="text-[10px] text-gray-400 bg-gray-100 px-1 py-0.2 rounded font-mono">SKU: {node.sku}</span>}
              {node.costBase && <span className="text-[10px] text-gray-500 font-normal">({node.costBase})</span>}
            </div>

            <div className="text-[11px] text-gray-500 flex items-center gap-2 mt-0.5 flex-wrap">
              {node.quantityUsed && <span>Cantidad: <strong className="text-gray-700">{node.quantityUsed}</strong></span>}
              {node.mermaPercent !== undefined && (
                <span className="text-amber-700 bg-amber-50 px-1.5 py-0.2 rounded border border-amber-200">
                  Merma: <strong>{node.mermaPercent}%</strong>
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="text-right shrink-0">
          <div className="font-bold text-gray-900 text-xs">
            {formatMoney(node.directCostCents)}
          </div>
          <div className="text-[10px] text-gray-400">Costo directo</div>
        </div>
      </div>

      {/* Nested Children (Subrecipes or Items) */}
      {isExpanded && node.children && node.children.length > 0 && (
        <div className="space-y-1">
          {node.children.map((child) => (
            <DagNodeItem
              key={child.id}
              node={child}
              level={level + 1}
              onModifierToggle={onModifierToggle}
            />
          ))}
        </div>
      )}

      {/* Nested Modifiers (Unifies old Secuencias modal into inline tree) */}
      {isExpanded && node.modifiers && node.modifiers.length > 0 && (
        <div className="ml-4 pl-3 border-l-2 border-violet-100 my-1 space-y-1 bg-violet-50/20 p-2 rounded-r-md">
          <div className="text-[10px] font-bold text-violet-800 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Sliders size={11} /> Modificadores de Secuencia
          </div>
          {node.modifiers.map((mod) => (
            <div
              key={mod.id}
              onClick={() => onModifierToggle?.(mod.id)}
              className="flex items-center justify-between text-xs py-1 px-1.5 rounded hover:bg-violet-50/60 cursor-pointer select-none transition-colors"
            >
              <div className="flex items-center gap-2">
                {mod.isSelected ? (
                  <CheckSquare size={13} className="text-violet-600" />
                ) : (
                  <Square size={13} className="text-gray-400" />
                )}
                <span className={mod.isSelected ? 'font-medium text-gray-900' : 'text-gray-600'}>
                  {mod.name}
                </span>
              </div>
              <span className="text-[11px] font-mono text-gray-500">
                {mod.extraCostCents > 0 ? `+${formatMoney(mod.extraCostCents)}` : '+$0.00'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const DagTreeView: React.FC<DagTreeViewProps> = ({
  rootTitle,
  rootSku,
  nodes,
  totalDirectCostCents,
  onModifierToggle,
}) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-xs">
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-100">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
          <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
            {rootTitle}
          </h4>
          {rootSku && (
            <span className="text-[10px] font-mono bg-gray-100 text-gray-600 px-1 py-0.5 rounded">
              SKU {rootSku}
            </span>
          )}
        </div>
        {totalDirectCostCents !== undefined && (
          <div className="text-right">
            <span className="text-[10px] text-gray-400 block">Costo Directo Total</span>
            <span className="text-xs font-extrabold text-emerald-700">
              ${(totalDirectCostCents / 100).toFixed(2)} MXN
            </span>
          </div>
        )}
      </div>

      <div className="space-y-0.5">
        {nodes.map((node) => (
          <DagNodeItem
            key={node.id}
            node={node}
            level={0}
            onModifierToggle={onModifierToggle}
          />
        ))}
      </div>
    </div>
  );
};

export default DagTreeView;
