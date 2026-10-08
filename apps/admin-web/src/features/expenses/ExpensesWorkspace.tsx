import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, fetchApi } from '@restaurantos/api-client';
import { registerWorkspaceNavigationGuard } from '@restaurantos/ui';
import { useAdminSession, useAdminPermission } from '../../lib/adminSession';
import type { ExpenseConcept, ExpenseDocument, ExpenseInput, ExpenseCashContext, ExpenseSummary } from '../../../../../packages/contracts/operating-expenses-v1';
import { expenseCents, expenseMethods } from './expenseState';
import './expenses.css';
const money = (cents: number) => new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(cents / 100);
type Attempt = {
    path: string;
    method: string;
    key: string;
    body: Record<string, unknown>;
};
const empty = { concept_id: '', document_date: '', amount: '', tax: '', payment_method: '', reference: '', notes: '', evidence: '' };
export default function ExpensesWorkspace({ catalog = false }: {
    catalog?: boolean;
}) {
    const { session } = useAdminSession();
    return <Workspace key={`${session.user.id}:${session.active_branch.id}:${catalog}`} catalog={catalog}/>;
}
function Workspace({ catalog }: {
    catalog: boolean;
}) {
    const { session } = useAdminSession();
    const branch = session.active_branch.id;
    const scope = `${session.user.id}:${branch}`;
    const canWrite = useAdminPermission('expenses.manage');
    const canReadConcepts = useAdminPermission('expense.concept.read');
    const canReadExpenses = useAdminPermission('expenses.read');
    const canCatalog = useAdminPermission('expense.concept.manage');
    const canWithdraw = useAdminPermission('cash.movement.withdraw');
    const canCancel = useAdminPermission('expenses.cancel');
    const canCompensate = useAdminPermission('cash.movement.compensate');
    const canReport = useAdminPermission('reports.expenses.read');
    const queryClient = useQueryClient();
    const [selected, setSelected] = useState<ExpenseDocument | null>(null);
    const [editing, setEditing] = useState(false);
    const [form, setForm] = useState(empty);
    const [concept, setConcept] = useState<ExpenseConcept | null>(null);
    const [conceptForm, setConceptForm] = useState({ code: '', name: '', description: '' });
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [uncertain, setUncertain] = useState(false);
    const [register, setRegister] = useState('');
    const [cancelOpen, setCancelOpen] = useState(false);
    const [reason, setReason] = useState('');
    const [returnEvidence, setReturnEvidence] = useState('');
    const [returned, setReturned] = useState(false);
    const [cursor, setCursor] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [methodFilter, setMethodFilter] = useState('');
    const [conceptFilter, setConceptFilter] = useState('');
    const [from, setFrom] = useState('');
    const [to, setTo] = useState('');
    const alive = useRef(true);
    const attempt = useRef<Attempt | null>(null);
    const sending = useRef(false);
    const storageKey = `expense-attempt:${scope}`;
    const dirty = editing || Boolean(conceptForm.code || conceptForm.name || conceptForm.description) || uncertain;
    useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
    useEffect(() => registerWorkspaceNavigationGuard(() => !busy && (!dirty || (!uncertain && window.confirm('Hay una captura sin guardar. ¿Deseas salir?')))), [dirty, uncertain, busy]);
    useEffect(() => {
        const leave = (event: BeforeUnloadEvent) => { if (dirty || busy)
            event.preventDefault(); };
        window.addEventListener('beforeunload', leave);
        return () => window.removeEventListener('beforeunload', leave);
    }, [dirty, busy]);
    const concepts = useQuery<ExpenseConcept[]>({ queryKey: ['expense-concepts', scope, catalog], queryFn: () => fetchApi(`/expense-concepts?branch_id=${branch}&archived=${catalog && canCatalog}`), enabled: canReadConcepts });
    const filters = new URLSearchParams({ branch_id: branch, cursor, status: statusFilter, payment_method: methodFilter, concept_id: conceptFilter });
    const documents = useQuery<{
        items: ExpenseDocument[];
        next_cursor: string | null;
    }>({ queryKey: ['expenses', scope, filters.toString()], queryFn: () => fetchApi(`/expenses?${filters}`), enabled: !catalog });
    const cash = useQuery<ExpenseCashContext>({ queryKey: ['expense-cash', scope, selected?.id], queryFn: () => fetchApi(`/expenses/cash-context?branch_id=${branch}`), enabled: !catalog && selected?.status === 'draft' && selected.payment_method === 'cash' && canWrite && canWithdraw, staleTime: 0 });
    const reportFilters = new URLSearchParams({ branch_id: branch, from_date: from, to_date: to, concept_id: conceptFilter, payment_method: methodFilter });
    const summary = useQuery<ExpenseSummary>({ queryKey: ['expense-summary', scope, reportFilters.toString()], queryFn: () => fetchApi(`/expenses/summary?${reportFilters}`), enabled: !catalog && canReport && Boolean(from && to && from <= to) });
    useEffect(() => {
        const boxes = cash.data?.open_registers || [];
        const hint = localStorage.getItem(`expense-register:${scope}`) || localStorage.getItem('pos_register_id');
        setRegister(boxes.find(b => b.register_id === hint)?.register_id || (boxes.length === 1 ? boxes[0].register_id : ''));
    }, [cash.data, scope]);
    const refresh = () => Promise.all(['expenses', 'expense-concepts', 'expense-cash', 'expense-summary', 'cash-shifts', 'cash-movements'].map(key => queryClient.invalidateQueries({ queryKey: [key] })));
    const applied = async (result: ExpenseDocument | ExpenseConcept | {
        abandoned: true;
    }) => {
        sessionStorage.removeItem(storageKey);
        attempt.current = null;
        setUncertain(false);
        setError('');
        setEditing(false);
        setCancelOpen(false);
        setForm(empty);
        setConcept(null);
        setConceptForm({ code: '', name: '', description: '' });
        if ('folio' in result)
            setSelected(result);
        await refresh().catch(() => { if (alive.current)
            setError('El registro se guardó. Actualiza la lista para consultar los cambios.'); });
    };
    const send = async (next: Attempt) => {
        if (!navigator.onLine) {
            setError('Necesitas conexión para registrar el gasto.');
            return;
        }
        if (sending.current)
            return;
        sending.current = true;
        attempt.current = next;
        setBusy(true);
        setError('');
        // Recovery metadata only. Draft contents and evidence remain in memory/server.
        try {
            sessionStorage.setItem(storageKey, JSON.stringify({ key: next.key, path: next.path, method: next.method }));
            const result = await fetchApi<ExpenseDocument | ExpenseConcept>(next.path, { method: next.method, headers: { 'Idempotency-Key': next.key }, body: JSON.stringify(next.body) });
            if (alive.current)
                await applied(result);
        }
        catch (cause) {
            if (!alive.current)
                return;
            const definitive = cause instanceof ApiError && cause.status >= 400 && cause.status < 500;
            if (definitive && !uncertain) {
                attempt.current = null;
                sessionStorage.removeItem(storageKey);
            }
            else
                setUncertain(true);
            setError(cause instanceof Error ? cause.message : 'No pudimos verificar el resultado. Recupera la operación.');
        }
        finally {
            sending.current = false;
            if (alive.current)
                setBusy(false);
        }
    };
    const recover = async () => {
        if (attempt.current) {
            await send(attempt.current);
            return;
        }
        setBusy(true);
        try {
            const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null') as {
                key: string;
            } | null;
            if (!saved) {
                setUncertain(false);
                return;
            }
            const result = await fetchApi<ExpenseDocument | ExpenseConcept | {
                abandoned: true;
            }>(`/expense-commands/${encodeURIComponent(saved.key)}`);
            if (alive.current)
                await applied(result);
        }
        catch (cause) {
            if (alive.current)
                setError(cause instanceof Error ? cause.message : 'Recuperación pendiente.');
        }
        finally {
            sending.current = false;
            if (alive.current)
                setBusy(false);
        }
    };
    const resolve = async () => {
        const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null') as {
            key: string;
            path: string;
            method: string;
        } | null;
        if (!saved || busy)
            return;
        const parts = saved.path.split('/').filter(Boolean);
        const kind = `${parts[0] === 'expense-concepts' ? 'concept' : 'document'}.${parts[2] || (parts[1] ? 'edit' : 'create')}`;
        setBusy(true);
        try {
            const result = await fetchApi<ExpenseDocument | ExpenseConcept | {
                abandoned: true;
            }>(`/expense-commands/${encodeURIComponent(saved.key)}/resolve`, { method: 'POST', body: JSON.stringify({ kind, target_id: parts[1] || null, branch_id: branch }) });
            if (alive.current)
                await applied(result);
        }
        catch (cause) {
            if (alive.current)
                setError(cause instanceof Error ? cause.message : 'No fue posible resolver el intento.');
        }
        finally {
            sending.current = false;
            if (alive.current)
                setBusy(false);
        }
    };
    useEffect(() => { if (sessionStorage.getItem(storageKey))
        setUncertain(true); }, [storageKey]);
    const perform = (path: string, body: Record<string, unknown>, method = 'POST') => send({ path, body, method, key: crypto.randomUUID() });
    const save = (event: FormEvent) => {
        event.preventDefault();
        try {
            const body: ExpenseInput = { branch_id: branch, concept_id: form.concept_id, document_date: form.document_date, total_cents: expenseCents(form.amount), tax_cents: form.tax ? expenseCents(form.tax) : null, payment_method: form.payment_method as ExpenseInput['payment_method'], reference: form.reference, notes: form.notes, evidence_refs: form.evidence.trim() ? form.evidence.split('\n').map(s => s.trim()).filter(Boolean) : [] };
            void perform(selected ? `/expenses/${selected.id}` : '/expenses', { ...body, ...(selected ? { version: selected.version } : {}) }, selected ? 'PATCH' : 'POST');
        }
        catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Revisa el importe.');
        }
    };
    const edit = (doc: ExpenseDocument) => { setSelected(doc); setEditing(true); setForm({ concept_id: doc.concept_id, document_date: doc.document_date, amount: (doc.total_cents / 100).toFixed(2), tax: doc.tax_cents === null ? '' : (doc.tax_cents / 100).toFixed(2), payment_method: doc.payment_method, reference: doc.reference, notes: doc.notes, evidence: doc.evidence_refs.join('\n') }); };
    const confirm = () => {
        if (!selected)
            return;
        const box = cash.data?.open_registers.find(b => b.register_id === register);
        if (selected.payment_method === 'cash' && !box) {
            setError('Selecciona una caja con turno abierto.');
            return;
        }
        if (box)
            localStorage.setItem(`expense-register:${scope}`, box.register_id);
        void perform(`/expenses/${selected.id}/confirm`, { branch_id: branch, version: selected.version, ...(selected.payment_method === 'cash' && box ? { register_id: box.register_id, expected_cash_shift_id: box.cash_shift_id } : {}) });
    };
    const blocked = busy || uncertain;
    const readError = concepts.error || documents.error || cash.error || summary.error;
    return <main className="expense-shell">
    <header className="expense-header">
    <div>
    <p className="expense-eyebrow">{session.active_branch.name}</p>
    <h1>{catalog ? 'Conceptos de gasto' : 'Gastos'}</h1>
    <p>{catalog ? 'Organiza los servicios y gastos operativos de tus sucursales.' : 'Registra pagos operativos. Sólo el efectivo genera un retiro de caja.'}</p>
    </div>
    <nav>
    {(catalog ? canReadExpenses : canReadConcepts) && <Link to={catalog ? '/expenses' : '/expense-concepts'}>{catalog ? 'Ver gastos' : 'Conceptos de gasto'}</Link>}{!catalog && canWrite && <button disabled={blocked} onClick={() => { setSelected(null); setForm(empty); setEditing(true); }}>Nuevo gasto</button>}</nav>
    </header>
    {(error || readError) && <p role="alert" className="expense-message">{error || readError?.message}</p>}
    {uncertain && <div role="status" className="expense-message">Hay una operación pendiente de verificar. <button disabled={busy} onClick={() => void recover()}>Recuperar resultado</button>
        <button disabled={busy} onClick={() => void resolve()}>Cerrar intento pendiente</button>
        <p>Si ya se guardó, se recuperará su resultado. Si no se ejecutó, se impedirá un envío tardío.</p>
        </div>}
    {catalog ? <div className="expense-layout">
        <section className="expense-panel">
        <h2>Catálogo</h2>{concepts.isPending && <p>Cargando conceptos…</p>}{concepts.data?.length === 0 && <p>Agrega tu primer concepto, por ejemplo Luz o Renta.</p>}{concepts.data?.map(item => <article className="expense-row" key={item.id}>
            <div>
            <strong>{item.name}</strong>
            <small>{item.code} · {item.status === 'active' ? 'Activo' : 'Archivado'}</small>
            <p>{item.description}</p>
            </div>{canCatalog && item.status === 'active' && <button disabled={blocked} onClick={() => { setConcept(item); setConceptForm({ code: item.code, name: item.name, description: item.description }); }}>Editar</button>}</article>)}</section>
      {canCatalog && <form className="expense-panel" onSubmit={event => { event.preventDefault(); void perform(concept ? `/expense-concepts/${concept.id}` : '/expense-concepts', concept ? { version: concept.version, name: conceptForm.name, description: conceptForm.description } : conceptForm, concept ? 'PATCH' : 'POST'); }}>
            <h2>{concept ? 'Editar concepto' : 'Nuevo concepto'}</h2>
            <fieldset disabled={blocked}>
            <label>Código<input required maxLength={64} disabled={Boolean(concept)} value={conceptForm.code} onChange={e => setConceptForm({ ...conceptForm, code: e.target.value })}/>
            </label>
            <label>Nombre<input required maxLength={160} value={conceptForm.name} onChange={e => setConceptForm({ ...conceptForm, name: e.target.value })}/>
            </label>
            <label>Descripción<textarea maxLength={600} value={conceptForm.description} onChange={e => setConceptForm({ ...conceptForm, description: e.target.value })}/>
            </label>
            <div className="expense-actions">
            <button type="submit">Guardar concepto</button>{concept && <button type="button" onClick={() => void perform(`/expense-concepts/${concept.id}/archive`, { version: concept.version })}>Archivar concepto</button>}<button type="button" onClick={() => { setConcept(null); setConceptForm({ code: '', name: '', description: '' }); }}>Limpiar</button>
            </div>
            </fieldset>
            </form>}</div> : <>
      <section className="expense-panel expense-filters">
        <label>Estado<select aria-label="Estado" value={statusFilter} onChange={e => { setCursor(''); setStatusFilter(e.target.value); }}>
        <option value="">Todos</option>
        <option value="draft">Borrador</option>
        <option value="confirmed">Confirmado</option>
        <option value="cancelled">Anulado</option>
        </select>
        </label>
        <label>Concepto<select aria-label="Concepto" value={conceptFilter} onChange={e => { setCursor(''); setConceptFilter(e.target.value); }}>
        <option value="">Todos</option>{concepts.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        </label>
        <label>Medio de pago<select aria-label="Medio de pago" value={methodFilter} onChange={e => { setCursor(''); setMethodFilter(e.target.value); }}>
        <option value="">Todos</option>{Object.entries(expenseMethods).map(([k, v]) => <option value={k} key={k}>{v}</option>)}</select>
        </label>
        </section>
      <div className="expense-layout">
        <section className="expense-panel">
        <h2>Registros</h2>{documents.isPending && <p>Cargando gastos…</p>}{documents.data?.items.length === 0 && <p>No hay gastos para estos filtros.</p>}{documents.data?.items.map(doc => <button className="expense-row expense-select" disabled={blocked} key={doc.id} onClick={() => { setSelected(doc); setEditing(false); setCancelOpen(false); }}>
            <span>
            <strong>{doc.concept_snapshot.name}</strong>
            <small>{doc.document_date} · {expenseMethods[doc.payment_method]}</small>
            <small>{doc.status === 'draft' ? 'Borrador' : doc.status === 'confirmed' ? 'Confirmado' : 'Anulado'}</small>
            </span>
            <strong>{money(doc.total_cents)}</strong>
            </button>)}<div className="expense-actions">{Boolean(cursor) && <button onClick={() => setCursor('')}>Primera página</button>}{documents.data?.next_cursor != null && <button onClick={() => setCursor(documents.data!.next_cursor!)}>Siguiente</button>}</div>
        </section>
      {editing ? <form className="expense-panel" onSubmit={save}>
            <h2>{selected ? 'Editar borrador' : 'Nuevo gasto'}</h2>
            <fieldset disabled={blocked}>
            <div className="expense-fields">
            <label>Concepto<select aria-label="Concepto" required value={form.concept_id} onChange={e => setForm({ ...form, concept_id: e.target.value })}>
            <option value="">Selecciona un concepto</option>{concepts.data?.filter(c => c.status === 'active').map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
            </label>
            <label>Fecha del comprobante<input type="date" required value={form.document_date} onChange={e => setForm({ ...form, document_date: e.target.value })}/>
            </label>
            <label>Importe total MXN<input inputMode="decimal" required value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })}/>
            </label>
            <label>Impuesto incluido (opcional)<input inputMode="decimal" value={form.tax} onChange={e => setForm({ ...form, tax: e.target.value })}/>
            </label>
            <label>Medio de pago<select aria-label="Medio de pago" required value={form.payment_method} onChange={e => setForm({ ...form, payment_method: e.target.value })}>
            <option value="">Selecciona un medio</option>{Object.entries(expenseMethods).map(([k, v]) => <option value={k} key={k}>{v}</option>)}</select>
            </label>
            <label>Referencia<input maxLength={120} value={form.reference} onChange={e => setForm({ ...form, reference: e.target.value })}/>
            </label>
            </div>
            <label>Referencias de evidencia (una por línea)<textarea value={form.evidence} onChange={e => setForm({ ...form, evidence: e.target.value })}/>
            </label>
            <label>Observaciones<textarea maxLength={600} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}/>
            </label>
            <p className="expense-help">Guardar crea un borrador. Confirmar registra el gasto y, si es efectivo, retira el importe de la caja revisada.</p>
            <div className="expense-actions">
            <button type="submit">Guardar borrador</button>
            <button type="button" onClick={() => setEditing(false)}>Cerrar captura</button>
            </div>
            </fieldset>
            </form> : selected ? <section className="expense-panel">
            <p className="expense-eyebrow">Detalle del gasto</p>
            <h2>{selected.concept_snapshot.name}</h2>
            <p className="expense-total">{money(selected.total_cents)}</p>
            <dl>
            <dt>Sucursal</dt>
            <dd>{session.active_branch.name}</dd>
            <dt>Medio de pago</dt>
            <dd>{expenseMethods[selected.payment_method]}</dd>
            <dt>Fecha</dt>
            <dd>{selected.document_date}</dd>
            <dt>Referencia</dt>
            <dd>{selected.reference || 'Sin referencia'}</dd>
            <dt>Folio</dt>
            <dd>{selected.folio}</dd>
            </dl>{selected.notes && <p>{selected.notes}</p>}{selected.evidence_refs.map((e, i) => <p className="expense-help" key={i}>{e}</p>)}
        {selected.status === 'draft' && selected.payment_method === 'cash' && <>
                <label>Caja<select aria-label="Caja" disabled={blocked || !canWithdraw} value={register} onChange={e => setRegister(e.target.value)}>
                <option value="">Selecciona una caja abierta</option>{cash.data?.open_registers.map(b => <option key={b.cash_shift_id} value={b.register_id}>{b.register_id} · {b.cash_shift_id}</option>)}</select>
                </label>
                <p className="expense-help">{!canWithdraw ? 'Tu cuenta no tiene permiso de retiro.' : cash.data?.open_registers.length === 0 ? 'No hay turnos abiertos. El gasto permanece en borrador.' : `Se retirarán ${money(selected.total_cents)} de la caja seleccionada.`}</p>
                </>}
        <div className="expense-actions">{selected.status === 'draft' && canWrite && <>
                <button disabled={blocked} onClick={() => edit(selected)}>Editar borrador</button>
                <button disabled={blocked || (selected.payment_method === 'cash' && (!register || !canWithdraw))} onClick={confirm}>Confirmar gasto</button>
                </>}{selected.status !== 'cancelled' && (selected.status === 'draft' ? canWrite : canCancel && (selected.payment_method !== 'cash' || canCompensate)) && <button disabled={blocked} onClick={() => { setCancelOpen(true); setReason(''); setReturnEvidence(''); setReturned(false); }}>{selected.status === 'draft' ? 'Descartar borrador' : 'Anular gasto'}</button>}</div>
        {cancelOpen && <form onSubmit={e => { e.preventDefault(); void perform(`/expenses/${selected.id}/cancel`, { branch_id: branch, version: selected.version, reason, ...(selected.status === 'confirmed' && selected.payment_method === 'cash' ? { cash_returned: returned, evidence_refs: returnEvidence.split('\n').filter(Boolean) } : {}) }); }}>
                <fieldset disabled={blocked}>
                <label>Motivo de anulación<textarea required maxLength={600} value={reason} onChange={e => setReason(e.target.value)}/>
                </label>{selected.status === 'confirmed' && selected.payment_method === 'cash' && <>
                    <label className="expense-check">
                    <input type="checkbox" required checked={returned} onChange={e => setReturned(e.target.checked)}/>El efectivo fue devuelto a la caja original</label>
                    <label>Evidencia de devolución<textarea required value={returnEvidence} onChange={e => setReturnEvidence(e.target.value)}/>
                    </label>
                    <p>El turno original debe seguir abierto.</p>
                    </>}<button type="submit">Confirmar anulación</button>
                </fieldset>
                </form>}{selected.status === 'cancelled' && <p>Registro anulado: {selected.cancellation_reason}</p>}</section> : <section className="expense-panel">
            <h2>Revisa un gasto</h2>
            <p>Selecciona un registro para consultar su detalle o crear una nueva captura.</p>
            </section>}</div>
      {canReport && <section className="expense-panel">
            <h2>Estadísticas de gastos</h2>
            <p>Por fecha de confirmación y anulación en la zona de esta sucursal. Incluye todos los medios.</p>
            <div className="expense-fields">
            <label>Desde<input type="date" value={from} onChange={e => setFrom(e.target.value)}/>
            </label>
            <label>Hasta<input type="date" value={to} onChange={e => setTo(e.target.value)}/>
            </label>
            </div>{summary.data && <>
                <div className="expense-metrics">{[['Confirmados', summary.data.confirmed_cents], ['Anulaciones', summary.data.reversed_cents], ['Neto', summary.data.net_cents], ['Efectivo neto', summary.data.cash_cents], ['Otros medios', summary.data.other_cents]].map(([label, total]) => <div key={label}>
                    <small>{label}</small>
                    <strong>{money(Number(total))}</strong>
                    </div>)}</div>{summary.data.groups.map((g, i) => <div className="expense-row" key={i}>
                    <span>{g.concept_name} · {expenseMethods[g.payment_method]}</span>
                    <strong>{money(g.net_cents)}</strong>
                    </div>)}</>}</section>}
    </>}
  </main>;
}
