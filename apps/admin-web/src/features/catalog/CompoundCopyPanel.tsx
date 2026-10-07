import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import {
  Button,
  discardWorkspaceSnapshot,
  isWorkspaceRejection,
  readWorkspaceSnapshot,
  registerWorkspaceNavigationGuard,
  registerWorkspaceSnapshot,
  usePythonPreview,
} from '@restaurantos/ui';
import { resolveBranchId, getSessionUser } from '../../lib/branchContext';
import { centsToMxn } from './ingredientVariationMoney';

type GroupOption = {
  id?: string;
  name: string;
  component_quantity?: string | number | null;
  price_delta_cents: number;
};
type Group = {
  id?: string;
  name: string;
  minimum_selections: number;
  maximum_selections: number;
  included_selections: number;
  options: GroupOption[];
};
type ProductSummary = {
  id: string;
  name: string;
  catalog_scope?: 'organization' | 'branch';
};
type PreviewComponent = {
  item_id: string;
  item_name?: string;
  gross_quantity: string;
  unit_code?: string;
};
type SelectionPreview = {
  source: 'python';
  context_fingerprint: string;
  line_total_cents: number;
  modifier_total_cents: number;
  consumption: { components: PreviewComponent[] };
};

export interface CopyResult {
  version: number;
  groups: unknown[];
  result: 'applied' | 'replay';
}

interface CopyRecovery {
  key: string;
  body: string;
  sourceId: string;
}

const previewErrorMessage = (error: string): string => {
  if (/requires at least/i.test(error)) {
    return 'La configuración vigente exige completar las selecciones obligatorias.';
  }
  if (/allows at most|maximum/i.test(error)) {
    return 'La selección excede el máximo permitido por la configuración vigente.';
  }
  return error;
};

