import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import { Navigate } from 'react-router-dom';
import { CheckCircle2, Eye, MapPin, Search, Store, Undo2, XCircle } from 'lucide-react';
import { useAdminPermission, useAdminSession } from '../../lib/adminSession';
import ProductsList from './ProductsList';
import VariationNotes from './VariationNotes';
import IngredientExtras from './IngredientExtras';
import RecipesWorkspace from '../recipes/RecipesWorkspace';
import './CatalogAvailability.css';

type Kind = 'products' | 'variations' | 'ingredient-extras';
type AvailabilityKind = Exclude<Kind, 'variations'>;
const resources: Record<AvailabilityKind, string> = {
  products: 'products',
  'ingredient-extras': 'ingredient-variations',
};

interface AvailabilityRow {
  id?: string;
  option_id?: string;
  name: string;
  sku?: string;
  product_name?: string;
  effective_availability?: boolean;
  effective_enabled?: boolean;
  has_local_override?: boolean;
  override?: boolean | null;
  status?: string;
  central_status?: string;
  show_in_digital_menu?: boolean;
  has_digital_menu_override?: boolean;
  applicable_branch_count?: number;
  available_branch_count?: number;
  digital_menu_visible_branch_count?: number;
  availability_summary?: 'all' | 'none' | 'mixed';
  digital_menu_summary?: 'all' | 'none' | 'mixed';
}

interface AllActiveSummary {
  scope: 'all_active';
  branches: { id: string; name: string; code: string }[];
  items: AvailabilityRow[];
}

const rowId = (row: AvailabilityRow) => row.id || row.option_id || '';

