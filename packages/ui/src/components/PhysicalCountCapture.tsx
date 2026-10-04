import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, LockKeyhole, PackageCheck, Save, Search } from 'lucide-react';
import { Button } from './Button';
import { Input } from './Input';

export interface PhysicalCountPresentation {
  id: string;
  code: string;
  name: string;
  commercial_unit_code: string;
  base_unit_yield: number;
}

export interface PhysicalCountEntry {
  presentation_id?: string | null;
  presentation_name_snapshot?: string | null;
  commercial_unit_code_snapshot?: string | null;
  base_unit_yield_snapshot: number;
  quantity: number;
  converted_quantity: number;
}

export interface PhysicalCountLine {
  id: string;
  item_name: string;
  item_sku: string;
  category_name?: string | null;
  unit_code: string;
  counted_quantity?: number | null;
  capture_version: number;
  presentations: PhysicalCountPresentation[];
  entries: PhysicalCountEntry[];
}

export interface PhysicalCountCaptureSession {
  id: string;
  folio: string;
  status: string;
  lines: PhysicalCountLine[];
}

export interface PhysicalCountLineCapture {
  line_id: string;
  expected_version: number;
  entries: Array<{ presentation_id: string | null; quantity: string }>;
}

interface PhysicalCountCaptureProps {
  session: PhysicalCountCaptureSession;
  busy?: boolean;
  onSave: (capture: PhysicalCountLineCapture) => Promise<PhysicalCountCaptureSession>;
  onSubmit: () => Promise<void>;
}

const entryKey = (presentationId?: string | null) => presentationId || 'base';

