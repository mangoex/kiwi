import { useState } from 'react';
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
}
function BranchAvailability({kind}:{kind:Kind}) {
  const {session} = useAdminSession();
  const canManage = useAdminPermission('catalog.branch.manage');
  const branchId = session.active_branch.id;
  const client = useQueryClient();
  const [search,setSearch] = useState('');
  const endpoint = `/branch-administration/catalog/${resources[kind]}`;
  const query = `?branch_id=${encodeURIComponent(branchId)}`;
  const key = ['branch-availability',kind,session.user.id,branchId];
  const rows = useQuery<AvailabilityRow[]>({queryKey:key,queryFn:({signal})=>fetchApi(endpoint+query,{signal})});
  const mutation = useMutation({
    mutationFn: ({id,action}:{id:string;action:string}) => {
      if (!canManage) throw new Error('No tienes permiso para modificar disponibilidad.');
      return fetchApi(`${endpoint}/${encodeURIComponent(id)}${kind === 'products' ? '/availability' : ''}${query}`, {method:'PUT',body:JSON.stringify({action})});
    },
    onSuccess:() => client.invalidateQueries({queryKey:key}),
  });
  const visibilityMutation = useMutation({
    mutationFn: ({id,visible}:{id:string;visible:boolean}) => {
      if (!canManage || kind !== 'products') throw new Error('No tienes permiso para modificar la visibilidad digital.');
      return fetchApi(`${endpoint}/${encodeURIComponent(id)}/digital-menu-visibility${query}`, {method:'PUT',body:JSON.stringify({visible})});
    },
    onSuccess:() => client.invalidateQueries({queryKey:key}),
  });
  const visible = (rows.data || []).filter(row => `${row.name} ${row.product_name || ''} ${row.sku || ''}`.toLowerCase().includes(search.toLowerCase()));
  return <section style={{marginTop:24,padding:24,border:'1px solid #d4d4d4',borderRadius:12}}>
    <h2>Disponibilidad en {session.active_branch.name}</h2>
    <p>{kind === 'products' ? 'Configura la venta local y la publicación en el menú digital de esta sucursal.' : 'Configura excepciones locales sobre el catálogo vigente de esta sucursal.'}</p>
    <input aria-label="Buscar disponibilidad" placeholder="Buscar por nombre o producto" value={search} onChange={event=>setSearch(event.target.value)} style={{padding:10,width:'min(100%,440px)'}} />
    {rows.isPending && <p role="status">Cargando disponibilidad…</p>}
    {(rows.error || mutation.error || visibilityMutation.error) && <p role="alert">{(rows.error || mutation.error || visibilityMutation.error)?.message} <button onClick={()=>void rows.refetch()}>Reintentar</button></p>}
    {!rows.isPending && !rows.error && !visible.length && <p>No hay registros que coincidan.</p>}
    <div style={{display:'grid',gap:12,marginTop:16}}>{visible.map(row=>{
      const id = row.id || row.option_id || '';
      const available = row.effective_availability ?? row.effective_enabled;
      const local = row.has_local_override ?? row.override != null;
      return <article key={`${id}:${row.product_name || ''}`} style={{display:'flex',gap:16,alignItems:'center',flexWrap:'wrap',borderBottom:'1px solid #e5e5e5',padding:'12px 0'}}>
        <div style={{flex:1,minWidth:180}}><strong>{row.name}</strong><div>{row.product_name || row.sku}</div><small>{local ? 'Excepción local' : 'Herencia del catálogo'} · {row.status || row.central_status}</small></div>
        <span>{available ? 'Disponible' : 'No disponible'}</span>
        {kind === 'products' && <label style={{display:'inline-flex',alignItems:'center',gap:8,padding:'8px 10px'}}>
          <input
            type="checkbox"
            checked={row.show_in_digital_menu !== false}
            disabled={!canManage || visibilityMutation.isPending}
            aria-label={`Mostrar ${row.name} en menú digital`}
            onChange={event=>visibilityMutation.mutate({id,visible:event.target.checked})}
          />
          <span>Mostrar en menú digital{!available && <small style={{display:'block',color:'#666'}}>Se publicará sólo cuando vuelva a estar disponible.</small>}</span>
        </label>}
        {canManage && <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{(['available','unavailable','inherit'] as const).map((action,index)=><button key={action} disabled={mutation.isPending} onClick={()=>mutation.mutate({id,action})} style={{padding:'10px 14px'}}>{['Disponible','No disponible','Heredar'][index]}</button>)}</div>}
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
