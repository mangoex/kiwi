// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-mobile-password-autocomplete-v1
// Repository policy exception: autocomplete HTML values are public constants, not credentials.
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
    <label>Teléfono<input value={profile.phone} readOnly /></label>
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
  const [register, setRegister] = useState(false);
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError('');
    if (register && password !== confirmation) { setError('Las contraseñas no coinciden.'); return; }
    setBusy(true);
    try {
      const data = await customerRequest<CustomerProfile>(publicKey, register ? 'access/register' : 'access/login', { phone, password });
      setPassword(''); setConfirmation(''); onSaved(data);
    } catch (err) { setError(accessErrorMessage(err)); }
    finally { setBusy(false); }
  };
  return <main className="customer-access"><div className="customer-access-card">
    <span className="customer-brand">🥝 Kiwi</span>
    {profile ? <ProfileEditor publicKey={publicKey} profile={profile} onSaved={onSaved} onSessionExpired={onSessionExpired} /> : <form className="customer-profile-form" onSubmit={submit}>
      <h1>Bienvenido a Kiwi</h1><p>{register ? 'Crea tu cuenta para conocer el menú y hacer pedidos.' : 'Entra con tu teléfono y contraseña para continuar.'}</p>
      <label>Tu teléfono<input type="tel" autoComplete="username" inputMode="tel" pattern="(?:\+?52)?[0-9]{10}" maxLength={13} required value={phone} placeholder="10 dígitos" onChange={e => setPhone(e.target.value)} /></label>
      <label>Contraseña<input type={showPassword ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 15 : 1} maxLength={128} required value={password} onChange={e => setPassword(e.target.value)} /></label>
      {register && <><p>Usa al menos 15 caracteres. Puedes escribir una frase fácil de recordar.</p>
        <label>Confirmar contraseña<input type={showPassword ? 'text' : 'password'} autoComplete="new-password" minLength={15} maxLength={128} required value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label></>}
      <label className="customer-check"><input type="checkbox" checked={showPassword} onChange={e => setShowPassword(e.target.checked)} />Mostrar contraseña</label>
      {error && <p className="customer-error" role="alert">{error}</p>}
      <button className="customer-primary" disabled={busy}>{busy ? 'Espera…' : register ? 'Crear mi cuenta' : 'Entrar'}</button>
      <button type="button" disabled={busy} onClick={() => { setRegister(!register); setPassword(''); setConfirmation(''); setError(''); }}>{register ? 'Ya tengo cuenta' : 'Crear cuenta'}</button>
    </form>}
  </div></main>;
}

interface SecurityProps {
  publicKey: string;
  onSaved: (profile: CustomerProfile) => void;
  onSessionExpired?: () => void;
}

function expiredSession(error: unknown, onSessionExpired?: () => void) {
  if (error instanceof CustomerAccessError && error.code === 'mobile_session_required') onSessionExpired?.();
}

export function PasswordChange({ publicKey, hasPassword, onSaved, onSessionExpired }: SecurityProps & { hasPassword: boolean }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  return <form className="customer-profile-form" onSubmit={async event => {
    event.preventDefault(); setError(''); setSaved(false);
    if (newPassword !== confirmation) { setError('Las contraseñas no coinciden.'); return; }
    setBusy(true);
    try {
      const result = await customerRequest<CustomerProfile>(publicKey, 'profile/password', { current_password: currentPassword, new_password: newPassword }, 'PUT');
      setCurrentPassword(''); setNewPassword(''); setConfirmation(''); setSaved(true); onSaved(result);
    } catch (err) { setError(accessErrorMessage(err)); expiredSession(err, onSessionExpired); }
    finally { setBusy(false); }
  }}>
    <h3>{hasPassword ? 'Cambiar contraseña' : 'Crear contraseña'}</h3>
    {!hasPassword && <p>Crea una contraseña para volver a entrar con tu teléfono.</p>}
    {hasPassword && <label>Contraseña actual<input type="password" autoComplete="current-password" required maxLength={128} value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label>}
    <label>Nueva contraseña<input type="password" autoComplete="new-password" required minLength={15} maxLength={128} value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label>
    <p>Usa al menos 15 caracteres, por ejemplo una frase fácil de recordar.</p>
    <label>Confirmar nueva contraseña<input type="password" autoComplete="new-password" required minLength={15} maxLength={128} value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label>
    {error && <p role="alert" className="customer-error">{error}</p>}
    {saved && <p role="status">Contraseña guardada. Cerramos tus otras sesiones.</p>}
    <button className="customer-primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar contraseña'}</button>
  </form>;
}

export function PhoneChange({ publicKey, onSaved, onSessionExpired }: SecurityProps) {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  return <form className="customer-profile-form" onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError(''); setSaved(false);
    try {
      const result = await customerRequest<CustomerProfile>(publicKey, 'profile/phone', { phone, current_password: password }, 'PUT');
      onSaved(result); setPhone(''); setPassword(''); setSaved(true);
    } catch (err) { setError(accessErrorMessage(err)); expiredSession(err, onSessionExpired); }
    finally { setBusy(false); }
  }}>
    <h3>Cambiar teléfono</h3>
    <label>Nuevo teléfono<input type="tel" autoComplete="tel-national" inputMode="tel" pattern="(?:\+?52)?[0-9]{10}" maxLength={13} required value={phone} onChange={e => setPhone(e.target.value)} /></label>
    <label>Confirma tu contraseña<input type="password" autoComplete="current-password" maxLength={128} required value={password} onChange={e => setPassword(e.target.value)} /></label>
    {error && <p role="alert" className="customer-error">{error}</p>}
    {saved && <p role="status">Teléfono actualizado. Úsalo para tu próximo inicio de sesión.</p>}
    <button type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar nuevo teléfono'}</button>
  </form>;
}
