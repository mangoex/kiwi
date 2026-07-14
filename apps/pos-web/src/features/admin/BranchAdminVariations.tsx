import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, MessageSquareText, Search } from 'lucide-react';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { usePosSession } from '../../session';
import { BranchAdminPage } from './BranchAdminPage';

interface VariationNote { product_id: string; product_name: string; option_id: string; name: string; central_status: string; effective_enabled: boolean; override: boolean | null; }
interface IngredientVariation extends VariationNote { variation_id: string; effect_type: 'add' | 'remove'; inventory_item_name?: string; inventory_item_sku?: string | null; unit_code?: string | null; }

export default function BranchAdminVariations() {
  const { hasPermission, session } = usePosSession();
  const [notes, setNotes] = useState<VariationNote[]>([]);
  const [ingredients, setIngredients] = useState<IngredientVariation[]>([]);
  const [tab, setTab] = useState<'notes' | 'ingredients'>('notes');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [acting, setActing] = useState<string | null>(null);
  const canManage = hasPermission('catalog.branch.manage');
  const branchName = session?.active_branch?.name;
  const load = async () => {
    setLoading(true); setError('');
    try { const [simpleNotes, ingredientChanges] = await Promise.all([fetchApi<VariationNote[]>('/branch-administration/catalog/variation-notes'), fetchApi<IngredientVariation[]>('/branch-administration/catalog/ingredient-variations')]); setNotes(simpleNotes); setIngredients(ingredientChanges); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : 'No fue posible cargar las variaciones.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const visible = useMemo(() => { const source = tab === 'notes' ? notes : ingredients; const q = search.trim().toLowerCase(); return !q ? source : source.filter((note) => `${note.product_name} ${note.name} ${(note as IngredientVariation).inventory_item_name || ''} ${(note as IngredientVariation).inventory_item_sku || ''}`.toLowerCase().includes(q)); }, [notes, ingredients, search, tab]);
  const setAvailability = async (optionId: string, action: 'available' | 'unavailable' | 'inherit') => {
    setActing(optionId); setError('');
    try { const endpoint = tab === 'notes' ? 'variation-notes' : 'ingredient-variations'; await fetchApi(`/branch-administration/catalog/${endpoint}/${encodeURIComponent(optionId)}`, { method: 'PUT', body: JSON.stringify({ action }) }); await load(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : 'No fue posible actualizar la disponibilidad.'); }
    finally { setActing(null); }
  };
  return <BranchAdminPage title="Variaciones y cambios" description={`Disponibilidad local por acción${branchName ? ` para ${branchName}` : ''}.`} icon={MessageSquareText}>
    <div role="tablist" style={{ display: 'flex', gap: 8, marginBottom: 16 }}><button aria-selected={tab === 'notes'} onClick={() => setTab('notes')}>Notas simples</button><button aria-selected={tab === 'ingredients'} onClick={() => setTab('ingredients')}>Cambios de insumos</button></div>
    <div style={{ position: 'relative', maxWidth: 440, marginBottom: 16 }}><Search size={16} style={{ position: 'absolute', left: 10, top: 11, color: '#64748b' }} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por producto o nota…" style={{ width: '100%', boxSizing: 'border-box', padding: '9px 12px 9px 32px', border: '1px solid #cbd5e1', borderRadius: 8 }} /></div>
    {error && <div role="alert" style={{ color: '#b91c1c', display: 'flex', gap: 6, alignItems: 'center' }}><AlertCircle size={16} />{error} <button onClick={() => void load()}>Reintentar</button></div>}
    {loading ? <p>Cargando variaciones…</p> : visible.length === 0 ? <p style={{ color: '#64748b' }}>No hay cambios que coincidan.</p> : <div style={{ display: 'grid', gap: 8 }}>{visible.map((note) => { const ingredient = note as IngredientVariation; const ingredientContext = tab === 'ingredients' ? `${ingredient.inventory_item_name || 'Insumo'}${ingredient.inventory_item_sku ? ` (${ingredient.inventory_item_sku})` : ''}${ingredient.unit_code ? ` · ${ingredient.unit_code}` : ''} · ${ingredient.effect_type === 'add' ? 'Con' : 'Sin'} · ` : ''; return <div key={note.option_id} style={{ padding: 12, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}><div style={{ flex: 1 }}><strong>{note.name}</strong><div style={{ fontSize: 12, color: '#64748b' }}>{ingredientContext}{note.product_name} · Central: {note.central_status}</div></div><span style={{ color: note.effective_enabled ? '#047857' : '#b91c1c', fontSize: 13 }}>{note.effective_enabled ? 'Disponible' : 'No disponible'}</span>{canManage && <div style={{ display: 'flex', gap: 6 }}><button disabled={acting === note.option_id} onClick={() => void setAvailability(note.option_id, 'available')}>Disponible</button><button disabled={acting === note.option_id} onClick={() => void setAvailability(note.option_id, 'unavailable')}>No disponible</button><button disabled={acting === note.option_id} onClick={() => void setAvailability(note.option_id, 'inherit')}>Heredar</button></div>}</div>; })}</div>}
  </BranchAdminPage>;
}
