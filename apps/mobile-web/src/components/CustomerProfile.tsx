import React, { useState } from 'react';
import { CustomerProfile, CustomerAddress, CustomerAccessError, customerRequest, accessErrorMessage } from '../customerProfile';
import './CustomerProfile.css';

interface EditorProps {
  publicKey: string;
  profile: CustomerProfile;
  onSaved: (profile: CustomerProfile) => void;
  onSessionExpired?: () => void;
}

const emptyAddress = {
  alias: 'Casa', street: '', exterior_number: '', interior_number: '', neighborhood: '',
  postal_code: '', city: '', municipality: '', state: '', references: '', is_default: true,
};

export function ProfileEditor({ publicKey, profile, onSaved, onSessionExpired }: EditorProps) {
  const [name, setName] = useState(profile.name || '');
  const [day, setDay] = useState(String(profile.birthday_day || ''));
  const [month, setMonth] = useState(String(profile.birthday_month || ''));
  const [year, setYear] = useState(String(profile.birthday_year || ''));
  const [email, setEmail] = useState(profile.email || '');
  const [address, setAddress] = useState<Partial<CustomerAddress>>(() => profile.addresses[0] || { ...emptyAddress, creation_key: crypto.randomUUID() });
  const [withAddress, setWithAddress] = useState(profile.addresses.length > 0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      const saved = await customerRequest<CustomerProfile>(publicKey, 'profile', {
        name: name.trim(), birthday_day: Number(day), birthday_month: Number(month),
        birthday_year: year ? Number(year) : null, email: email.trim() || null,
        ...(withAddress ? { address } : {}),
      }, 'PUT');
      if (saved.saved_address_id) {
        setAddress(saved.addresses.find(a => a.id === saved.saved_address_id) || address);
      }
      onSaved(saved);
    } catch (err) {
      setError(accessErrorMessage(err));
      if (err instanceof CustomerAccessError && err.status === 401) onSessionExpired?.();
    }
    finally { setBusy(false); }
  };

  return <form className="customer-profile-form" onSubmit={save}>
    <h2>{profile.complete ? 'Mi perfil' : 'Cuéntanos de ti'}</h2>
    <p>Tu nombre, teléfono y cumpleaños nos ayudan a atenderte mejor.</p>
    <label>Nombre completo<input autoComplete="name" value={name} maxLength={160} required onChange={e => setName(e.target.value)} /></label>
    <label>Teléfono verificado<input value={profile.phone} readOnly /></label>
    <fieldset><legend>Cumpleaños</legend><div className="customer-birthday-fields">
      <label>Día<input type="number" inputMode="numeric" min={1} max={31} required value={day} onChange={e => setDay(e.target.value)} /></label>
      <label>Mes<select aria-label="Mes" required value={month} onChange={e => setMonth(e.target.value)}>
        <option value="">Selecciona</option>
        {['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'].map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
      </select></label>
      <label>Año (opcional)<input type="number" inputMode="numeric" min={1900} max={new Date().getFullYear()} value={year} onChange={e => setYear(e.target.value)} /></label>
    </div></fieldset>
    <label>Correo electrónico <small>(obligatorio para delivery)</small><input type="email" autoComplete="email" maxLength={180} value={email} onChange={e => setEmail(e.target.value)} /></label>
    <label className="customer-check"><input type="checkbox" checked={withAddress} onChange={e => setWithAddress(e.target.checked)} />Completar domicilio de entrega</label>
    {withAddress && <fieldset><legend>Domicilio</legend>
      {profile.addresses.length > 0 && <label>Domicilio a editar<select aria-label="Domicilio a editar" value={address.id || ''} onChange={e => setAddress(profile.addresses.find(a => a.id === e.target.value) || { ...emptyAddress, creation_key: crypto.randomUUID() })}>
        <option value="">Agregar otro domicilio</option>
        {profile.addresses.map(a => <option value={a.id} key={a.id}>{a.alias}: {a.street} {a.exterior_number}</option>)}
      </select></label>}
      {([
        ['alias', 'Alias (Casa, Oficina…)'], ['street', 'Calle'], ['exterior_number', 'Número exterior'],
        ['interior_number', 'Número interior (opcional)'], ['neighborhood', 'Colonia'],
        ['postal_code', 'Código postal'], ['city', 'Ciudad'], ['municipality', 'Municipio'],
        ['state', 'Estado'], ['references', 'Referencias (opcional)'],
      ] as const).map(([field, label]) => <label key={field}>{label}<input
        value={String(address[field] || '')} required={!['interior_number', 'references'].includes(field)}
        maxLength={field === 'postal_code' ? 5 : field.includes('number') ? 32 : field === 'references' ? 600 : field === 'street' ? 180 : field === 'alias' ? 60 : 100}
        pattern={field === 'postal_code' ? '[0-9]{5}' : undefined}
        autoComplete={field === 'street' ? 'address-line1' : field === 'postal_code' ? 'postal-code' : undefined}
        onChange={e => setAddress({ ...address, [field]: e.target.value })} /></label>)}
      <label className="customer-check"><input type="checkbox" checked={address.is_default ?? true} onChange={e => setAddress({ ...address, is_default: e.target.checked })} />Usar como predeterminado</label>
    </fieldset>}
    {error && <p className="customer-error" role="alert">{error}</p>}
    <button className="customer-primary" type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar mis datos'}</button>
  </form>;
}

