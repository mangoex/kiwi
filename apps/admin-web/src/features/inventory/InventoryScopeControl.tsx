import { Select } from '@restaurantos/ui';
import { useAdminSession } from '../../lib/adminSession';
import './InventoryVisibility.css';

export default function InventoryScopeControl() {
  const { session, inventoryQueryScope: scope, selectInventoryQueryScope } = useAdminSession();
  const capabilities = session.inventory_query_capabilities;
  if (!capabilities) return <p role="alert">La consulta administrativa de inventario aún no está disponible en el servidor.</p>;
  return <div className="inventory-scope">
    <label htmlFor="inventory-query-scope">Consulta de inventario</label>
    <Select id="inventory-query-scope" value={scope?.branch_id ?? (scope ? '' : '__choose__')}
      onChange={event => selectInventoryQueryScope(event.target.value
        ? { kind: 'branch', branch_id: event.target.value } : { kind: 'organization', branch_id: null })}>
      {!scope && <option disabled value="__choose__">Selecciona una sucursal</option>}
      {capabilities.organization_read && <option value="">Todas las sucursales</option>}
      {capabilities.branches.map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
    </Select>
    <span>Este filtro no cambia tu caja ni la sucursal del POS.</span>
  </div>;
}
