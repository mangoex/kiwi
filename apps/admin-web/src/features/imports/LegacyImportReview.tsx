import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Database, FileWarning, CheckCircle2, Clock3 } from 'lucide-react';
import { fetchApi } from '@restaurantos/api-client';
import { resolveBranchId } from '../../lib/branchContext';

interface ImportBatch {
  id: string;
  source_system: string;
  manifest_checksum: string;
  status: string;
  summary: Record<string, number>;
  created_at: string;
}

interface ImportRecord {
  id: string;
  entity_type: string;
  source_key: string;
  source_row: number;
  status: string;
  reason_code: string | null;
  target_entity_id: string | null;
}

interface RecordPage {
  items: ImportRecord[];
  total: number;
  limit: number;
  offset: number;
}

const statusLabels: Record<string, string> = {
  loading: 'Cargando',
  review: 'Requiere revisión',
  completed: 'Completado',
  imported: 'Importado',
  linked: 'Vinculado',
  needs_review: 'Requiere revisión',
  rejected: 'Rechazado',
};

const reasonLabels: Record<string, string> = {
  missing_station: 'Falta asignar estación antes de activar el producto',
  missing_supplier: 'Falta vincular un proveedor',
  missing_recipe_components: 'El archivo no contiene ingredientes, cantidades ni rendimiento',
  sku_conflict: 'La clave ya existe en otro alcance; requiere conciliación',
};

export default function LegacyImportReview() {
  const branchId = resolveBranchId();
  const [selectedBatchId, setSelectedBatchId] = useState('');
  const batchesQuery = useQuery<ImportBatch[]>({
    queryKey: ['legacy-imports', branchId],
    queryFn: () => fetchApi(`/legacy-imports?branch_id=${encodeURIComponent(branchId)}`),
    enabled: Boolean(branchId),
  });
  const activeBatchId = selectedBatchId || batchesQuery.data?.[0]?.id || '';
  const recordsQuery = useQuery<RecordPage>({
    queryKey: ['legacy-import-records', activeBatchId],
    queryFn: () => fetchApi(`/legacy-imports/${encodeURIComponent(activeBatchId)}/records?status=needs_review&limit=100`),
    enabled: Boolean(activeBatchId),
  });

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 28 }}>
        <div style={{ padding: 12, borderRadius: 14, color: '#047857', background: '#d1fae5' }}><Database size={28} /></div>
        <div>
          <h1 className="premium-header-title" style={{ margin: 0 }}>Importaciones de sucursal</h1>
          <p className="premium-header-subtitle" style={{ margin: '5px 0 0' }}>Revisa lo importado y completa los datos que el sistema anterior no entregó.</p>
        </div>
      </div>

      {!branchId && <div role="alert" style={{ color: '#b91c1c' }}>Selecciona una sucursal para consultar sus importaciones.</div>}
      {batchesQuery.isError && <div role="alert" style={{ color: '#b91c1c' }}>No se pudieron cargar los lotes.</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 14, marginBottom: 24 }}>
        {(batchesQuery.data || []).map((batch) => (
          <button
            key={batch.id}
            type="button"
            onClick={() => setSelectedBatchId(batch.id)}
            style={{ textAlign: 'left', padding: 18, borderRadius: 14, border: activeBatchId === batch.id ? '2px solid #10b981' : '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <strong>{batch.source_system}</strong>
              {batch.status === 'completed' ? <CheckCircle2 size={19} color="#16a34a" /> : <Clock3 size={19} color="#d97706" />}
            </div>
            <div style={{ color: '#64748b', marginTop: 8, fontSize: 13 }}>{statusLabels[batch.status] || batch.status}</div>
            <div style={{ display: 'flex', gap: 12, marginTop: 10, color: '#334155', fontSize: 13 }}>
              <span>{batch.summary.imported || 0} importados</span>
              <span>{batch.summary.needs_review || 0} por revisar</span>
            </div>
          </button>
        ))}
      </div>

      <div className="premium-card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: 18, borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: 10 }}>
          <FileWarning size={20} color="#d97706" />
          <strong>Pendientes de revisión ({recordsQuery.data?.total || 0})</strong>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="premium-table">
            <thead><tr><th>Tipo</th><th>Clave origen</th><th>Fila</th><th>Motivo</th><th>Destino</th></tr></thead>
            <tbody>
              {(recordsQuery.data?.items || []).map((record) => (
                <tr key={record.id}>
                  <td>{record.entity_type}</td>
                  <td>{record.source_key}</td>
                  <td>{record.source_row}</td>
                  <td>{reasonLabels[record.reason_code || ''] || record.reason_code || 'Revisión manual'}</td>
                  <td>{record.target_entity_id ? 'Creado para ajustar' : 'Pendiente de vincular'}</td>
                </tr>
              ))}
              {!recordsQuery.isLoading && (recordsQuery.data?.items.length || 0) === 0 && (
                <tr><td colSpan={5} style={{ padding: 32, textAlign: 'center', color: '#64748b' }}>No hay registros pendientes en este lote.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