export function CustomerAccess({ publicKey, profile, onSaved, onSessionExpired }: {
  publicKey: string; profile: CustomerProfile | null; onSaved: (profile: CustomerProfile) => void;
  onSessionExpired?: () => void;
}) {
  const [phone, setPhone] = useState('');
  const [challenge, setChallenge] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      if (!challenge) {
        const data = await customerRequest<{ challenge: string }>(publicKey, 'access/start', { phone });
        setChallenge(data.challenge);
      } else {
        const data = await customerRequest<CustomerProfile>(publicKey, 'access/verify', { challenge, code });
        onSaved(data);
      }
    } catch (err) { setError(accessErrorMessage(err)); }
    finally { setBusy(false); }
  };
  return <main className="customer-access"><div className="customer-access-card">
    <span className="customer-brand">🥝 Kiwi</span>
    {profile ? <ProfileEditor publicKey={publicKey} profile={profile} onSaved={onSaved} onSessionExpired={onSessionExpired} /> : <form className="customer-profile-form" onSubmit={submit}>
      <h1>Bienvenido a Kiwi</h1><p>Regístrate o inicia sesión para conocer nuestro menú y hacer tu pedido.</p>
      {!challenge ? <label>Tu teléfono<input type="tel" autoComplete="tel-national" inputMode="tel" pattern="(?:\+?52)?[0-9]{10}" maxLength={13} required value={phone} placeholder="10 dígitos" onChange={e => setPhone(e.target.value)} /></label>
        : <><p>Enviamos un código al {phone}. Ingresa el código para continuar.</p><label>Código de verificación<input autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{4,10}" maxLength={10} required value={code} onChange={e => setCode(e.target.value)} /></label></>}
      {error && <p className="customer-error" role="alert">{error}</p>}
      <button className="customer-primary" disabled={busy}>{busy ? 'Espera…' : challenge ? 'Verificar y continuar' : 'Recibir código'}</button>
      {challenge && <button type="button" disabled={busy} onClick={() => { setChallenge(''); setCode(''); setError(''); }}>Solicitar otro código o cambiar teléfono</button>}
    </form>}
  </div></main>;
}

export function PhoneChange({ publicKey, onSaved, onSessionExpired }: { publicKey: string; onSaved: (profile: CustomerProfile) => void; onSessionExpired?: () => void }) {
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [challenge, setChallenge] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  return <form className="customer-profile-form" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError('');
    try {
      if (!challenge) {
        setChallenge((await customerRequest<{ challenge: string }>(publicKey, 'profile/phone/start', { phone })).challenge);
      } else {
        const saved = await customerRequest<CustomerProfile>(publicKey, 'access/verify', { challenge, code });
        onSaved(saved);
        setChallenge(''); setPhone(''); setCode('');
      }
    } catch (err) {
      setError(accessErrorMessage(err));
      if (err instanceof CustomerAccessError && err.status === 401) onSessionExpired?.();
    } finally { setBusy(false); }
  }}>
    <h3>Cambiar teléfono</h3>
    <label>Nuevo teléfono<input type="tel" inputMode="tel" required disabled={Boolean(challenge)} value={phone} onChange={e => setPhone(e.target.value)} /></label>
    {challenge && <label>Código al nuevo teléfono<input inputMode="numeric" autoComplete="one-time-code" required value={code} onChange={e => setCode(e.target.value)} /></label>}
    {error && <p role="alert" className="customer-error">{error}</p>}
    <button type="submit" disabled={busy}>{busy ? 'Espera…' : challenge ? 'Confirmar nuevo teléfono' : 'Verificar nuevo teléfono'}</button>
    {challenge && <button type="button" onClick={() => { setChallenge(''); setCode(''); }}>Cambiar número o reenviar</button>}
  </form>;
}