export function CompoundCopyPanel({ productId, expectedVersion, disabled, onCopied, onBusyChange }: {
  productId: string;
  expectedVersion: number;
  disabled: boolean;
  onCopied: (result: CopyResult) => void | Promise<void>;
  onBusyChange: (busy: boolean) => void;
}) {
  const actorId = getSessionUser().id || '';
  const recoveryKey = 'compound-copy:' + actorId + ':' + productId;
  const [recovery] = useState(() => readWorkspaceSnapshot<CopyRecovery>(recoveryKey));
  const [sourceId, setSourceId] = useState(recovery?.sourceId || '');
  const [accepted, setAccepted] = useState(false);
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [uncertain, setUncertain] = useState(Boolean(recovery));
  const intent = useRef<{ key: string; body: string } | null>(recovery || null);

  useEffect(() => {
    discardWorkspaceSnapshot(recoveryKey);
    return registerWorkspaceSnapshot(recoveryKey, () => intent.current ? {
      ...intent.current,
      sourceId: JSON.parse(intent.current.body).source_product_id,
    } : null);
  }, [recoveryKey]);

  useEffect(() => {
    if (recovery) onBusyChange(true);
  }, [recovery, onBusyChange]);

  useEffect(() => {
    if (!pending && !uncertain) return;
    const unregister = registerWorkspaceNavigationGuard(() => {
      window.alert('Recupera el resultado de la copia antes de salir.');
      return false;
    });
    const unload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', unload);
    return () => {
      unregister();
      window.removeEventListener('beforeunload', unload);
    };
  }, [pending, uncertain]);

  const productsQuery = useQuery<ProductSummary[]>({
    queryKey: ['compound-copy-products'],
    queryFn: () => fetchApi<ProductSummary[]>('/catalog/products'),
    retry: false,
  });
  const products = Array.isArray(productsQuery.data)
    ? productsQuery.data.filter((product) => product.catalog_scope === 'organization')
    : [];
  const source = useQuery<{ expected_version: number; groups: Group[] }>({
    queryKey: ['compound-copy-source', sourceId],
    queryFn: () => fetchApi('/products/' + sourceId + '/modifier-configuration'),
    enabled: Boolean(sourceId),
    retry: false,
  });

  const copy = async () => {
    if (pending || (!uncertain && (productsQuery.isError || !accepted || !source.data))) return;
    intent.current ??= {
      key: 'compound-copy-' + crypto.randomUUID(),
      body: JSON.stringify({
        source_product_id: sourceId,
        expected_source_version: source.data?.expected_version,
        expected_target_version: expectedVersion,
      }),
    };
    setPending(true);
    onBusyChange(true);
    setMessage('');
    let applied = false;
    try {
      const result = await fetchApi<CopyResult>('/products/' + productId + '/modifier-configuration/copy', {
        method: 'POST',
        headers: { 'Idempotency-Key': intent.current.key },
        body: intent.current.body,
      });
      applied = true;
      await onCopied(result);
      intent.current = null;
      setUncertain(false);
      setAccepted(false);
      onBusyChange(false);
      setMessage('Copia registrada y destino releído. El origen y los pedidos históricos conservan sus datos.');
    } catch (error) {
      const rejected = !applied && error instanceof ApiError
        && isWorkspaceRejection(error.status, error.code, uncertain, 'copy');
      setUncertain(!rejected);
      setMessage(error instanceof Error ? error.message : 'No se confirmó la copia.');
      if (rejected) {
        intent.current = null;
        setAccepted(false);
        onBusyChange(false);
      }
    } finally {
      setPending(false);
    }
  };

  const catalogUnavailable = productsQuery.isError;
  return <section className="modifier-group-card modifier-tool-card" aria-label="Copiar configuración completa">
    <h3>Copiar grupos y opciones de otro producto</h3>
    <p>Esta acción reemplaza la configuración completa del producto actual después de tu confirmación.</p>
    <label>Producto de origen
      <select
        className="modifier-control"
        disabled={disabled || pending || uncertain || productsQuery.isLoading || catalogUnavailable}
        value={sourceId}
        onChange={(event) => {
          setSourceId(event.target.value);
          setAccepted(false);
        }}
      >
        <option value="">{productsQuery.isLoading ? 'Cargando productos…' : 'Selecciona producto'}</option>
        {products.filter((product) => product.id !== productId).map((product) => (
          <option key={product.id} value={product.id}>{product.name}</option>
        ))}
      </select>
    </label>
    {productsQuery.isError && <p role="alert">{uncertain
      ? 'No se pudo actualizar el catálogo corporativo. La recuperación conserva la intención pendiente.'
      : 'No se pudo cargar el catálogo corporativo. No puedes iniciar una copia nueva.'}</p>}
    {source.isError && <p role="alert">No se pudo consultar el origen. Reintenta su lectura.</p>}
    {source.data && <>
      <p>Origen v{source.data.expected_version} · destino v{expectedVersion}. Se reemplazarán todos los grupos y opciones del destino.</p>
      <ul>{source.data.groups.map((group) => <li key={group.id || group.name}>
        {group.name} · mínimo {group.minimum_selections}, máximo {group.maximum_selections}, incluidos {group.included_selections}
        <ul>{group.options.map((option) => <li key={option.id || option.name}>
          {option.name} · cantidad {option.component_quantity ?? '—'} · recargo ${centsToMxn(option.price_delta_cents)} MXN
        </li>)}</ul>
      </li>)}</ul>
      <p>Precio base, receta, combo fijo y disponibilidad conservan sus valores.</p>
      <label><input
        type="checkbox"
        checked={accepted}
        disabled={disabled || pending || uncertain}
        onChange={(event) => setAccepted(event.target.checked)}
      /> Revisé el reemplazo completo de grupos y opciones del destino.</label>
    </>}
    {message && <p role="alert">{message}</p>}
    {uncertain && <p>Recupera el resultado de esta copia antes de editar el destino.</p>}
    <div className="modifier-tool-actions">
      <Button
        disabled={disabled || pending || (!uncertain && (catalogUnavailable || !accepted || !source.data))}
        onClick={() => void copy()}
      >{pending ? 'Copiando…' : uncertain ? 'Recuperar copia' : 'Confirmar copia completa'}</Button>
      <Button
        variant="secondary"
        disabled={disabled || pending || uncertain || !sourceId}
        onClick={() => {
          setAccepted(false);
          void source.refetch();
        }}
      >Releer origen</Button>
    </div>
  </section>;
}

