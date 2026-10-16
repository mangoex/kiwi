import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '@restaurantos/api-client';
import { useAdminPermission, useAdminSession } from '../../lib/adminSession';
import ProductsList from './ProductsList';
import VariationNotes from './VariationNotes';
import IngredientExtras from './IngredientExtras';
import RecipesWorkspace from '../recipes/RecipesWorkspace';

type Kind = 'products' | 'variations' | 'ingredient-extras';
const resources: Record<Kind,string> = {products:'products',variations:'variation-notes','ingredient-extras':'ingredient-variations'};
interface AvailabilityRow {
  id?:string; option_id?:string; name:string; sku?:string; product_name?:string;
  effective_availability?:boolean; effective_enabled?:boolean;
  has_local_override?:boolean; override?:boolean | null; status?:string; central_status?:string;
  show_in_digital_menu?:boolean; has_digital_menu_override?:boolean;
  applicable_branch_count?:number; available_branch_count?:number;
  digital_menu_visible_branch_count?:number;
  availability_summary?:'all'|'none'|'mixed'; digital_menu_summary?:'all'|'none'|'mixed';
}

interface AllActiveSummary {scope:'all_active';branches:{id:string;name:string;code:string}[];items:AvailabilityRow[]}

function AggregateVisibilityCheckbox({row,disabled,onChange}:{row:AvailabilityRow;disabled:boolean;onChange:(visible:boolean)=>void}) {
  const input = useRef<HTMLInputElement>(null);
  const mixed = row.digital_menu_summary === 'mixed';
  const checked = row.digital_menu_summary === 'all';
  useEffect(() => { if (input.current) input.current.indeterminate = mixed; }, [mixed]);
  return <input ref={input} type="checkbox" checked={checked} aria-checked={mixed ? 'mixed' : checked}
    disabled={disabled} aria-label={`Mostrar ${row.name} en menú digital en todas las sucursales actuales`}
    onChange={event=>onChange(event.target.checked)} />;
}

