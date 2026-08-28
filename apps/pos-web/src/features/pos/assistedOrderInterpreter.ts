export type AssistedInstruction = {
  id: string;
  name: string;
  kind?: 'comment' | 'modifier';
  priceDeltaCents?: number;
};
export type AssistedCatalogProduct = {
  id: string;
  name: string;
  active: boolean;
  available: boolean;
  instructions?: AssistedInstruction[];
};
export type AssistedDraftLine = {
  productId?: string;
  quantity: number;
  instructionId?: string;
  instructionName?: string;
  instructionKind?: 'comment' | 'modifier';
  instructionPriceDeltaCents?: number;
  requiresPersonalization?: boolean;
  status: 'resolved' | 'ambiguous' | 'not-found';
  message: string;
};
export type AssistedOrderDraft = {
  customerName: string;
  phone: string;
  orderType?: 'takeout' | 'delivery';
  lines: AssistedDraftLine[];
};

const normalize = (value: string) => value
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase('es-MX').replace(/[^a-z0-9]+/g, ' ').trim();

const normalizedPhone = (value: string) => {
  const digits = value.replace(/\D/g, '');
  if (digits.length === 10) return digits;
  if (digits.length === 12 && digits.startsWith('52')) return digits;
  return '';
};

function findQuantity(text: string): number {
  const match = text.match(/\b(\d+|un|una|dos|tres|cuatro|cinco)\b/);
  const words: Record<string, number> = { un: 1, una: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5 };
  if (!match) return 1;
  return Math.max(1, Math.min(99, words[match[1]] || Number(match[1]) || 1));
}

export function interpretAssistedOrder(text: string, catalog: AssistedCatalogProduct[]): AssistedOrderDraft {
  const normalized = normalize(text);
  const phoneMatch = text.match(/(?:telefono|tel[eé]fono)?\s*(?:\+?52[\s-]?)?(\d[\d\s-]{8,}\d)/i);
  const nameMatch = text.match(/\bpara\s+(.+?)(?=\s+(?:con\s+)?tel[eé]fono\b|,|$)/i);
  const orderType = /\b(?:para recoger|para llevar)\b/.test(normalized)
    ? 'takeout'
    : /\ba domicilio\b/.test(normalized) ? 'delivery' : undefined;
  const available = catalog.filter((product) => product.active && product.available);
  const withoutPhone = normalized.replace(/\b(?:telefono)?\s*(?:52)?\s*\d[\d\s]*/g, '');
  const matches = available.filter((product) => normalize(product.name).split(' ').every((word) => withoutPhone.includes(word)));
  const quantity = findQuantity(withoutPhone);

  if (matches.length !== 1) {
    return {
      customerName: nameMatch?.[1]?.trim() || '', phone: normalizedPhone(phoneMatch?.[0] || ''), orderType,
      lines: [{ quantity, status: matches.length > 1 ? 'ambiguous' : 'not-found', message: matches.length > 1 ? 'El producto es ambiguo; elige una opción del catálogo.' : 'No se encontró un producto disponible en el catálogo.' }],
    };
  }

  const product = matches[0];
  const mentionedInstructions = (product.instructions || []).filter((instruction) => normalized.includes(normalize(instruction.name)));
  const productWordsRemoved = withoutPhone.replace(new RegExp(normalize(product.name).split(' ').join('\\s+(?:de\\s+)?'), 'g'), '');
  const hasInstructionCue = /\b(?:sin|extra)\s+|\bcon\s+(?!telefono\b)/.test(productWordsRemoved.replace(/\bpara\s+[^,]+/g, ''));
  if (mentionedInstructions.length !== 1 && hasInstructionCue) {
    return {
      customerName: nameMatch?.[1]?.trim() || '', phone: normalizedPhone(phoneMatch?.[0] || ''), orderType,
      lines: [{ productId: product.id, quantity, status: 'not-found', message: 'La instrucción no está configurada; personalízala en el flujo canónico.' }],
    };
  }

  return {
    customerName: nameMatch?.[1]?.trim() || '', phone: normalizedPhone(phoneMatch?.[0] || ''), orderType,
    lines: [{
      productId: product.id,
      quantity,
      instructionId: mentionedInstructions[0]?.id,
      instructionName: mentionedInstructions[0]?.name,
      instructionKind: mentionedInstructions[0]?.kind,
      instructionPriceDeltaCents: mentionedInstructions[0]?.priceDeltaCents,
      status: 'resolved',
      message: '',
    }],
  };
}