export function CompoundSelectionPreview({ productId, groups, disabled }: {
  productId: string;
  groups: Group[];
  disabled: boolean;
}) {
  const branchId = resolveBranchId();
  const [selected, setSelected] = useState<string[]>([]);
  const [requestedSelectionKey, setRequestedSelectionKey] = useState<string | null>(null);
  const [requestRevision, setRequestRevision] = useState(0);
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const selectionKey = selected.join('|');
  const groupCounts = groups.map((group) => ({
    group,
    count: group.options.reduce(
      (total, option) => total + (option.id && selectedSet.has(option.id) ? 1 : 0),
      0,
    ),
  }));
  const belowMinimum = groupCounts.find(({ group, count }) => count < group.minimum_selections);
  const aboveMaximum = groupCounts.find(({ group, count }) => count > group.maximum_selections);
  const selectionIsValid = !belowMinimum && !aboveMaximum;
  const canRequest = Boolean(branchId && !disabled && selectionIsValid);
  const preview = usePythonPreview<SelectionPreview>(
    fetchApi,
    '/products/' + productId + '/modifier-configuration/selection-preview',
    { branch_id: branchId, quantity: 1, modifiers: selected.map((option_id) => ({ option_id })) },
    canRequest && requestedSelectionKey === selectionKey,
    `${selectionKey}:${requestRevision}`,
  );

  let guidance = '';
  if (!branchId) guidance = 'Selecciona una sucursal para calcular la vista previa.';
  else if (disabled) guidance = 'Guarda o deshaz los cambios del editor antes de probar la configuración vigente.';
  else if (belowMinimum) {
    guidance = `${belowMinimum.group.name}: selecciona al menos ${belowMinimum.group.minimum_selections}.`;
  } else if (aboveMaximum) {
    guidance = `${aboveMaximum.group.name}: reduce la selección a ${aboveMaximum.group.maximum_selections}.`;
  }

  const toggleOption = (optionId: string, checked: boolean) => {
    setSelected((rows) => checked ? [...rows, optionId] : rows.filter((id) => id !== optionId));
    setRequestedSelectionKey(null);
  };

  return <section className="modifier-group-card modifier-tool-card" aria-label="Probar selección guardada">
    <h3>Probar selección guardada</h3>
    <p>Prueba una unidad con la configuración vigente en la sucursal seleccionada. El cálculo final siempre lo realiza Python.</p>
    {groups.map((group) => {
      const selectedInGroup = group.options.reduce(
        (total, option) => total + (option.id && selectedSet.has(option.id) ? 1 : 0),
        0,
      );
      return <fieldset key={group.id || group.name} disabled={disabled}>
        <legend>{group.name} · mínimo {group.minimum_selections}, máximo {group.maximum_selections}</legend>
        {group.options.map((option) => {
          const checked = Boolean(option.id && selectedSet.has(option.id));
          const maximumReached = !checked && selectedInGroup >= group.maximum_selections;
          return <label key={option.id || option.name} className="modifier-preview-option">
            <input
              type="checkbox"
              checked={checked}
              disabled={disabled || !option.id || maximumReached}
              onChange={(event) => {
                if (option.id) toggleOption(option.id, event.target.checked);
              }}
            /> {option.name}
          </label>;
        })}
      </fieldset>;
    })}
    {guidance && <p role="status">{guidance}</p>}
    <Button
      disabled={!canRequest || preview.pending}
      onClick={() => {
        setRequestedSelectionKey(selectionKey);
        setRequestRevision((revision) => revision + 1);
      }}
    >{preview.pending ? 'Calculando…' : 'Calcular vista previa'}</Button>
    {preview.error && <p role="alert">{previewErrorMessage(preview.error)}</p>}
    {preview.data && <div role="status" className="modifier-preview-result">
      <p>Precio: ${centsToMxn(preview.data.line_total_cents)} MXN · adicionales: ${centsToMxn(preview.data.modifier_total_cents)} MXN</p>
      <p>Cálculo verificado por Python.</p>
      <ul>{preview.data.consumption.components.map((row) => <li key={row.item_id}>
        {row.item_name || row.item_id}: {row.gross_quantity} {row.unit_code}
      </li>)}</ul>
    </div>}
  </section>;
}
