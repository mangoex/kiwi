import React, { useEffect, useState } from 'react';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import {
  Building2,
  ChefHat,
  ClipboardCheck,
  Receipt,
  Trash2,
  Truck,
} from 'lucide-react';
import { usePosSession } from '../../session';
import { BranchAdminPage } from './BranchAdminPage';

interface Column<T> {
  key: string;
  label: string;
  render: (row: T) => React.ReactNode;
}

interface ResourceState<T> {
  data: T[];
  loading: boolean;
  error: string;
}

function useBranchResource<T>(path: string, includeBranch = true): ResourceState<T> {
  const { session } = usePosSession();
  const branchId = session?.active_branch?.id || '';
  const [state, setState] = useState<ResourceState<T>>({
    data: [],
    loading: true,
    error: '',
  });

  useEffect(() => {
    if (includeBranch && !branchId) {
      setState({ data: [], loading: false, error: 'No hay una sucursal activa.' });
      return;
    }

    const controller = new AbortController();
    const separator = path.includes('?') ? '&' : '?';
    const endpoint = includeBranch
      ? `${path}${separator}branch_id=${encodeURIComponent(branchId)}`
      : path;

    setState((current) => ({ ...current, loading: true, error: '' }));
    void fetchApi<T[]>(endpoint, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        setState({ data: Array.isArray(data) ? data : [], loading: false, error: '' });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          data: [],
          loading: false,
          error: error instanceof ApiError ? error.message : 'No se pudo cargar la información.',
        });
      });

    return () => controller.abort();
  }, [branchId, includeBranch, path]);

  return state;
}

function BranchTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  error,
  emptyMessage,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading: boolean;
  error: string;
  emptyMessage: string;
}) {
  if (loading) return <p style={{ color: '#64748b' }}>Cargando información…</p>;
  if (error) return <div role="alert" style={{ color: '#b91c1c' }}>{error}</div>;
  if (rows.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>{emptyMessage}</div>
    );
  }

  return (
    <div style={{ overflowX: 'auto', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 16 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
        <thead>
          <tr style={{ background: '#f8fafc' }}>
            {columns.map((column) => (
              <th key={column.key} style={headerStyle}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} style={{ borderTop: '1px solid #f1f5f9' }}>
              {columns.map((column) => (
                <td key={column.key} style={cellStyle}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const headerStyle: React.CSSProperties = {
  padding: '13px 16px',
  color: '#64748b',
  fontSize: 12,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const cellStyle: React.CSSProperties = {
  padding: '14px 16px',
  color: '#334155',
  fontSize: 14,
  verticalAlign: 'top',
};

function Status({ value }: { value: string }) {
  const active = ['active', 'confirmed', 'received', 'closed'].includes(value);
  return (
    <span
      style={{
        display: 'inline-block',
        borderRadius: 999,
        padding: '3px 9px',
        color: active ? '#047857' : '#475569',
        background: active ? '#d1fae5' : '#f1f5f9',
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {value}
    </span>
  );
}

function money(value: number | string | null | undefined): string {
  return `$${Number(value || 0).toFixed(2)}`;
}

function dateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('es-MX');
}

interface Supplier {
  id: string;
  code: string;
  commercial_name: string;
  tax_id?: string;
  credit_days: number;
  contacts?: Array<{ id: string; name: string; primary_for_orders: boolean }>;
}

interface Presentation {
  id: string;
  code: string;
  name: string;
  supplier_name: string;
  item_name: string;
  last_net_price: number;
  base_unit_code: string;
}

export function BranchAdminSuppliers() {
  const suppliers = useBranchResource<Supplier>('/suppliers');
  const presentations = useBranchResource<Presentation>('/purchase-presentations');
  return (
    <BranchAdminPage
      title="Proveedores"
      description="Consulta proveedores y presentaciones disponibles para la operación de tu sucursal."
      icon={Building2}
    >
      <p style={{ color: '#64748b', marginTop: 0 }}>
        El alta y modificación del catálogo central permanece en Administración corporativa.
      </p>
      <h2 style={sectionTitle}>Directorio de proveedores</h2>
      <BranchTable
        columns={[
          { key: 'code', label: 'Código', render: (row) => row.code },
          { key: 'name', label: 'Proveedor', render: (row) => row.commercial_name },
          { key: 'tax', label: 'RFC', render: (row) => row.tax_id || '—' },
          { key: 'credit', label: 'Crédito', render: (row) => `${row.credit_days} días` },
          {
            key: 'contact',
            label: 'Contacto de pedidos',
            render: (row) => row.contacts?.find((contact) => contact.primary_for_orders)?.name || '—',
          },
        ]}
        rows={suppliers.data}
        rowKey={(row) => row.id}
        loading={suppliers.loading}
        error={suppliers.error}
        emptyMessage="No hay proveedores registrados."
      />
      <h2 style={sectionTitle}>Presentaciones de compra</h2>
      <BranchTable
        columns={[
          { key: 'code', label: 'Código', render: (row) => row.code },
          { key: 'name', label: 'Presentación', render: (row) => row.name },
          { key: 'supplier', label: 'Proveedor', render: (row) => row.supplier_name },
          { key: 'item', label: 'Insumo', render: (row) => row.item_name },
          { key: 'price', label: 'Último precio', render: (row) => money(row.last_net_price) },
        ]}
        rows={presentations.data}
        rowKey={(row) => row.id}
        loading={presentations.loading}
        error={presentations.error}
        emptyMessage="No hay presentaciones registradas."
      />
    </BranchAdminPage>
  );
}

interface Purchase {
  id: string;
  folio: string;
  supplier_id: string;
  document_type: string;
  total: number;
  paid_from_cash: boolean;
  status: string;
}

export function BranchAdminPurchases() {
  const purchases = useBranchResource<Purchase>('/purchases');
  return (
    <BranchAdminPage
      title="Compras"
      description="Recepciones y documentos de compra correspondientes a la sucursal activa."
      icon={Receipt}
    >
      <BranchTable
        columns={[
          { key: 'folio', label: 'Folio', render: (row) => row.folio },
          { key: 'supplier', label: 'Proveedor', render: (row) => row.supplier_id },
          { key: 'document', label: 'Documento', render: (row) => row.document_type },
          { key: 'total', label: 'Total', render: (row) => money(row.total) },
          { key: 'payment', label: 'Pago', render: (row) => row.paid_from_cash ? 'Caja' : 'Otro medio' },
          { key: 'status', label: 'Estado', render: (row) => <Status value={row.status} /> },
        ]}
        rows={purchases.data}
        rowKey={(row) => row.id}
        loading={purchases.loading}
        error={purchases.error}
        emptyMessage="No hay compras registradas para esta sucursal."
      />
    </BranchAdminPage>
  );
}

interface ProductionBatch {
  id: string;
  recipe_id: string;
  lot_code: string;
  planned_quantity: number;
  actual_quantity: number;
  total_cost: number;
  unit_cost: number;
  status: string;
}

export function BranchAdminProduction() {
  const batches = useBranchResource<ProductionBatch>('/production-batches');
  return (
    <BranchAdminPage
      title="Producción"
      description="Lotes y elaborados producidos localmente en la sucursal activa."
      icon={ChefHat}
    >
      <BranchTable
        columns={[
          { key: 'lot', label: 'Lote', render: (row) => row.lot_code },
          { key: 'recipe', label: 'Receta', render: (row) => row.recipe_id },
          { key: 'planned', label: 'Planeado', render: (row) => Number(row.planned_quantity) },
          { key: 'actual', label: 'Real', render: (row) => Number(row.actual_quantity) },
          { key: 'cost', label: 'Costo unitario', render: (row) => money(row.unit_cost) },
          { key: 'status', label: 'Estado', render: (row) => <Status value={row.status} /> },
        ]}
        rows={batches.data}
        rowKey={(row) => row.id}
        loading={batches.loading}
        error={batches.error}
        emptyMessage="No hay lotes de producción en esta sucursal."
      />
    </BranchAdminPage>
  );
}

interface Waste {
  id: string;
  effective_at: string;
  item_name: string;
  item_sku: string;
  reason_name: string;
  stage: string;
  quantity: number;
  unit_code: string;
  total_cost: number;
  status: string;
}

export function BranchAdminWaste() {
  const wastes = useBranchResource<Waste>('/inventory/wastes');
  return (
    <BranchAdminPage
      title="Mermas"
      description="Pérdidas reales, motivos y estado de autorización de la sucursal."
      icon={Trash2}
    >
      <BranchTable
        columns={[
          { key: 'date', label: 'Fecha', render: (row) => dateTime(row.effective_at) },
          { key: 'item', label: 'Insumo', render: (row) => <><strong>{row.item_name}</strong><br /><small>{row.item_sku}</small></> },
          { key: 'reason', label: 'Motivo', render: (row) => `${row.reason_name} · ${row.stage}` },
          { key: 'quantity', label: 'Cantidad', render: (row) => `${Number(row.quantity)} ${row.unit_code}` },
          { key: 'cost', label: 'Costo', render: (row) => money(row.total_cost) },
          { key: 'status', label: 'Estado', render: (row) => <Status value={row.status} /> },
        ]}
        rows={wastes.data}
        rowKey={(row) => row.id}
        loading={wastes.loading}
        error={wastes.error}
        emptyMessage="No hay mermas registradas en esta sucursal."
      />
    </BranchAdminPage>
  );
}

interface TransferLine {
  id: string;
  item_name: string;
  requested_quantity: number;
  unit_code: string;
}

interface Transfer {
  id: string;
  folio: string;
  source_branch_name: string;
  destination_branch_name: string;
  created_at: string;
  status: string;
  lines: TransferLine[];
}

export function BranchAdminTransfers() {
  const transfers = useBranchResource<Transfer>('/inventory/transfers');
  return (
    <BranchAdminPage
      title="Traspasos"
      description="Salidas, tránsito y recepciones relacionadas con la sucursal activa."
      icon={Truck}
    >
      <BranchTable
        columns={[
          { key: 'folio', label: 'Folio', render: (row) => <><strong>{row.folio}</strong><br /><small>{dateTime(row.created_at)}</small></> },
          { key: 'source', label: 'Origen', render: (row) => row.source_branch_name },
          { key: 'destination', label: 'Destino', render: (row) => row.destination_branch_name },
          { key: 'items', label: 'Artículos', render: (row) => row.lines?.length || 0 },
          { key: 'status', label: 'Estado', render: (row) => <Status value={row.status} /> },
        ]}
        rows={transfers.data}
        rowKey={(row) => row.id}
        loading={transfers.loading}
        error={transfers.error}
        emptyMessage="No hay traspasos relacionados con esta sucursal."
      />
    </BranchAdminPage>
  );
}

interface PhysicalCount {
  id: string;
  folio: string;
  branch_name: string;
  snapshot_at: string;
  scope: string;
  blind: boolean;
  status: string;
  lines: Array<{ id: string }>;
}

export function BranchAdminCounts() {
  const counts = useBranchResource<PhysicalCount>('/inventory/physical-counts');
  return (
    <BranchAdminPage
      title="Conteos físicos"
      description="Fotografías teóricas, capturas ciegas y estados de conciliación."
      icon={ClipboardCheck}
    >
      <BranchTable
        columns={[
          { key: 'folio', label: 'Folio', render: (row) => row.folio },
          { key: 'snapshot', label: 'Fotografía', render: (row) => dateTime(row.snapshot_at) },
          { key: 'scope', label: 'Alcance', render: (row) => row.scope },
          { key: 'items', label: 'Artículos', render: (row) => row.lines?.length || 0 },
          { key: 'blind', label: 'Captura', render: (row) => row.blind ? 'Ciega' : 'Visible' },
          { key: 'status', label: 'Estado', render: (row) => <Status value={row.status} /> },
        ]}
        rows={counts.data}
        rowKey={(row) => row.id}
        loading={counts.loading}
        error={counts.error}
        emptyMessage="No hay conteos físicos registrados en esta sucursal."
      />
    </BranchAdminPage>
  );
}

const sectionTitle: React.CSSProperties = {
  color: '#0f172a',
  fontSize: 18,
  margin: '28px 0 12px',
};
