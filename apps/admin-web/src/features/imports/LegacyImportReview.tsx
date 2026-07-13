import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  ChefHat,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Database,
  Package,
  Search,
  Truck,
} from 'lucide-react';
import { fetchApi } from '@restaurantos/api-client';
import { resolveBranchId } from '../../lib/branchContext';

type PendingType = 'presentation' | 'product' | 'recipe';

interface ImportBatch {
  id: string;
  source_system: string;
  manifest_checksum: string;
  status: string;
  summary: Record<string, number>;
  entity_summary: Record<string, Record<string, number>>;
  created_at: string;
}

interface ImportRecord {
  id: string;
  entity_type: PendingType;
  source_key: string;
  source_row: number;
  status: string;
  reason_code: string | null;
  target_entity_id: string | null;
  normalized_payload: Record<string, unknown>;
}

interface RecordPage {
  items: ImportRecord[];
  total: number;
  limit: number;
  offset: number;
}

interface ReviewFlow {
  label: string;
  singular: string;
  description: string;
  steps: string[];
  actionLabel: string;
  icon: typeof Package;
  color: string;
  background: string;
}

const PAGE_SIZE = 25;

const reviewFlows: Record<PendingType, ReviewFlow> = {
  presentation: {
    label: 'Presentaciones',
    singular: 'Presentación',
    description: 'El archivo contiene unidad y rendimiento, pero no identifica al proveedor.',
    steps: [
      'Comprueba el nombre, la unidad y el rendimiento heredados.',
      'Abre Proveedores y crea o selecciona el proveedor real.',
      'Registra la presentación de compra; el costo heredado es sólo referencia.',
    ],
    actionLabel: 'Ir a Proveedores',
    icon: Truck,
    color: '#0369a1',
    background: '#e0f2fe',
  },
  product: {
    label: 'Productos',
    singular: 'Producto',
    description: 'El producto existe, pero no puede venderse hasta asignarle una estación.',
    steps: [
      'Abre el producto usando su clave como búsqueda.',
      'Confirma categoría, precio y asigna Cocina, Bebidas o Empaque.',
      'Cambia el estado a Activo sólo después de completar la configuración.',
    ],
    actionLabel: 'Configurar producto',
    icon: Package,
    color: '#047857',
    background: '#d1fae5',
  },
  recipe: {
    label: 'Recetas',
    singular: 'Receta',
    description: 'El archivo repetía productos y no incluía ingredientes ni rendimiento.',
    steps: [
      'Localiza el producto mediante su clave.',
      'Abre Receta y captura ingredientes, cantidades, unidades y rendimiento.',
      'No guardes una receta vacía ni supongas componentes inexistentes.',
    ],
    actionLabel: 'Capturar receta',
    icon: ChefHat,
    color: '#b45309',
    background: '#fef3c7',
  },
};

const pendingTypes = Object.keys(reviewFlows) as PendingType[];

