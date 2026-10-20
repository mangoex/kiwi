export interface CustomerAddress {
  creation_key?: string;
  id: string;
  alias: string;
  street: string;
  exterior_number: string;
  interior_number: string | null;
  neighborhood: string;
  postal_code: string;
  city: string;
  municipality: string;
  state: string;
  references: string | null;
  is_default: boolean;
}

export interface CustomerProfile {
  saved_address_id?: string | null;
  id: string | null;
  name: string | null;
  phone: string;
  email: string | null;
  birthday_day: number | null;
  birthday_month: number | null;
  birthday_year: number | null;
  addresses: CustomerAddress[];
  complete: boolean;
}

export class CustomerAccessError extends Error {
  constructor(public readonly status: number, public readonly code: string) {
    super(code);
  }
}

export async function customerRequest<T>(publicKey: string, route: string, body?: unknown, method = 'POST'): Promise<T> {
  const response = await fetch(`/api/v1/mobile/branches/${encodeURIComponent(publicKey)}/${route}`, {
    method, credentials: 'same-origin', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', 'X-Mobile-Request': '1' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    let code = 'mobile_request_failed';
    try { code = (await response.json()).detail?.code || code; } catch { /* Generic error. */ }
    throw new CustomerAccessError(response.status, code);
  }
  return response.json() as Promise<T>;
}

export function accessErrorMessage(error: unknown): string {
  if (error instanceof CustomerAccessError) {
    if (error.status === 401) return 'Tu sesión o código venció. Verifica tu teléfono de nuevo.';
    if (error.status === 429) return 'Espera un momento antes de solicitar otro código.';
    if (error.code === 'mobile_customer_ambiguous' || error.code === 'mobile_phone_in_use') {
      return 'Este teléfono necesita revisión. Comunícate con la sucursal para actualizar tu registro.';
    }
    if (error.status === 503) return 'El acceso no está disponible por ahora. Intenta más tarde.';
    if (error.code === 'invalid_birthday') return 'Revisa tu cumpleaños: la fecha debe ser válida y el año es opcional.';
    if (error.status === 422) return 'Revisa los datos. Completa los campos obligatorios con valores válidos.';
  }
  return 'No pudimos guardar los cambios. Conservamos tus datos para que reintentes.';
}
