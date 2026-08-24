import React from 'react';
import { BranchInfo } from '../types';
import { MapPin, Navigation, X, Check, Phone } from 'lucide-react';

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
    <div
      className="branch-modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="branch-modal-sheet" role="dialog" aria-modal="true" aria-label="Seleccionar sucursal">
        {/* Header */}
        <div className="branch-modal-header">
          <div className="branch-modal-header-left">
            <div className="branch-modal-header-icon-badge">
              <MapPin size={20} color="#10b981" />
            </div>
            <div>
              <h2 className="branch-modal-header-title">Seleccionar Sucursal</h2>
              <p className="branch-modal-header-subtitle">¿Dónde deseas ordenar o recoger tus productos?</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="branch-modal-close-btn"
            aria-label="Cerrar modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* GPS Button Banner */}
        <div className="branch-modal-gps-banner">
          <button
            type="button"
            onClick={onRefreshLocation}
            disabled={isLoadingLocation}
            className="branch-modal-gps-btn"
          >
            <Navigation size={15} />
            <span>{isLoadingLocation ? 'Detectando ubicación GPS…' : 'Detectar sucursal más cercana (GPS)'}</span>
          </button>
        </div>

        {/* Branch Cards List */}
        <div className="branch-cards-list">
          {branches.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
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
                  className={`branch-card ${isSelected ? 'active' : ''}`}
                  role="button"
                  tabIndex={0}
                >
                  <div className="branch-card-top-row">
                    <div className="branch-card-title-wrap">
                      <span className="branch-card-name">{branch.name}</span>
                      <span className="branch-card-code-badge">{branch.code}</span>
                    </div>
                    {isSelected && (
                      <span className="branch-card-active-tag">
                        <Check size={11} style={{ display: 'inline', marginRight: 3 }} />
                        Activa
                      </span>
                    )}
                  </div>

                  {/* Address info */}
                  {(branch.street || branch.neighborhood || branch.city) && (
                    <div className="branch-card-address-text">
                      {branch.street} {branch.exterior_number ? `#${branch.exterior_number}` : ''}
                      {branch.neighborhood ? `, Col. ${branch.neighborhood}` : ''}
                      {branch.city ? `, ${branch.city}` : ''}
                    </div>
                  )}

                  {/* Cross streets */}
                  {branch.cross_streets && (
                    <div>
                      <span className="branch-card-cross-streets">
                        🛣️ Entre: {branch.cross_streets}
                      </span>
                    </div>
                  )}

                  {/* Footer with Distance and Phone */}
                  <div className="branch-card-footer">
                    {distanceDisplay ? (
                      <span className="branch-card-distance-badge">
                        {distanceDisplay}
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontStyle: 'italic' }}>
                        Distancia no calculada
                      </span>
                    )}
                    {branch.phone && (
                      <span className="branch-card-phone">
                        <Phone size={11} style={{ display: 'inline', marginRight: 3 }} />
                        {branch.phone}
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="branch-modal-footer">
          <button
            type="button"
            onClick={onClose}
            className="branch-modal-btn-close"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
};