function textValue(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

function recordIdentity(record: ImportRecord) {
  const payload = record.normalized_payload || {};
  return {
    name: textValue(payload.name) || 'Sin descripción heredada',
    sku: textValue(payload.sku) || record.source_key,
    unit: textValue(payload.unit_code),
    yieldValue: textValue(payload.yield),
  };
}

function actionPath(type: PendingType, record?: ImportRecord): string {
  if (type === 'presentation') return '/suppliers';
  const sku = record ? recordIdentity(record).sku : '';
  return sku ? `/products?search=${encodeURIComponent(sku)}` : '/products';
}

export default function LegacyImportReview() {
  const branchId = resolveBranchId();
  const [selectedBatchId, setSelectedBatchId] = useState('');
  const [selectedType, setSelectedType] = useState<PendingType>('presentation');
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');

  const batchesQuery = useQuery<ImportBatch[]>({
    queryKey: ['legacy-imports', branchId],
    queryFn: () => fetchApi(`/legacy-imports?branch_id=${encodeURIComponent(branchId)}`),
    enabled: Boolean(branchId),
  });
  const activeBatchId = selectedBatchId || batchesQuery.data?.[0]?.id || '';
  const activeBatch = batchesQuery.data?.find((batch) => batch.id === activeBatchId);
  const recordsQuery = useQuery<RecordPage>({
    queryKey: ['legacy-import-records', activeBatchId, selectedType, page],
    queryFn: () => fetchApi(
      `/legacy-imports/${encodeURIComponent(activeBatchId)}/records`
      + `?status=needs_review&entity_type=${selectedType}&limit=${PAGE_SIZE}`
      + `&offset=${page * PAGE_SIZE}`,
    ),
    enabled: Boolean(activeBatchId),
  });

  const filteredRecords = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('es-MX');
    if (!term) return recordsQuery.data?.items || [];
    return (recordsQuery.data?.items || []).filter((record) => {
      const identity = recordIdentity(record);
      return [identity.name, identity.sku, record.source_key]
        .some((value) => value.toLocaleLowerCase('es-MX').includes(term));
    });
  }, [recordsQuery.data?.items, search]);

  const flow = reviewFlows[selectedType];
  const pageTotal = recordsQuery.data?.total || 0;
  const firstItem = pageTotal === 0 ? 0 : page * PAGE_SIZE + 1;
  const lastItem = Math.min((page + 1) * PAGE_SIZE, pageTotal);

  const selectType = (type: PendingType) => {
    setSelectedType(type);
    setPage(0);
    setSearch('');
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 28 }}>
        <div style={{ padding: 12, borderRadius: 14, color: '#047857', background: '#d1fae5' }}>
          <Database size={28} />
        </div>
        <div>
          <h1 className="premium-header-title" style={{ margin: 0 }}>Importaciones de sucursal</h1>
          <p className="premium-header-subtitle" style={{ margin: '5px 0 0' }}>
            Completa los datos faltantes sin inventar proveedores, estaciones o ingredientes.
          </p>
        </div>
      </div>

      {!branchId && <div role="alert" style={{ color: '#b91c1c' }}>Selecciona una sucursal para consultar sus importaciones.</div>}
      {batchesQuery.isError && <div role="alert" style={{ color: '#b91c1c' }}>No se pudieron cargar los lotes.</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 14, marginBottom: 24 }}>
        {(batchesQuery.data || []).map((batch) => (
          <button
            key={batch.id}
            type="button"
            onClick={() => {
              setSelectedBatchId(batch.id);
              setPage(0);
            }}
            style={{ textAlign: 'left', padding: 18, borderRadius: 14, border: activeBatchId === batch.id ? '2px solid #10b981' : '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <strong>{batch.source_system}</strong>
              {batch.status === 'completed' ? <CheckCircle2 size={19} color="#16a34a" /> : <Clock3 size={19} color="#d97706" />}
            </div>
            <div style={{ color: '#64748b', marginTop: 8, fontSize: 13 }}>
              {batch.status === 'review' ? 'Requiere revisión' : 'Completado'}
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 10, color: '#334155', fontSize: 13 }}>
              <span>{batch.summary.imported || 0} importados</span>
              <span>{batch.summary.needs_review || 0} por revisar</span>
            </div>
          </button>
        ))}
      </div>

      {activeBatch && (
        <>
          <section style={{ marginBottom: 20 }}>
            <div style={{ marginBottom: 12 }}>
              <h2 style={{ margin: 0, fontSize: 20, color: '#0f172a' }}>¿Qué falta completar?</h2>
              <p style={{ margin: '5px 0 0', color: '#64748b', fontSize: 14 }}>
                Elige un tipo. Cada grupo tiene una causa y un procedimiento diferente.
              </p>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
              {pendingTypes.map((type) => {
                const config = reviewFlows[type];
                const Icon = config.icon;
                const count = activeBatch.entity_summary?.[type]?.needs_review || 0;
                const isActive = type === selectedType;
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => selectType(type)}
                    aria-pressed={isActive}
                    style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 16, textAlign: 'left', borderRadius: 14, border: isActive ? `2px solid ${config.color}` : '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }}
                  >
                    <span style={{ display: 'grid', placeItems: 'center', width: 42, height: 42, flex: '0 0 auto', borderRadius: 12, color: config.color, background: config.background }}>
                      <Icon size={22} />
                    </span>
                    <span>
                      <strong style={{ display: 'block', color: '#0f172a' }}>{config.label}</strong>
                      <span style={{ color: config.color, fontSize: 13 }}>{count} pendientes</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 20, alignItems: 'start', marginBottom: 20, padding: 20, border: `1px solid ${flow.background}`, borderRadius: 14, background: flow.background }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 18, color: flow.color }}>Cómo resolver {flow.label.toLocaleLowerCase('es-MX')}</h2>
              <p style={{ margin: '7px 0 12px', color: '#334155', fontSize: 14 }}>{flow.description}</p>
              <ol style={{ margin: 0, paddingLeft: 20, color: '#334155', fontSize: 14, lineHeight: 1.7 }}>
                {flow.steps.map((step) => <li key={step}>{step}</li>)}
              </ol>
            </div>
            <Link
              to={actionPath(selectedType)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '10px 14px', borderRadius: 9, background: flow.color, color: '#fff', textDecoration: 'none', fontWeight: 600, whiteSpace: 'nowrap' }}
            >
              {flow.actionLabel} <ArrowRight size={16} />
            </Link>
          </section>

          <div className="premium-card" style={{ overflow: 'hidden' }}>
            <div style={{ padding: 18, borderBottom: '1px solid #e2e8f0', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div>
                <strong>{flow.label} pendientes ({pageTotal})</strong>
                <div style={{ color: '#64748b', fontSize: 12, marginTop: 3 }}>
                  Mostrando {firstItem}–{lastItem}. La búsqueda se aplica a esta página.
                </div>
              </div>
              <div style={{ position: 'relative', width: 280, maxWidth: '100%' }}>
                <Search size={16} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Buscar nombre o clave en esta página"
                  style={{ width: '100%', boxSizing: 'border-box', padding: '9px 10px 9px 34px', border: '1px solid #cbd5e1', borderRadius: 9 }}
                />
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="premium-table">
                <thead><tr><th>{flow.singular}</th><th>Dato faltante</th><th>Origen</th><th>Acción</th></tr></thead>
                <tbody>
                  {filteredRecords.map((record) => {
                    const identity = recordIdentity(record);
                    return (
                      <tr key={record.id}>
                        <td>
                          <strong>{identity.name}</strong>
                          <div style={{ marginTop: 4, color: '#64748b', fontSize: 12 }}>
                            Clave: {identity.sku}
                            {selectedType === 'presentation' && identity.unit && ` · Unidad: ${identity.unit}`}
                            {selectedType === 'presentation' && identity.yieldValue && ` · Rendimiento: ${identity.yieldValue}`}
                          </div>
                        </td>
                        <td style={{ maxWidth: 330 }}>{flow.description}</td>
                        <td style={{ color: '#64748b', fontSize: 13 }}>Fila {record.source_row}</td>
                        <td>
                          <Link
                            to={actionPath(selectedType, record)}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: flow.color, fontWeight: 600, textDecoration: 'none', whiteSpace: 'nowrap' }}
                          >
                            {flow.actionLabel} <ArrowRight size={15} />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                  {!recordsQuery.isLoading && filteredRecords.length === 0 && (
                    <tr><td colSpan={4} style={{ padding: 32, textAlign: 'center', color: '#64748b' }}>
                      {search ? 'No hay coincidencias en esta página.' : `No hay ${flow.label.toLocaleLowerCase('es-MX')} pendientes.`}
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 14, borderTop: '1px solid #e2e8f0' }}>
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(current - 1, 0))}
                disabled={page === 0 || recordsQuery.isFetching}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '8px 11px', border: '1px solid #cbd5e1', borderRadius: 8, background: '#fff' }}
              >
                <ChevronLeft size={16} /> Anterior
              </button>
              <span style={{ color: '#64748b', fontSize: 13 }}>Página {page + 1} de {Math.max(Math.ceil(pageTotal / PAGE_SIZE), 1)}</span>
              <button
                type="button"
                onClick={() => setPage((current) => current + 1)}
                disabled={lastItem >= pageTotal || recordsQuery.isFetching}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '8px 11px', border: '1px solid #cbd5e1', borderRadius: 8, background: '#fff' }}
              >
                Siguiente <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
