import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { Button, Input, Select, Badge } from '@restaurantos/ui';
import { Link } from 'react-router-dom';
import { RefreshCw, Search, Package } from 'lucide-react';
import { useAdminSession, useAdminPermission } from '../../lib/adminSession';
import { formatRecipeDecimal } from '../catalog/recipeDecimal';
import InventoryScopeControl from './InventoryScopeControl';
import { useInventoryOnline } from './useInventoryOnline';
import './InventoryVisibility.css';

interface StockRow {
  item_id: string; item_name: string; sku: string; item_type: string;
  branch_id: string; branch_name: string; timezone: string;
  warehouse_id: string; warehouse_name: string; unit_id: string; unit_code: string;
  physical_quantity: string; reserved_quantity: string; available_quantity: string;
  reservation_inconsistent: boolean; last_movement_at: string | null;
}
interface Overview {
  items: StockRow[]; as_of: string; total_rows: number; limit: number; offset: number;
  counts: { positive: number; zero: number; negative: number };
}
export function inventoryDate(value: string | null, zone: string): string {
  if (!value) return 'Sin movimientos';
  try { return `${new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short', timeZone: zone }).format(new Date(value))} · ${zone}`; }
  catch { return 'Fecha no disponible'; }
}

export default function InventoryStock() {
  const { session, inventoryQueryScope: scope } = useAdminSession();
  const manage = useAdminPermission('catalog.manage');
  const online = useInventoryOnline();
  const [search, setSearch] = useState('');
  const [availability, setAvailability] = useState('all');
  const [unit, setUnit] = useState('');
  const [page, setPage] = useState(0);
  const [lastScope, setLastScope] = useState(scope);
  if (lastScope !== scope) { setLastScope(scope); setPage(0); }
  const params = new URLSearchParams({ scope: scope?.kind || 'branch', q: search,
    availability, limit: '50', offset: String(page * 50) });
  if (scope?.branch_id) params.set('branch_id', scope.branch_id);
  if (unit) params.set('unit_id', unit);
  const stock = useQuery({
    queryKey: ['inventory-overview', session.user.id, session.organization_id,
      session.scope.authorization_version, params.toString()],
    queryFn: ({ signal }) => fetchApi<Overview>(`/inventory/overview?${params}`, { signal }),
    enabled: Boolean(scope && session.inventory_query_capabilities && online), retry: false,
  });
  const units = useQuery({ queryKey: ['inventory-query-units', session.user.id, session.organization_id],
    queryFn: ({ signal }) => fetchApi<{ id: string; name: string; code: string }[]>('/inventory/units', { signal }),
    enabled: Boolean(scope), retry: false });
  const changeFilter = (setter: (value: string) => void, value: string) => { setter(value); setPage(0); };
  const data = stock.data;
  const branch = session.inventory_query_capabilities?.branches.find(row => row.id === scope?.branch_id);
  const zone = branch?.timezone || 'UTC';
  return <main className="inventory-visibility">
    <header><h1>Existencias</h1><p>Consulta el inventario registrado por sucursal y almacén. Las reservas se muestran por separado.</p></header>
    <InventoryScopeControl />
    {!online && <p className="inventory-state" role="alert">Sin conexión. Las existencias no se muestran como actuales; vuelve a conectarte y actualiza.</p>}
    {scope && online && <>
      <div className="inventory-toolbar">
        <label className="inventory-search">Buscar insumo o SKU<Input icon={<Search size={16} />} value={search} maxLength={120}
          onChange={event => changeFilter(setSearch, event.target.value)} placeholder="Nombre o código del artículo" /></label>
        <label>Disponibilidad<Select value={availability} onChange={event => changeFilter(setAvailability, event.target.value)}>
          <option value="all">Todos</option><option value="positive">Con disponible</option>
          <option value="zero">Sin disponible</option><option value="negative">Disponible negativo</option>
        </Select></label>
        <label>Unidad base<Select value={unit} onChange={event => changeFilter(setUnit, event.target.value)}>
          <option value="">Todas las unidades</option>{units.data?.map(row => <option key={row.id} value={row.id}>{row.name} ({row.code})</option>)}
        </Select></label>
        <Button variant="secondary" disabled={stock.isFetching} onClick={() => void stock.refetch()}><RefreshCw size={16} /> Actualizar</Button>
      </div>
      {stock.isPending && <p className="inventory-state" role="status">Consultando existencias…</p>}
      {stock.isError && <div className="inventory-state" role="alert">{stock.error instanceof ApiError ? stock.error.message : 'No fue posible consultar el inventario. Comprueba tu conexión y vuelve a actualizar.'}</div>}
      {!stock.isError && data && <>
        <div className="inventory-summary" aria-label="Resumen de filas del conjunto filtrado">
          <span><strong>{data.total_rows}</strong>filas de inventario</span>
          <span><strong>{data.counts.positive}</strong>con disponible</span>
          <span><strong>{data.counts.zero}</strong>sin disponible</span>
          <span><strong>{data.counts.negative}</strong>con disponible negativo</span>
        </div>
        <p className="inventory-caption" role="status">{stock.isFetching ? 'Actualizando. Última consulta: ' : 'Consulta: '}{inventoryDate(data.as_of, zone)}. Cada fila representa un artículo en un almacén.</p>
        {!data.items.length ? <div className="inventory-state"><Package size={20} /><p>No hay artículos que coincidan con esta consulta.</p></div>
          : <div className="inventory-table-wrap" tabIndex={0} role="region" aria-label="Existencias por sucursal">
            <table className="inventory-table"><thead><tr><th>Artículo</th><th>Sucursal / almacén</th><th>Existencia teórica</th><th>Reserva pendiente</th><th>Disponible</th><th>Último movimiento</th>{manage && <th>Configuración</th>}</tr></thead>
              <tbody>{data.items.map(row => <tr key={`${row.item_id}:${row.branch_id}:${row.warehouse_id}`}>
                <td><strong>{row.item_name}</strong><small>{row.sku}</small></td>
                <td>{row.branch_name}<small>{row.warehouse_name}</small></td>
                <td className="inventory-quantity">{formatRecipeDecimal(row.physical_quantity)} {row.unit_code}</td>
                <td className="inventory-quantity">{formatRecipeDecimal(row.reserved_quantity)} {row.unit_code}{row.reservation_inconsistent && <small><Badge variant="warning">Revisar reserva</Badge></small>}</td>
                <td className={`inventory-quantity ${row.available_quantity.startsWith('-') ? 'inventory-negative' : ''}`}>{formatRecipeDecimal(row.available_quantity)} {row.unit_code}</td>
                <td><time dateTime={row.last_movement_at || undefined}>{inventoryDate(row.last_movement_at, row.timezone)}</time></td>
                {manage && <td>{row.item_type === 'ingredient' && <Link to={`/inventory/thresholds?inventory_branch_id=${encodeURIComponent(row.branch_id)}&item_id=${encodeURIComponent(row.item_id)}`}>Ver umbrales</Link>}</td>}
              </tr>)}</tbody></table>
          </div>}
        <p className="inventory-caption">Existencia teórica antes de reservas; no sustituye un conteo físico. Las cantidades de distintas unidades no se suman.</p>
        <nav className="inventory-pagination" aria-label="Páginas de inventario">
          <Button variant="secondary" disabled={page === 0 || stock.isFetching} onClick={() => setPage(value => value - 1)}>Anterior</Button>
          <span>Página {page + 1} · {data.total_rows} filas</span>
          <Button variant="secondary" disabled={(page + 1) * 50 >= data.total_rows || stock.isFetching} onClick={() => setPage(value => value + 1)}>Siguiente</Button>
        </nav>
      </>}
    </>}
  </main>;
}