function BranchAvailability({kind}:{kind:Kind}) {
  const {session} = useAdminSession();
  const canManage = useAdminPermission('catalog.branch.manage');
  const client = useQueryClient();
  const [search,setSearch] = useState('');
  const [selectedScope,setSelectedScope] = useState(session.active_branch.id);
  const activeBranches = session.allowed_branches.filter(branch=>branch.status === 'active');
  const canSelectScope = session.scope.level === 'organization' && activeBranches.length > 1;
  const allActive = kind === 'products' && canSelectScope && selectedScope === 'all-active';
  const selectedBranch = activeBranches.find(branch=>branch.id === selectedScope) || session.active_branch;
  const branchId = selectedBranch.id;
  useEffect(() => {
    if (selectedScope !== 'all-active' && !activeBranches.some(branch=>branch.id === selectedScope)) {
      setSelectedScope(session.active_branch.id);
    }
  }, [activeBranches, selectedScope, session.active_branch.id]);
  const endpoint = `/branch-administration/catalog/${resources[kind]}`;
  const query = allActive ? '' : `?branch_id=${encodeURIComponent(branchId)}`;
  const key = ['branch-availability',kind,session.user.id,selectedScope];
  const rows = useQuery<AvailabilityRow[]>({queryKey:key,queryFn:async ({signal})=>{
    if (allActive) {
      const summary = await fetchApi<AllActiveSummary>(`${endpoint}/all-active-summary`,{signal});
      return summary.items;
    }
    return fetchApi<AvailabilityRow[]>(endpoint+query,{signal});
  }});
  const confirmAll = (description:string,branchCount:number) => window.confirm(
    `${description} en ${branchCount} sucursales actuales aplicables. Las sucursales futuras no cambiarán. ¿Deseas continuar?`,
  );
  const mutation = useMutation({
    mutationFn: ({id,action}:{id:string;action:string}) => {
      if (!canManage) throw new Error('No tienes permiso para modificar disponibilidad.');
      const suffix = kind === 'products' ? allActive ? '/availability/all-active' : '/availability' : '';
      return fetchApi(`${endpoint}/${encodeURIComponent(id)}${suffix}${query}`, {method:'PUT',body:JSON.stringify({action})});
    },
    onSuccess:() => client.invalidateQueries({queryKey:key}),
  });
  const visibilityMutation = useMutation({
    mutationFn: ({id,visible}:{id:string;visible:boolean}) => {
      if (!canManage || kind !== 'products') throw new Error('No tienes permiso para modificar la visibilidad digital.');
      const suffix = allActive ? '/digital-menu-visibility/all-active' : '/digital-menu-visibility';
      return fetchApi(`${endpoint}/${encodeURIComponent(id)}${suffix}${query}`, {method:'PUT',body:JSON.stringify({visible})});
    },
    onSuccess:() => client.invalidateQueries({queryKey:key}),
  });
  const mutateAvailability = (id:string,action:string,branchCount:number) => {
    if (allActive && !confirmAll(`${action === 'available' ? 'Marcar como disponible' : action === 'unavailable' ? 'Marcar como no disponible' : 'Heredar la disponibilidad'} el producto`,branchCount)) return;
    mutation.mutate({id,action});
  };
  const mutateVisibility = (id:string,visible:boolean,branchCount:number) => {
    if (allActive && !confirmAll(`${visible ? 'Mostrar' : 'Ocultar'} el producto en el menú digital`,branchCount)) return;
    visibilityMutation.mutate({id,visible});
  };
  const visible = (rows.data || []).filter(row => `${row.name} ${row.product_name || ''} ${row.sku || ''}`.toLowerCase().includes(search.toLowerCase()));
  return <section style={{marginTop:24,padding:24,border:'1px solid #d4d4d4',borderRadius:12}}>
    <h2>Disponibilidad en {allActive ? 'todas las sucursales actuales' : selectedBranch.name}</h2>
    <p>{kind === 'products' ? allActive ? 'Aplica venta local y publicación digital a las sucursales activas existentes; las futuras conservarán los valores predeterminados.' : 'Configura la venta local y la publicación en el menú digital de esta sucursal.' : 'Configura excepciones locales sobre el catálogo vigente de esta sucursal.'}</p>
    <div style={{display:'flex',gap:12,alignItems:'end',flexWrap:'wrap'}}>
      {canSelectScope && <label style={{display:'grid',gap:6,fontWeight:600}}>Sucursal
        <select aria-label="Sucursal para disponibilidad" value={selectedScope} disabled={mutation.isPending || visibilityMutation.isPending}
          onChange={event=>setSelectedScope(event.target.value)} style={{padding:10,minWidth:240}}>
          {kind === 'products' && <option value="all-active">Todas las sucursales actuales</option>}
          {activeBranches.map(branch=><option key={branch.id} value={branch.id}>{branch.name}</option>)}
        </select>
      </label>}
      <input aria-label="Buscar disponibilidad" placeholder="Buscar por nombre o producto" value={search} onChange={event=>setSearch(event.target.value)} style={{padding:10,width:'min(100%,440px)'}} />
    </div>
    {rows.isPending && <p role="status">Cargando disponibilidad…</p>}
    {(rows.error || mutation.error || visibilityMutation.error) && <p role="alert">{(rows.error || mutation.error || visibilityMutation.error)?.message} <button onClick={()=>void rows.refetch()}>Reintentar</button></p>}
    {!rows.isPending && !rows.error && !visible.length && <p>No hay registros que coincidan.</p>}
    <div style={{display:'grid',gap:12,marginTop:16}}>{visible.map(row=>{
      const id = row.id || row.option_id || '';
      const available = row.effective_availability ?? row.effective_enabled;
      const local = row.has_local_override ?? row.override != null;
      const applicable = row.applicable_branch_count || activeBranches.length;
      const availabilityText = allActive ? `Disponible en ${row.available_branch_count || 0} de ${applicable}` : available ? 'Disponible' : 'No disponible';
      const summaryLabel = row.availability_summary === 'all' ? 'todas disponibles' : row.availability_summary === 'none' ? 'ninguna disponible' : 'estado mixto';
      return <article key={`${id}:${row.product_name || ''}`} style={{display:'flex',gap:16,alignItems:'center',flexWrap:'wrap',borderBottom:'1px solid #e5e5e5',padding:'12px 0'}}>
        <div style={{flex:1,minWidth:180}}><strong>{row.name}</strong><div>{row.product_name || row.sku}</div><small>{allActive ? `${applicable} sucursales aplicables · ${summaryLabel}` : `${local ? 'Excepción local' : 'Herencia del catálogo'} · ${row.status || row.central_status}`}</small></div>
        <span>{availabilityText}</span>
        {kind === 'products' && <label style={{display:'inline-flex',alignItems:'center',gap:8,padding:'8px 10px'}}>
          {allActive ? <AggregateVisibilityCheckbox row={row} disabled={!canManage || visibilityMutation.isPending}
            onChange={next=>mutateVisibility(id,next,applicable)} /> : <input
            type="checkbox"
            checked={row.show_in_digital_menu !== false}
            disabled={!canManage || visibilityMutation.isPending}
            aria-label={`Mostrar ${row.name} en menú digital`}
            onChange={event=>mutateVisibility(id,event.target.checked,1)}
          />}
          <span>{allActive ? `Menú digital en ${row.digital_menu_visible_branch_count || 0} de ${applicable}` : 'Mostrar en menú digital'}{!available && !allActive && <small style={{display:'block',color:'#666'}}>Se publicará sólo cuando vuelva a estar disponible.</small>}</span>
        </label>}
        {canManage && <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{(['available','unavailable','inherit'] as const).map((action,index)=><button key={action} disabled={mutation.isPending} onClick={()=>mutateAvailability(id,action,applicable)} style={{padding:'10px 14px'}}>{['Disponible','No disponible','Heredar'][index]}</button>)}</div>}
      </article>;
    })}</div>
  </section>;
}
export function CatalogAdministration({kind}:{kind:Kind}) {
  const central = useAdminPermission('catalog.manage');
  const recipes = useAdminPermission('recipes.manage');
  const branchAccess = useAdminPermission('branch.admin.access');
  const branchManage = useAdminPermission('catalog.branch.manage');
  return <>
    {central ? kind === 'products' ? <ProductsList /> : kind === 'variations' ? <VariationNotes /> : <IngredientExtras />
      : kind === 'products' && recipes ? <RecipesWorkspace /> : <h1>{kind === 'products' ? 'Productos y recetas' : kind === 'variations' ? 'Comentarios del pedido' : 'Ingredientes adicionales'}</h1>}
    {branchAccess && (kind === 'products' || branchManage) && <BranchAvailability kind={kind} />}
  </>;
}
