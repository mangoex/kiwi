import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Package, Search, AlertCircle, RefreshCw, AlertTriangle } from 'lucide-react';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { usePosSession } from '../../session';

interface StockRow {
  id: string;
  sku: string;
  name: string;
  item_type: string;
  unit_code: string;
  unit_name: string;
  warehouse_id: string;
  warehouse_name: string;
  branch_id: string;
  branch_name: string;
  quantity_on_hand: string | number;
  last_movement_at: string | null;
}

type FilterType = 'all' | 'with-stock' | 'no-stock' | 'negative';

const FILTER_LABELS: Record<FilterType, string> = {
  'all': 'Todos',
  'with-stock': 'Con existencia',
  'no-stock': 'Sin existencia',
  'negative': 'Existencia negativa',
};

const PAGE_SIZE = 25;

function qtyNumber(q: string | number): number {
  const n = Number(q);
  return Number.isFinite(n) ? n : 0;
}

function itemTypeLabel(t: string): string {
  if (t === 'ingredient') return 'Insumo';
  if (t === 'product') return 'Producto';
  if (t === 'prepared') return 'Elaborado';
  if (t === 'packaging') return 'Empaque';
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function formatDate(iso: string | null): string {
  if (!iso) return 'Sin movimientos';
  try {
    return new Date(iso).toLocaleDateString('es-MX', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

const PosInventory = () => {
  const { session, state: sessionState } = usePosSession();
  const branchId = session?.active_branch?.id || '';
  const branchName = session?.active_branch?.name || '';
  const warehouseName = session?.active_branch?.warehouse?.name || '';

  const [stock, setStock] = useState<StockRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [page, setPage] = useState(0);

  const fetchStock = useCallback(async () => {
    if (!branchId) {
      if (sessionState.status !== 'loading') {
        setLoading(false);
        setError('La sesión no tiene una sucursal activa. Vuelve a iniciar sesión.');
      }
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await fetchApi<StockRow[]>(
        `/inventory/stock?branch_id=${encodeURIComponent(branchId)}`,
      );
      setStock(Array.isArray(data) ? data : []);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('No se pudo cargar el inventario.');
      }
      setStock([]);
    } finally {
      setLoading(false);
    }
  }, [branchId, sessionState.status]);

  useEffect(() => {
    void fetchStock();
  }, [fetchStock]);

  const filtered = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return stock.filter((item) => {
      const matchesSearch =
        !q ||
        item.name.toLowerCase().includes(q) ||
        item.sku.toLowerCase().includes(q);
      if (!matchesSearch) return false;
      const qty = qtyNumber(item.quantity_on_hand);
      if (filter === 'with-stock') return qty > 0;
      if (filter === 'no-stock') return qty === 0;
      if (filter === 'negative') return qty < 0;
      return true;
    });
  }, [stock, searchTerm, filter]);

  const stats = useMemo(() => {
    const total = stock.length;
    let withStock = 0;
    let noStock = 0;
    let negative = 0;
    for (const item of stock) {
      const qty = qtyNumber(item.quantity_on_hand);
      if (qty > 0) withStock++;
      else if (qty === 0) noStock++;
      else negative++;
    }
    return { total, withStock, noStock, negative };
  }, [stock]);

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE);
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div style={{ padding: '32px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Encabezado */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
          Inventario de sucursal
        </h1>
        <p style={{ color: '#64748b', margin: '4px 0 0' }}>
          {branchName}
          {warehouseName ? ` · ${warehouseName}` : ''} · Existencias teóricas derivadas de movimientos
        </p>
      </div>

      {/* Tarjetas resumen */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 24 }}>
        <SummaryCard label="Total de artículos" value={stats.total} color="#0f172a" />
        <SummaryCard label="Con existencia" value={stats.withStock} color="#16a34a" />
        <SummaryCard label="Sin existencia" value={stats.noStock} color="#64748b" />
        <SummaryCard label="Existencia negativa" value={stats.negative} color="#dc2626" />
      </div>

      {/* Buscador y filtros */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 240px', maxWidth: 360 }}>
          <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
          <input
            type="text"
            placeholder="Buscar por nombre o SKU…"
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setPage(0); }}
            style={{ width: '100%', padding: '0.5rem 0.75rem 0.5rem 2.25rem', border: '1px solid #d1d5db', borderRadius: '0.5rem' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {(Object.keys(FILTER_LABELS) as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(0); }}
              style={{
                padding: '0.4rem 0.8rem',
                borderRadius: '0.5rem',
                border: '1px solid',
                borderColor: filter === f ? '#16a34a' : '#d1d5db',
                background: filter === f ? '#f0fdf4' : '#fff',
                color: filter === f ? '#16a34a' : '#64748b',
                fontWeight: filter === f ? 600 : 400,
                cursor: 'pointer',
                fontSize: '0.875rem',
              }}
            >
              {FILTER_LABELS[f]}
            </button>
          ))}
        </div>
      </div>

      {/* Estados */}
      {loading ? (
        <p style={{ color: '#64748b', padding: '2rem 0' }}>Cargando inventario…</p>
      ) : error ? (
        <div style={{ color: '#dc2626', padding: '1rem 0', display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'flex-start' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><AlertCircle size={16} /> {error}</span>
          <button onClick={() => void fetchStock()} style={{ padding: '0.4rem 1rem', borderRadius: '0.5rem', border: '1px solid #16a34a', background: '#16a34a', color: '#fff', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <RefreshCw size={14} /> Reintentar
          </button>
        </div>
      ) : stock.length === 0 ? (
        <p style={{ color: '#64748b', padding: '2rem 0' }}>No hay artículos en el inventario de esta sucursal.</p>
      ) : filtered.length === 0 ? (
        <p style={{ color: '#64748b', padding: '2rem 0' }}>No se encontraron artículos con esos criterios.</p>
      ) : (
        <>
          {/* Tabla */}
          <div style={{ overflowX: 'auto', background: '#fff', borderRadius: '0.75rem', border: '1px solid #e5e7eb' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
                  <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem', whiteSpace: 'nowrap' }}>Artículo</th>
                  <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Tipo</th>
                  <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Almacén</th>
                  <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Existencia teórica</th>
                  <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Último movimiento</th>
                  <th style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((item) => {
                  const qty = qtyNumber(item.quantity_on_hand);
                  const isNegative = qty < 0;
                  const isZero = qty === 0;
                  return (
                    <tr key={item.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Package size={14} color="#10b981" />
                          <div>
                            <div style={{ fontWeight: 500 }}>{item.name}</div>
                            <div style={{ fontSize: '0.75rem', color: '#9ca3af', fontFamily: 'monospace' }}>{item.sku}</div>
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: '0.6rem 1rem', fontSize: '0.875rem' }}>{itemTypeLabel(item.item_type)}</td>
                      <td style={{ padding: '0.6rem 1rem', fontSize: '0.875rem', color: '#64748b' }}>{item.warehouse_name || '—'}</td>
                      <td style={{
                        padding: '0.6rem 1rem',
                        fontWeight: 700,
                        color: isNegative ? '#dc2626' : isZero ? '#64748b' : '#16a34a',
                      }}>
                        {qty} {item.unit_code}
                      </td>
                      <td style={{ padding: '0.6rem 1rem', fontSize: '0.875rem', color: '#64748b' }}>
                        {formatDate(item.last_movement_at)}
                      </td>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        {isNegative ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#dc2626', fontSize: '0.8rem', fontWeight: 600 }}>
                            <AlertTriangle size={14} /> Negativa
                          </span>
                        ) : isZero ? (
                          <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Sin existencia</span>
                        ) : (
                          <span style={{ color: '#16a34a', fontSize: '0.8rem' }}>Disponible</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Paginación */}
          {pageCount > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1rem' }}>
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                style={{ padding: '0.3rem 0.8rem', borderRadius: '0.375rem', border: '1px solid #d1d5db', background: '#fff', cursor: page === 0 ? 'not-allowed' : 'pointer', opacity: page === 0 ? 0.5 : 1 }}
              >
                Anterior
              </button>
              <span style={{ padding: '0.3rem 0.5rem', color: '#64748b', fontSize: '0.875rem' }}>
                Página {page + 1} de {pageCount}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                disabled={page >= pageCount - 1}
                style={{ padding: '0.3rem 0.8rem', borderRadius: '0.375rem', border: '1px solid #d1d5db', background: '#fff', cursor: page >= pageCount - 1 ? 'not-allowed' : 'pointer', opacity: page >= pageCount - 1 ? 0.5 : 1 }}
              >
                Siguiente
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

function SummaryCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: '0.75rem', padding: '1rem 1.25rem', border: '1px solid #e5e7eb' }}>
      <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

export default PosInventory;