function AggregateVisibilityCheckbox({
  row,
  disabled,
  onChange,
}: {
  row: AvailabilityRow;
  disabled: boolean;
  onChange: (visible: boolean) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const mixed = row.digital_menu_summary === 'mixed';
  const checked = row.digital_menu_summary === 'all';
  useEffect(() => {
    if (input.current) input.current.indeterminate = mixed;
  }, [mixed]);
  return (
    <input
      ref={input}
      type="checkbox"
      checked={checked}
      aria-checked={mixed ? 'mixed' : checked}
      disabled={disabled}
      aria-label={`Mostrar ${row.name} en menú digital en todas las sucursales actuales`}
      onChange={(event) => onChange(event.target.checked)}
    />
  );
}

function BranchAvailability({ kind, standalone = false }: { kind: AvailabilityKind; standalone?: boolean }) {
  const { session } = useAdminSession();
  const canManage = useAdminPermission('catalog.branch.manage');
  const client = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [selectedScope, setSelectedScope] = useState(() =>
    kind === 'products' && session.scope.level === 'organization' ? 'all-active' : session.active_branch.id,
  );
  const activeBranches = session.allowed_branches.filter((branch) => branch.status === 'active');
  const organizationScope = session.scope.level === 'organization';
  const canSelectScope = organizationScope && (kind === 'products' || activeBranches.length > 1);
  const allActive = kind === 'products' && organizationScope && selectedScope === 'all-active';
  const selectedBranch = activeBranches.find((branch) => branch.id === selectedScope) || session.active_branch;
  const branchId = selectedBranch.id;

  useEffect(() => {
    if (kind === 'products' && organizationScope && selectedScope === 'all-active') return;
    if (!activeBranches.some((branch) => branch.id === selectedScope)) {
      setSelectedScope(kind === 'products' && organizationScope ? 'all-active' : session.active_branch.id);
    }
  }, [activeBranches, kind, organizationScope, selectedScope, session.active_branch.id]);

  const endpoint = `/branch-administration/catalog/${resources[kind]}`;
  const query = allActive ? '' : `?branch_id=${encodeURIComponent(branchId)}`;
  const key = ['branch-availability', kind, session.user.id, selectedScope];
  const rows = useQuery<AvailabilityRow[]>({
    queryKey: key,
    queryFn: async ({ signal }) => {
      if (allActive) {
        const summary = await fetchApi<AllActiveSummary>(`${endpoint}/all-active-summary`, { signal });
        return summary.items;
      }
      return fetchApi<AvailabilityRow[]>(endpoint + query, { signal });
    },
  });

  const confirmAll = (description: string, branchCount: number) => window.confirm(
    `${description} en ${branchCount} sucursales actuales aplicables. Las sucursales futuras no cambiarán. ¿Deseas continuar?`,
  );
  const mutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => {
      if (!canManage) throw new Error('No tienes permiso para modificar disponibilidad.');
      const suffix = kind === 'products' ? allActive ? '/availability/all-active' : '/availability' : '';
      return fetchApi(`${endpoint}/${encodeURIComponent(id)}${suffix}${query}`, {
        method: 'PUT',
        body: JSON.stringify({ action }),
      });
    },
    onSuccess: () => {
      setStatusMessage('La disponibilidad quedó actualizada.');
      void client.invalidateQueries({ queryKey: key });
    },
  });
  const visibilityMutation = useMutation({
    mutationFn: ({ id, visible }: { id: string; visible: boolean }) => {
      if (!canManage || kind !== 'products') {
        throw new Error('No tienes permiso para modificar la visibilidad digital.');
      }
      const suffix = allActive ? '/digital-menu-visibility/all-active' : '/digital-menu-visibility';
      return fetchApi(`${endpoint}/${encodeURIComponent(id)}${suffix}${query}`, {
        method: 'PUT',
        body: JSON.stringify({ visible }),
      });
    },
    onMutate: async ({ id, visible }) => {
      setStatusMessage('');
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<AvailabilityRow[]>(key);
      client.setQueryData<AvailabilityRow[]>(key, (current = []) => current.map((row) => {
        if (rowId(row) !== id) return row;
        const applicable = row.applicable_branch_count || activeBranches.length;
        return allActive
          ? {
              ...row,
              digital_menu_summary: visible ? 'all' : 'none',
              digital_menu_visible_branch_count: visible ? applicable : 0,
            }
          : {
              ...row,
              show_in_digital_menu: visible,
              has_digital_menu_override: !visible,
            };
      }));
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) client.setQueryData(key, context.previous);
    },
    onSuccess: (_response, variables) => {
      setStatusMessage(variables.visible
        ? 'El producto volverá a mostrarse en el menú digital donde esté disponible.'
        : 'El producto quedó oculto del menú digital; seguirá disponible en el POS.');
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: key });
    },
  });

  const mutateAvailability = (id: string, action: string, branchCount: number) => {
    setStatusMessage('');
    const description = action === 'available'
      ? 'Marcar como disponible'
      : action === 'unavailable' ? 'Marcar como no disponible' : 'Heredar la disponibilidad';
    if (allActive && !confirmAll(`${description} el producto`, branchCount)) return;
    mutation.mutate({ id, action });
  };
  const mutateVisibility = (id: string, visible: boolean, branchCount: number) => {
    if (allActive && !confirmAll(`${visible ? 'Mostrar' : 'Ocultar'} el producto en el menú digital`, branchCount)) return;
    visibilityMutation.mutate({ id, visible });
  };
  const visibleRows = (rows.data || []).filter((row) =>
    `${row.name} ${row.product_name || ''} ${row.sku || ''}`.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <section className={`availability-workspace${standalone ? ' availability-workspace--standalone' : ''}`}>
      <header className="availability-hero">
        <div className="availability-hero__icon" aria-hidden="true"><Store size={24} /></div>
        <div>
          <span className="availability-eyebrow">Catálogo y Menú</span>
          <h1>{kind === 'products' ? 'Disponibilidad de productos' : 'Disponibilidad local'}</h1>
          <p>{kind === 'products'
            ? 'Decide dónde se vende cada producto y si aparece en el menú digital, sin modificar su presencia en el POS.'
            : 'Configura excepciones locales sobre el catálogo vigente de esta sucursal.'}</p>
        </div>
      </header>

      <div className="availability-toolbar">
        {canSelectScope ? <label className="availability-field">
          <span>Alcance</span>
          <div className="availability-control-with-icon">
            {allActive ? <Store size={17} /> : <MapPin size={17} />}
            <select
              aria-label="Sucursal para disponibilidad"
              value={selectedScope}
              disabled={mutation.isPending || visibilityMutation.isPending}
              onChange={(event) => {
                setStatusMessage('');
                setSelectedScope(event.target.value);
              }}
            >
              {kind === 'products' && <option value="all-active">Todas las sucursales</option>}
              {activeBranches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
            </select>
          </div>
        </label> : <div className="availability-static-scope">
          <MapPin size={18} aria-hidden="true" />
          <span><small>Sucursal</small><strong>{selectedBranch.name}</strong></span>
        </div>}
        <label className="availability-field availability-field--search">
          <span>Buscar producto</span>
          <div className="availability-control-with-icon">
            <Search size={17} />
            <input
              aria-label="Buscar disponibilidad"
              placeholder="Nombre o clave del producto"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
        </label>
      </div>

      <div className={`availability-scope-note ${allActive ? 'corporate' : 'branch'}`}>
        {allActive
          ? <><Store size={18} /><span><strong>Todas las sucursales actuales</strong> Los cambios masivos no alteran el valor predeterminado de sucursales futuras.</span></>
          : <><MapPin size={18} /><span><strong>Sólo {selectedBranch.name}</strong> La venta POS y la publicación digital se controlan de forma independiente.</span></>}
      </div>

      {rows.isPending && <p role="status" className="availability-message">Cargando disponibilidad…</p>}
      {(rows.error || mutation.error || visibilityMutation.error) && (
        <p role="alert" className="availability-message availability-message--error">
          {(rows.error || mutation.error || visibilityMutation.error)?.message}{' '}
          <button type="button" onClick={() => void rows.refetch()}>Reintentar</button>
        </p>
      )}
      {statusMessage && <p role="status" className="availability-message availability-message--success">{statusMessage}</p>}
      {!rows.isPending && !rows.error && !visibleRows.length && <p className="availability-empty">No hay registros que coincidan.</p>}

      <div className="availability-product-grid">
        {visibleRows.map((row) => {
          const id = rowId(row);
          const available = row.effective_availability ?? row.effective_enabled;
          const local = row.has_local_override ?? row.override != null;
          const applicable = row.applicable_branch_count || activeBranches.length;
          const availabilityText = allActive
            ? `${row.available_branch_count || 0} de ${applicable} disponibles`
            : available ? 'Disponible en POS' : 'No disponible en POS';
          const visibilityText = allActive
            ? `${row.digital_menu_visible_branch_count || 0} de ${applicable} en menú digital`
            : row.show_in_digital_menu !== false ? 'Visible en menú digital' : 'Oculto del menú digital';
          const summaryLabel = row.availability_summary === 'all'
            ? 'Todas disponibles'
            : row.availability_summary === 'none' ? 'Ninguna disponible' : 'Configuración mixta';
          return (
            <article className="availability-product-card" key={`${id}:${row.product_name || ''}`}>
              <div className="availability-product-card__identity">
                <div className="availability-product-card__title-row">
                  <strong>{row.name}</strong>
                  <span className={`availability-status-pill ${available ? 'available' : 'unavailable'}`}>{availabilityText}</span>
                </div>
                <span className="availability-product-card__sku">Clave {row.product_name || row.sku || 'sin clave'}</span>
                <small>{allActive ? `${applicable} sucursales aplicables · ${summaryLabel}` : `${local ? 'Excepción local' : 'Hereda configuración'} · ${row.status || row.central_status || 'active'}`}</small>
              </div>

              {kind === 'products' && <label className={`availability-digital-toggle ${row.show_in_digital_menu === false || row.digital_menu_summary === 'none' ? 'off' : ''}`}>
                {allActive ? <AggregateVisibilityCheckbox
                  row={row}
                  disabled={!canManage || visibilityMutation.isPending}
                  onChange={(next) => mutateVisibility(id, next, applicable)}
                /> : <input
                  type="checkbox"
                  checked={row.show_in_digital_menu !== false}
                  disabled={!canManage || visibilityMutation.isPending}
                  aria-label={`Mostrar ${row.name} en menú digital`}
                  onChange={(event) => mutateVisibility(id, event.target.checked, 1)}
                />}
                <span className="availability-digital-toggle__track" aria-hidden="true"><span /></span>
                <span className="availability-digital-toggle__copy"><Eye size={17} /><span><strong>{visibilityText}</strong>{!available && !allActive && <small>Se publicará sólo cuando vuelva a estar disponible.</small>}</span></span>
              </label>}

              {canManage && <div className="availability-actions" aria-label={`Disponibilidad de ${row.name}`}>
                <button
                  type="button"
                  className={(!allActive && local && available) || (allActive && row.availability_summary === 'all') ? 'active' : ''}
                  aria-pressed={(!allActive && local && available) || (allActive && row.availability_summary === 'all')}
                  disabled={mutation.isPending}
                  onClick={() => mutateAvailability(id, 'available', applicable)}
                ><CheckCircle2 size={16} /> Disponible</button>
                <button
                  type="button"
                  className={(!allActive && local && !available) || (allActive && row.availability_summary === 'none') ? 'active danger' : ''}
                  aria-pressed={(!allActive && local && !available) || (allActive && row.availability_summary === 'none')}
                  disabled={mutation.isPending}
                  onClick={() => mutateAvailability(id, 'unavailable', applicable)}
                ><XCircle size={16} /> No disponible</button>
                <button
                  type="button"
                  className={!allActive && !local ? 'active muted' : ''}
                  aria-pressed={!allActive && !local}
                  disabled={mutation.isPending}
                  onClick={() => mutateAvailability(id, 'inherit', applicable)}
                ><Undo2 size={16} /> Heredar</button>
              </div>}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function AvailabilityAdministration() {
  return <BranchAvailability kind="products" standalone />;
}

export function CatalogAdministration({ kind }: { kind: Kind }) {
  const central = useAdminPermission('catalog.manage');
  const recipes = useAdminPermission('recipes.manage');
  const branchAccess = useAdminPermission('branch.admin.access');
  const branchManage = useAdminPermission('catalog.branch.manage');
  if (kind === 'products' && !central && !recipes && branchAccess) {
    return <Navigate to="/availability" replace />;
  }
  return <>
    {central
      ? kind === 'products' ? <ProductsList /> : kind === 'variations' ? <VariationNotes /> : <IngredientExtras />
      : kind === 'products' && recipes ? <RecipesWorkspace /> : <h1>{kind === 'products' ? 'Productos y recetas' : kind === 'variations' ? 'Comentarios del pedido' : 'Ingredientes adicionales'}</h1>}
    {kind === 'ingredient-extras' && branchAccess && branchManage && <BranchAvailability kind={kind} />}
  </>;
}
