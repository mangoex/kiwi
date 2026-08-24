import React from 'react';
import { BranchInfo } from '../types';

interface BranchSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  branches: BranchInfo[];
  selectedBranchId: string | null;
  onSelectBranch: (branch: BranchInfo) => void;
  onRefreshLocation: () => void;
  isLoadingLocation?: boolean;
}

export const BranchSelectorModal: React.FC<BranchSelectorModalProps> = ({
  isOpen,
  onClose,
  branches,
  selectedBranchId,
  onSelectBranch,
  onRefreshLocation,
  isLoadingLocation = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-0 sm:p-4 animate-fade-in">
      <div 
        className="w-full max-w-lg bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden animate-slide-up"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-100 bg-emerald-700 text-white rounded-t-3xl sm:rounded-t-3xl">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-lg">
              📍
            </div>
            <div>
              <h2 className="text-lg font-bold">Seleccionar Sucursal</h2>
              <p className="text-xs text-emerald-100">Pide o recoge en la sucursal de tu preferencia</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center transition-colors text-white font-bold"
          >
            ✕
          </button>
        </div>

        {/* GPS Locate Button */}
        <div className="p-4 bg-emerald-50 border-b border-emerald-100">
          <button
            onClick={onRefreshLocation}
            disabled={isLoadingLocation}
            className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50"
          >
            <span className="text-base">{isLoadingLocation ? '⏳' : '🎯'}</span>
            {isLoadingLocation ? 'Detectando ubicación GPS...' : 'Detectar sucursal más cercana (GPS)'}
          </button>
        </div>

        {/* Branch List */}
        <div className="overflow-y-auto p-4 space-y-3 divide-y divide-gray-50 flex-1">
          {branches.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              No se encontraron sucursales disponibles en este momento.
            </div>
          ) : (
            branches.map((branch) => {
              const isSelected = branch.id === selectedBranchId;
              const hasDistance = branch.distance_km !== undefined && branch.distance_km !== null;
              const distanceDisplay = hasDistance
                ? (branch.distance_km! < 0.1
                    ? '📍 Estás aquí (<100m)'
                    : branch.distance_km! < 1
                    ? `📍 A ${Math.round(branch.distance_km! * 1000)} m`
                    : `📍 A ${branch.distance_km} km`)
                : null;

              return (
                <div
                  key={branch.id}
                  onClick={() => {
                    onSelectBranch(branch);
                    onClose();
                  }}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer flex flex-col gap-1.5 ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-50/50 shadow-sm ring-1 ring-emerald-500'
                      : 'border-gray-200 hover:border-emerald-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-gray-900 text-base">{branch.name}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 font-mono text-gray-600">
                        {branch.code}
                      </span>
                    </div>
                    {isSelected && (
                      <span className="text-xs font-bold bg-emerald-600 text-white px-2.5 py-0.5 rounded-full">
                        Seleccionada ✓
                      </span>
                    )}
                  </div>

                  {/* Address info */}
                  {(branch.street || branch.neighborhood || branch.city) && (
                    <div className="text-xs text-gray-600 flex items-start gap-1">
                      <span className="text-gray-400 mt-0.5">🏠</span>
                      <span>
                        {branch.street} {branch.exterior_number ? `#${branch.exterior_number}` : ''}
                        {branch.neighborhood ? `, Col. ${branch.neighborhood}` : ''}
                        {branch.city ? `, ${branch.city}` : ''}
                      </span>
                    </div>
                  )}

                  {/* Cross streets */}
                  {branch.cross_streets && (
                    <div className="text-xs text-emerald-800 bg-emerald-100/60 px-2 py-1 rounded-md">
                      🛣️ <span className="font-medium">Entre:</span> {branch.cross_streets}
                    </div>
                  )}

                  {/* Distance badge & phone */}
                  <div className="flex items-center justify-between mt-1 pt-1 border-t border-gray-100/60 text-xs">
                    {distanceDisplay ? (
                      <span className="text-emerald-700 font-semibold bg-emerald-100/80 px-2 py-0.5 rounded-md">
                        {distanceDisplay}
                      </span>
                    ) : (
                      <span className="text-gray-400 italic">Distancia no calculada</span>
                    )}
                    {branch.phone && (
                      <span className="text-gray-500 font-mono">
                        📞 {branch.phone}
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-gray-100 bg-gray-50">
          <button
            onClick={onClose}
            className="w-full py-3 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-xl font-bold text-sm transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
};