export function PhysicalCountCapture({
  session,
  busy = false,
  onSave,
  onSubmit,
}: PhysicalCountCaptureProps) {
  const [search, setSearch] = useState('');
  const [selectedLineId, setSelectedLineId] = useState(
    session.lines.find((line) => line.counted_quantity === null || line.counted_quantity === undefined)?.id
      || session.lines[0]?.id
      || '',
  );
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');

  const selectedLine = session.lines.find((line) => line.id === selectedLineId) || session.lines[0];
  const completed = session.lines.filter(
    (line) => line.counted_quantity !== null && line.counted_quantity !== undefined,
  ).length;
  const filteredLines = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('es-MX');
    if (!term) return session.lines;
    return session.lines.filter((line) =>
      `${line.item_name} ${line.item_sku} ${line.category_name || ''}`
        .toLocaleLowerCase('es-MX')
        .includes(term),
    );
  }, [search, session.lines]);

  useEffect(() => {
    if (!selectedLine) {
      setQuantities({});
      return;
    }
    setQuantities(
      Object.fromEntries(
        selectedLine.entries.map((entry) => [
          entryKey(entry.presentation_id),
          String(entry.quantity),
        ]),
      ),
    );
    setMessage('');
  }, [selectedLine?.id, selectedLine?.capture_version]);

  const updateQuantity = (key: string, value: string) => {
    setQuantities((current) => ({ ...current, [key]: value }));
  };

  const saveSelected = async (advance: boolean) => {
    if (!selectedLine) return;
    const entries = [
      ...selectedLine.presentations.map((presentation) => ({
        presentation_id: presentation.id,
        quantity: quantities[entryKey(presentation.id)] || '',
      })),
      { presentation_id: null, quantity: quantities.base || '' },
    ].filter((entry) => entry.quantity !== '');
    if (entries.length === 0) {
      setMessage('Captura al menos una cantidad. Usa 0 cuando no exista físicamente.');
      return;
    }
    try {
      const updated = await onSave({
        line_id: selectedLine.id,
        expected_version: selectedLine.capture_version,
        entries,
      });
      setMessage('Captura guardada en el servidor.');
      if (advance) {
        const currentIndex = updated.lines.findIndex((line) => line.id === selectedLine.id);
        const next = [
          ...updated.lines.slice(currentIndex + 1),
          ...updated.lines.slice(0, currentIndex),
        ].find((line) => line.counted_quantity === null || line.counted_quantity === undefined);
        if (next) setSelectedLineId(next.id);
      }
    } catch {
      setMessage('No se confirmó el guardado. Conservamos los valores para que puedas reintentar.');
    }
  };

  const allCaptured = completed === session.lines.length && session.lines.length > 0;

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          gap: 12,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <strong style={{ color: '#0f172a' }}>{session.folio}</strong>
          <div style={{ color: '#64748b', fontSize: 13, marginTop: 3 }}>
            {completed} de {session.lines.length} insumos capturados
          </div>
        </div>
        <div
          aria-label={`${completed} de ${session.lines.length} insumos capturados`}
          style={{ width: 220, height: 9, borderRadius: 999, background: '#e2e8f0', overflow: 'hidden' }}
        >
          <div
            style={{
              width: `${session.lines.length ? (completed / session.lines.length) * 100 : 0}%`,
              height: '100%',
              background: '#22c55e',
              transition: 'width 180ms ease',
            }}
          />
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          border: '1px solid #cbd5e1',
          borderRadius: 10,
          padding: '0 12px',
          background: '#fff',
        }}
      >
        <Search size={17} color="#64748b" aria-hidden="true" />
        <input
          aria-label="Buscar insumo por nombre, clave o grupo"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar insumo, clave o grupo…"
          style={{ border: 0, outline: 0, minHeight: 42, flex: 1, font: 'inherit' }}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        <div style={{ display: 'grid', gap: 8, maxHeight: 430, overflowY: 'auto', alignContent: 'start' }}>
          {filteredLines.map((line) => {
            const done = line.counted_quantity !== null && line.counted_quantity !== undefined;
            const selected = line.id === selectedLine?.id;
            return (
              <button
                key={line.id}
                type="button"
                onClick={() => setSelectedLineId(line.id)}
                style={{
                  border: `1px solid ${selected ? '#22c55e' : '#e2e8f0'}`,
                  background: selected ? '#f0fdf4' : '#fff',
                  borderRadius: 10,
                  padding: 12,
                  textAlign: 'left',
                  minHeight: 62,
                  cursor: 'pointer',
                }}
              >
                <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong style={{ color: '#0f172a' }}>{line.item_name}</strong>
                  {done && <CheckCircle2 size={17} color="#16a34a" aria-label="Capturado" />}
                </span>
                <small style={{ color: '#64748b' }}>
                  {line.item_sku} · {line.category_name || 'Sin grupo'}
                </small>
              </button>
            );
          })}
        </div>

        {selectedLine && (
          <section
            aria-labelledby="physical-count-selected-item"
            style={{ border: '1px solid #e2e8f0', borderRadius: 12, padding: 16, background: '#f8fafc' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
              <div>
                <h3 id="physical-count-selected-item" style={{ margin: 0, color: '#0f172a' }}>
                  {selectedLine.item_name}
                </h3>
                <small style={{ color: '#64748b' }}>{selectedLine.item_sku}</small>
              </div>
              <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center', color: '#475569', fontSize: 12 }}>
                <LockKeyhole size={14} /> Captura ciega
              </span>
            </div>

            <div style={{ display: 'grid', gap: 10 }}>
              {selectedLine.presentations.map((presentation) => (
                <label
                  key={presentation.id}
                  style={{ display: 'grid', gridTemplateColumns: '1fr minmax(110px, 150px)', gap: 12, alignItems: 'center' }}
                >
                  <span>
                    <strong style={{ display: 'block', color: '#334155', fontSize: 14 }}>{presentation.name}</strong>
                    <small style={{ color: '#64748b' }}>
                      1 {presentation.commercial_unit_code} = {presentation.base_unit_yield} {selectedLine.unit_code}
                    </small>
                  </span>
                  <Input
                    aria-label={`Cantidad de ${presentation.name}`}
                    type="number"
                    min={0}
                    step="any"
                    inputMode="decimal"
                    value={quantities[entryKey(presentation.id)] || ''}
                    onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                      updateQuantity(entryKey(presentation.id), event.target.value)
                    }
                    placeholder={presentation.commercial_unit_code}
                  />
                </label>
              ))}
              <label style={{ display: 'grid', gridTemplateColumns: '1fr minmax(110px, 150px)', gap: 12, alignItems: 'center' }}>
                <span>
                  <strong style={{ display: 'block', color: '#334155', fontSize: 14 }}>Cantidad suelta</strong>
                  <small style={{ color: '#64748b' }}>Unidad base: {selectedLine.unit_code}</small>
                </span>
                <Input
                  aria-label={`Cantidad suelta en ${selectedLine.unit_code}`}
                  type="number"
                  min={0}
                  step="any"
                  inputMode="decimal"
                  value={quantities.base || ''}
                  onChange={(event: React.ChangeEvent<HTMLInputElement>) => updateQuantity('base', event.target.value)}
                  placeholder={selectedLine.unit_code}
                />
              </label>
            </div>

            {selectedLine.counted_quantity !== null && selectedLine.counted_quantity !== undefined && (
              <div style={{ marginTop: 14, padding: 10, borderRadius: 9, background: '#ecfdf5', color: '#166534' }}>
                Total guardado: <strong>{selectedLine.counted_quantity} {selectedLine.unit_code}</strong>
              </div>
            )}

            {message && <p role="status" style={{ margin: '12px 0 0', color: '#475569', fontSize: 13 }}>{message}</p>}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
              <Button variant="secondary" disabled={busy} onClick={() => void saveSelected(false)}>
                <Save size={15} /> Guardar
              </Button>
              <Button variant="primary" disabled={busy} onClick={() => void saveSelected(true)}>
                Guardar y siguiente <ArrowRight size={15} />
              </Button>
            </div>
          </section>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <small style={{ color: '#64748b' }}>
          <PackageCheck size={14} style={{ verticalAlign: 'text-bottom', marginRight: 5 }} />
          El envío requiere conexión y todas las líneas guardadas.
        </small>
        <Button
          variant="primary"
          disabled={!allCaptured || busy}
          onClick={() => void onSubmit().catch(() => setMessage('No se confirmó el envío. Revisa la conexión y vuelve a intentar.'))}
        >
          Enviar a revisión
        </Button>
      </div>
    </div>
  );
}
