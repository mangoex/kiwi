import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Modal } from '@restaurantos/ui';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { ShoppingBag, Search, Plus, Minus, Coffee, CupSoda, Sandwich, Salad, Wheat, Package, Utensils, Users, X, Check, Banknote, CreditCard, Landmark, Trash2 } from 'lucide-react';
import { usePosSession } from '../../session';
import { cartLineTotalCents, cartSubtotalCents, formatMxnCents } from './cartMoney';

const getProductIcon = (category: string, size: number = 40) => {
  const cat = (category || '').toLowerCase();
  if (cat.includes('café') || cat.includes('matcha')) return <Coffee size={size} strokeWidth={1.5} />;
  if (cat.includes('jugo') || cat.includes('agua') || cat.includes('bebida') || cat.includes('smoothie') || cat.includes('extracto') || cat.includes('drink')) return <CupSoda size={size} strokeWidth={1.5} />;
  if (cat.includes('ensalada')) return <Salad size={size} strokeWidth={1.5} />;
  if (cat.includes('panadería') || cat.includes('pan') || cat.includes('dessert')) return <Wheat size={size} strokeWidth={1.5} />;
  if (cat.includes('emparedado') || cat.includes('sando') || cat.includes('burger')) return <Sandwich size={size} strokeWidth={1.5} />;
  if (cat.includes('combo')) return <Package size={size} strokeWidth={1.5} />;
  return <Utensils size={size} strokeWidth={1.5} />;
};

interface Product {
  id: string;
  name: string;
  sku: string;
  category: string;
  price_cents: number;
  description: string;
  station: string;
  image_url?: string;
}

interface CartItem extends Product {
  lineId: string;
  quantity: number;
  modifiers: SelectedModifier[];
  commentPresets: SelectedOrderComment[];
  ingredientExtras: SelectedIngredientExtra[];
  modifierPriceCents: number;
}

interface IngredientExtra { extra_id: string; id?: string; name: string; portion_quantity: string; sale_price_cents: number; station: 'kitchen' | 'drinks' | 'packing'; unit_code?: string; }
interface SelectedIngredientExtra extends IngredientExtra { portions: number; }
interface SelectedOrderComment { id: string; text: string; }
interface ModifierOption { id: string; name: string; effect_type: string; price_delta_cents: number; kitchen_text: string; variation_kind?: 'ingredient_extra' | 'order_comment'; variation_id?: string; action?: 'add'; }
interface ModifierGroup { id: string; name: string; minimum_selections: number; maximum_selections: number; options: ModifierOption[]; }
interface SelectedModifier { option_id: string; option_name: string; price_delta_cents: number; text?: string; }
interface EditableOrderLine {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price_cents: number;
  station: string;
  selected_modifiers: Array<Record<string, any>>;
}
interface EditableOrder {
  id: string;
  folio: string;
  version: number;
  owner_name?: string;
  order_type: string;
  payment_method_intent?: PaymentMethod | null;
  editable: boolean;
  edit_block_reason?: string | null;
  lines: EditableOrderLine[];
}

export function shouldAddProductWithoutModifiers(groups: ModifierGroup[]): boolean {
  return groups.length === 0;
}

export function toggleIngredientVariationSelection(selected: string[], options: ModifierOption[], optionId: string): string[] {
  if (selected.includes(optionId)) return selected.filter((id) => id !== optionId);
  const option = options.find((item) => item.id === optionId);
  if (!option?.variation_id) return [...selected, optionId];
  return [...selected.filter((id) => options.find((item) => item.id === id)?.variation_id !== option.variation_id), optionId];
}

interface PosCustomerAddress {
  id: string;
  alias: string;
  street: string;
  exterior_number: string;
  interior_number?: string | null;
  neighborhood: string;
  postal_code?: string;
  city?: string;
  municipality?: string;
  state?: string;
  is_default: boolean;
  status: string;
}

interface PosCustomer {
  id: string;
  name: string;
  addresses: PosCustomerAddress[];
  legacy_address_reference?: string | null;
  phones?: { captured_number?: string; normalized_number?: string }[];
}

interface PosCustomerPage {
  items: PosCustomer[];
  total: number;
}

type CustomerLookupStatus = 'idle' | 'searching' | 'found' | 'not-found' | 'error';

const ORDER_TYPES = [
  { value: 'dine-in', label: 'En sucursal' },
  { value: 'takeout', label: 'Para llevar' },
  { value: 'delivery', label: 'A domicilio' },
] as const;

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Efectivo', description: 'Pago en caja', icon: Banknote },
  { value: 'debit_card', label: 'Débito', description: 'Tarjeta de débito', icon: CreditCard },
  { value: 'credit_card', label: 'Crédito', description: 'Tarjeta de crédito', icon: CreditCard },
  { value: 'transfer', label: 'Transferencia', description: 'Transferencia bancaria', icon: Landmark },
] as const;

type PaymentMethod = typeof PAYMENT_METHODS[number]['value'];

function validMexicanPhone(value: string): string {
  const digits = value.replace(/\D/g, '');
  if (digits.length === 10) return digits;
  if (digits.length === 12 && digits.startsWith('52')) return digits;
  return '';
}

const orderErrorMessage = (code?: string, message?: string) => {
  if (code === 'cash_shift_required') {
    return 'La caja no está abierta. Ve a Configuración > Turno y Caja, selecciona la sucursal y abre CAJA-01 antes de cobrar.';
  }
  if (code === 'permission_denied') {
    return 'Tu usuario no tiene permiso para crear pedidos o cobrar en esta sucursal.';
  }
  if (code === 'actor_required') {
    return 'Tu sesión expiró. Inicia sesión otra vez para continuar en el POS.';
  }
  if (code === 'product_unavailable') {
    return 'Uno de los productos no está disponible en la sucursal actual.';
  }
  return message || 'Error al crear la orden.';
};

const PointOfSale = () => {
  const [searchParams] = useSearchParams();
  const editOrderId = searchParams.get('edit_order_id') || '';
  const { session, state: sessionState } = usePosSession();
  const branchId = session?.active_branch?.id || '';

  const [activeCategory, setActiveCategory] = useState('Todas');
  const [isPaymentOpen, setPaymentOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [modifierProduct, setModifierProduct] = useState<Product | null>(null);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [modifierSelections, setModifierSelections] = useState<Record<string, string[]>>({});
  const [modifierText, setModifierText] = useState<Record<string, string>>({});
  const [modifierError, setModifierError] = useState('');
  const [modifierLoadError, setModifierLoadError] = useState('');
  const [extraModalOpen, setExtraModalOpen] = useState(false);
  const [availableExtras, setAvailableExtras] = useState<IngredientExtra[]>([]);
  const [extraTargetLineId, setExtraTargetLineId] = useState('');
  const [extraSelections, setExtraSelections] = useState<Record<string, number>>({});
  const [extraError, setExtraError] = useState('');
  const [extrasLoading, setExtrasLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const [ownerName, setOwnerName] = useState('');
  const [orderType, setOrderType] = useState('dine-in');
  const [customerPhone, setCustomerPhone] = useState('');
  const [searchResults, setSearchResults] = useState<PosCustomer[]>([]);
  const [customerLookupStatus, setCustomerLookupStatus] = useState<CustomerLookupStatus>('idle');
  const [customerSearchError, setCustomerSearchError] = useState('');
  const [newCustomerName, setNewCustomerName] = useState('');
  const [newCustomerEmail, setNewCustomerEmail] = useState('');
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const [createCustomerError, setCreateCustomerError] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState<PosCustomer | null>(null);
  const [selectedAddressId, setSelectedAddressId] = useState('');
  const [showAddressForm, setShowAddressForm] = useState(false);
  const searchControllerRef = useRef<AbortController | null>(null);

  const [categories, setCategories] = useState<string[]>(['Todas']);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalogError, setCatalogError] = useState('');
  const [editingOrder, setEditingOrder] = useState<EditableOrder | null>(null);
  const [editLoadError, setEditLoadError] = useState('');

  // Cargar catálogo al montar (no precarga clientes)
  useEffect(() => {
    if (!localStorage.getItem('pos_register_id')) {
      localStorage.setItem('pos_register_id', 'CAJA-01');
    }
    if (!branchId) {
      if (sessionState.status !== 'loading') {
        setCatalogError('La sesión no tiene una sucursal activa. Vuelve a iniciar sesión.');
        setLoading(false);
      }
      return;
    }
    const fetchData = async () => {
      setLoading(true);
      setCatalogError('');
      try {
        const [catData, prodData] = await Promise.all([
          fetchApi<any[]>('/categories'),
          fetchApi<any[]>(`/catalog/products?branch_id=${encodeURIComponent(branchId)}`),
        ]);
        if (Array.isArray(catData)) {
          setCategories(['Todas', ...catData.map((c) => c.name)]);
        }
        if (Array.isArray(prodData)) {
          const mappedProducts = prodData
            .filter((p: any) => (
              p.status === 'active'
              && p.is_available !== false
              && Number.isSafeInteger(p.price_cents)
              && p.price_cents > 0
            ))
            .map((p: any) => ({
              id: p.id,
              name: p.name,
              sku: p.sku,
              category: p.category_name,
              price_cents: p.price_cents,
              description: p.description,
              station: p.station,
              image_url: p.image_url,
            }));
          setProducts(mappedProducts);
        }
      } catch (e) {
        console.error('Error al cargar datos del POS:', e);
        setCatalogError('No se pudo cargar el menú de la sucursal.');
        setProducts([]);
      } finally {
        setLoading(false);
      }
    };
    void fetchData();
  }, [branchId, sessionState.status]);

  useEffect(() => {
    if (!editOrderId || products.length === 0) return;
    let cancelled = false;
    fetchApi<EditableOrder>(`/orders/${editOrderId}`)
      .then((order) => {
        if (cancelled) return;
        if (!order.editable) {
          setEditLoadError(order.edit_block_reason || 'Este pedido ya no se puede editar.');
          return;
        }
        const productById = new Map(products.map((product) => [product.id, product]));
        const restored = order.lines.flatMap((line) => {
          const product = productById.get(line.product_id);
          if (!product) return [];
          const comments: SelectedOrderComment[] = [];
          const extras: SelectedIngredientExtra[] = [];
          const modifiers: SelectedModifier[] = [];
          for (const selected of line.selected_modifiers || []) {
            if (selected.kind === 'order_comment' || selected.selection_kind === 'order_comment') {
              comments.push({ id: String(selected.comment_preset_id || selected.option_id), text: String(selected.kitchen_text || selected.name || '') });
            } else if (selected.kind === 'ingredient_extra' || selected.selection_kind === 'ingredient_extra') {
              extras.push({
                extra_id: String(selected.extra_id || selected.variation_id || selected.option_id),
                name: String(selected.name || selected.kitchen_text || 'Adicional'),
                portion_quantity: String(selected.portion_quantity || '1'),
                sale_price_cents: Number(selected.price_delta_cents || 0),
                station: (selected.station || line.station) as IngredientExtra['station'],
                portions: Number(selected.portions || 1),
              });
            } else {
              modifiers.push({
                option_id: String(selected.option_id || selected.id),
                option_name: String(selected.name || selected.kitchen_text || 'Opción'),
                price_delta_cents: Number(selected.price_delta_cents || 0),
                text: selected.text ? String(selected.text) : undefined,
              });
            }
          }
          return [{
            ...product,
            lineId: crypto.randomUUID(),
            quantity: line.quantity,
            modifiers,
            commentPresets: comments,
            ingredientExtras: extras,
            modifierPriceCents: modifiers.reduce((sum, modifier) => sum + modifier.price_delta_cents, 0),
          }];
        });
        setEditingOrder(order);
        setCart(restored);
        setOwnerName(order.owner_name || '');
        setOrderType(order.order_type);
        setPaymentMethod(order.payment_method_intent || null);
      })
      .catch((error) => {
        if (!cancelled) {
          setEditLoadError(error instanceof ApiError ? error.message : 'No fue posible cargar el pedido.');
        }
      });
    return () => { cancelled = true; };
  }, [editOrderId, products]);

  // Búsqueda exacta por teléfono con debounce y AbortController
  useEffect(() => {
    const phone = validMexicanPhone(customerPhone);
    if (!branchId || !phone) {
      searchControllerRef.current?.abort();
      setSearchResults([]);
      setCustomerLookupStatus('idle');
      setCustomerSearchError('');
      return undefined;
    }
    setCustomerLookupStatus('searching');
    setCustomerSearchError('');
    searchControllerRef.current?.abort();
    const controller = new AbortController();
    searchControllerRef.current = controller;
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({
        branch_id: branchId,
        phone,
        limit: '20',
      });
      fetchApi<PosCustomerPage>(`/customers?${params.toString()}`, {
        signal: controller.signal,
      })
        .then((page) => {
          const items = page.items || [];
          setSearchResults(items);
          setCustomerLookupStatus(items.length > 0 ? 'found' : 'not-found');
        })
        .catch((err) => {
          if (err instanceof DOMException && err.name === 'AbortError') return;
          setCustomerSearchError('No fue posible buscar el teléfono. Intenta nuevamente.');
          setCustomerLookupStatus('error');
        });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [customerPhone, branchId]);

  const selectCustomer = useCallback((customer: PosCustomer) => {
    setSelectedCustomer(customer);
    setOwnerName(customer.name || '');
    setSearchResults([]);
    setCustomerLookupStatus('idle');
    setNewCustomerName('');
    setNewCustomerEmail('');
    setCreateCustomerError('');
    setShowAddressForm(false);
    // Seleccionar domicilio predeterminado o el único activo
    const activeAddresses = (customer.addresses || []).filter((a) => a.status === 'active');
    const defaultAddr = activeAddresses.find((a) => a.is_default);
    if (defaultAddr) {
      setSelectedAddressId(defaultAddr.id);
    } else if (activeAddresses.length === 1) {
      setSelectedAddressId(activeAddresses[0].id);
    } else {
      setSelectedAddressId('');
    }
  }, []);

  const clearCustomer = useCallback(() => {
    setSelectedCustomer(null);
    setOwnerName('');
    setSelectedAddressId('');
    setCustomerPhone('');
    setSearchResults([]);
    setCustomerLookupStatus('idle');
    setNewCustomerName('');
    setNewCustomerEmail('');
    setCreateCustomerError('');
    setShowAddressForm(false);
  }, []);

  const registerCustomer = async () => {
    const phone = validMexicanPhone(customerPhone);
    const name = newCustomerName.trim();
    if (!phone || !name || !branchId) {
      setCreateCustomerError('Captura un teléfono válido y el nombre del cliente.');
      return;
    }
    setCreatingCustomer(true);
    setCreateCustomerError('');
    try {
      const customer = await fetchApi<PosCustomer>('/customers', {
        method: 'POST',
        body: JSON.stringify({
          branch_id: branchId,
          name,
          email: newCustomerEmail.trim() || undefined,
          phones: [{ number: phone, is_primary: true, type: 'mobile' }],
        }),
      });
      selectCustomer(customer);
      if (orderType === 'delivery') setShowAddressForm(true);
    } catch (err) {
      setCreateCustomerError(
        err instanceof ApiError ? err.message : 'No se pudo registrar al cliente.',
      );
    } finally {
      setCreatingCustomer(false);
    }
  };

  const filteredProducts = products.filter(p => {
    if (activeCategory !== 'Todas' && p.category !== activeCategory) return false;
    if (searchQuery && !p.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const addToCart = (product: Product, modifiers: SelectedModifier[] = [], commentPresets: SelectedOrderComment[] = [], ingredientExtras: SelectedIngredientExtra[] = []) => {
    setCart(prev => {
      const existing = modifiers.length === 0 && commentPresets.length === 0 && ingredientExtras.length === 0 ? prev.find(item => item.id === product.id && item.modifiers.length === 0 && item.commentPresets.length === 0 && item.ingredientExtras.length === 0) : undefined;
      if (existing) {
        return prev.map(item => item.lineId === existing.lineId ? { ...item, quantity: item.quantity + 1 } : item);
      }
      return [...prev, {
        ...product,
        lineId: crypto.randomUUID(),
        quantity: 1,
        modifiers,
        commentPresets,
        ingredientExtras,
        modifierPriceCents: modifiers.reduce((sum, modifier) => sum + modifier.price_delta_cents, 0),
      }];
    });
  };

  const resetModifierModal = () => {
    setModifierProduct(null);
    setModifierGroups([]);
    setModifierSelections({});
    setModifierText({});
    setModifierError('');
    setModifierLoadError('');
  };

  const closeExtraModal = () => {
    setExtraModalOpen(false);
    setExtraTargetLineId('');
    setExtraSelections({});
    setExtraError('');
  };

  const openIngredientExtras = async () => {
    if (cart.length === 0) return;
    setExtraModalOpen(true);
    setExtraError('');
    setExtraTargetLineId(cart.length === 1 ? cart[0].lineId : '');
    setExtraSelections(cart.length === 1 ? Object.fromEntries(cart[0].ingredientExtras.map((extra) => [extra.extra_id, extra.portions])) : {});
    setExtrasLoading(true);
    try {
      const extras = await fetchApi<IngredientExtra[]>(`/catalog/ingredient-extras/available?branch_id=${encodeURIComponent(branchId)}`);
      setAvailableExtras(Array.isArray(extras) ? extras.filter((extra) => (
        Number.isSafeInteger(extra.sale_price_cents) && extra.sale_price_cents >= 0
      )) : []);
    } catch (error) {
      setExtraError(error instanceof ApiError ? error.message : 'No fue posible cargar los ingredientes adicionales.');
      setAvailableExtras([]);
    } finally {
      setExtrasLoading(false);
    }
  };

  const selectExtraTarget = (lineId: string) => {
    setExtraTargetLineId(lineId);
    const line = cart.find((item) => item.lineId === lineId);
    setExtraSelections(Object.fromEntries((line?.ingredientExtras || []).map((extra) => [extra.extra_id, extra.portions])));
    setExtraError('');
  };

  const removeIngredientExtra = (lineId: string, extraId: string) => {
    setCart((current) => current.map((item) => item.lineId === lineId ? { ...item, ingredientExtras: item.ingredientExtras.filter((extra) => extra.extra_id !== extraId) } : item));
  };

  const updateExtraSelection = (extra: IngredientExtra, portions: number) => {
    setExtraSelections((current) => {
      const next = { ...current };
      if (portions <= 0) delete next[extra.extra_id || extra.id || ''];
      else next[extra.extra_id || extra.id || ''] = Math.min(99, Math.max(0, Math.trunc(portions)));
      return next;
    });
  };

  const applyIngredientExtras = () => {
    if (!extraTargetLineId) {
      setExtraError('Selecciona la línea del pedido que recibirá los ingredientes adicionales.');
      return;
    }
    const selected = availableExtras.flatMap((extra) => {
      const extraId = extra.extra_id || extra.id || '';
      const portions = extraSelections[extraId] || 0;
      return portions > 0 ? [{ ...extra, extra_id: extraId, portions }] : [];
    });
    setCart((current) => current.map((item) => item.lineId === extraTargetLineId ? { ...item, ingredientExtras: selected } : item));
    closeExtraModal();
  };

  const selectProduct = async (product: Product) => {
    try {
      const groups = await fetchApi<ModifierGroup[]>(
        `/products/${product.id}/modifiers?branch_id=${encodeURIComponent(branchId)}`,
      );
      if (!Array.isArray(groups) || shouldAddProductWithoutModifiers(groups)) {
        resetModifierModal();
        addToCart(product);
        return;
      }
      setModifierProduct(product);
      setModifierGroups(groups);
      setModifierSelections({});
      setModifierText({});
      setModifierError('');
      setModifierLoadError('');
    } catch {
      setModifierProduct(product);
      setModifierGroups([]);
      setModifierLoadError('No fue posible cargar las variaciones del producto.');
    }
  };

  const toggleModifier = (group: ModifierGroup, optionId: string) => {
    setModifierSelections((current) => {
      const selected = current[group.id] || [];
      if (selected.includes(optionId)) return { ...current, [group.id]: selected.filter((id) => id !== optionId) };
      if (group.options.find((option) => option.id === optionId)?.variation_kind === 'ingredient_extra') return { ...current, [group.id]: toggleIngredientVariationSelection(selected, group.options, optionId) };
      if (group.maximum_selections === 1) return { ...current, [group.id]: [optionId] };
      if (selected.length >= group.maximum_selections) return current;
      return { ...current, [group.id]: [...selected, optionId] };
    });
  };

  const confirmModifiers = () => {
    if (!modifierProduct) return;
    const invalid = modifierGroups.find((group) => (modifierSelections[group.id] || []).length < group.minimum_selections);
    if (invalid) {
      setModifierError(`Selecciona al menos ${invalid.minimum_selections} opción(es) en ${invalid.name}.`);
      return;
    }
    const selected = modifierGroups.flatMap((group) => (modifierSelections[group.id] || []).map((optionId) => {
      const option = group.options.find((item) => item.id === optionId)!;
      return { option_id: option.id, option_name: option.name, price_delta_cents: option.price_delta_cents, text: option.effect_type === 'instruction' ? modifierText[option.id] : undefined };
    }));
    const commentOptionIds = new Set(
      modifierGroups.flatMap((group) => group.options)
        .filter((option) => option.variation_kind === 'order_comment')
        .map((option) => option.id),
    );
    const commentPresets = selected
      .filter((selection) => commentOptionIds.has(selection.option_id))
      .map((selection) => ({ id: selection.option_id, text: selection.option_name }));
    const modifiers = selected.filter((selection) => !commentOptionIds.has(selection.option_id));
    addToCart(modifierProduct, modifiers, commentPresets);
    resetModifierModal();
  };

  const updateQuantity = (lineId: string, delta: number) => {
    setCart(prev => prev.flatMap(item => {
      if (item.lineId === lineId) {
        const newQty = item.quantity + delta;
        return newQty > 0 ? [{ ...item, quantity: newQty }] : [];
      }
      return [item];
    }));
  };

  const removeCartLine = (lineId: string) => {
    setCart((current) => current.filter((item) => item.lineId !== lineId));
  };

  const processTransaction = async () => {
    const registerId = localStorage.getItem('pos_register_id') || 'CAJA-01';
    if (!paymentMethod && !editingOrder) return;
    if (!branchId) {
      alert('No hay sucursal asignada para este POS. Inicia sesión de nuevo o configura la sucursal.');
      return;
    }

    const payload = {
      owner_name: ownerName || 'Cliente General',
      customer_id: selectedCustomer?.id || undefined,
      delivery_address_id: selectedAddressId || undefined,
      payment_method_intent: orderType === 'dine-in' ? undefined : paymentMethod,
      order_type: orderType,
      branch_id: branchId || undefined,
      register_id: registerId || undefined,
      lines: cart.map((item) => ({
        product_id: item.id,
        quantity: item.quantity,
        notes: '',
        modifiers: item.modifiers.map((m) => ({ option_id: m.option_id, text: m.text })),
        comment_preset_ids: item.commentPresets.map((comment) => comment.id),
        ingredient_extras: item.ingredientExtras.map((extra) => ({ extra_id: extra.extra_id, portions: extra.portions })),
      })),
    };

    try {
      if (editingOrder) {
        await fetchApi(`/orders/${editingOrder.id}/amendments`, {
          method: 'POST',
          headers: { 'Idempotency-Key': crypto.randomUUID() },
          body: JSON.stringify({ expected_version: editingOrder.version, lines: payload.lines }),
        });
        alert(`Pedido #${editingOrder.folio} actualizado.`);
        window.location.href = '/pos/history';
        return;
      }
      const orderData = await fetchApi<{ id: string; folio: string; total_cents: number }>(
        '/orders',
        { method: 'POST', body: JSON.stringify(payload) },
      );
      if (orderType !== 'dine-in') {
        alert(`Pedido #${orderData.folio} guardado como pendiente de pago.`);
        setCart([]);
        setPaymentOpen(false);
        setPaymentMethod(null);
        clearCustomer();
        return;
      }
      // Cobro inmediato en sucursal
      try {
        await fetchApi(`/orders/${orderData.id}/payments`, {
          method: 'POST',
          body: JSON.stringify({ amount_cents: orderData.total_cents, method: paymentMethod }),
        });
      } catch (payErr) {
        const msg = payErr instanceof ApiError ? payErr.message : 'Error desconocido';
        alert(`Orden creada, pero el pago falló: ${msg}`);
        return;
      }
      alert(`¡Venta finalizada! Orden #${orderData.folio}`);
      setCart([]);
      setPaymentOpen(false);
      setPaymentMethod(null);
      clearCustomer();
    } catch (err) {
      if (err instanceof ApiError) {
        alert(orderErrorMessage(err.code, err.message));
      } else {
        alert('Error de conexión.');
      }
    }
  };

  const subtotalCents = cartSubtotalCents(cart);
  const taxCents = 0;
  const totalCents = subtotalCents + taxCents;
  const activeAddresses = (selectedCustomer?.addresses || []).filter((a) => a.status === 'active');
  const canCheckout = Boolean(
    editingOrder ||
      orderType !== 'delivery' ||
      (selectedCustomer && selectedAddressId),
  );

  return (
    <div className="pos-sale-screen">
      <header className="pos-sale-header">
        <div className="pos-sale-brand">
          <span className="pos-sale-mark">K</span>
          <div><strong>Kiwi POS</strong><small>Venta rápida</small></div>
        </div>
        <label className="pos-sale-search">
          <Search size={19} />
          <input type="search" placeholder="Buscar producto…" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
        </label>
        <div className="pos-sale-branch">{session?.active_branch?.name || 'Sucursal activa'}</div>
      </header>

      <div className="pos-sale-workspace">
        <main className="pos-sale-catalog">
          {editingOrder && <div className="pos-sale-edit-banner">Editando pedido <strong>#{editingOrder.folio}</strong> · Guardar no confirma el pago.</div>}
          {editLoadError && <div role="alert" className="pos-sale-feedback error">{editLoadError}</div>}
          <nav className="pos-sale-menu" aria-label="Menú de categorías">
            {categories.map((cat) => {
              const isActive = activeCategory === cat;
              return (
                <button key={cat} type="button" className={isActive ? 'active' : ''} aria-pressed={isActive} onClick={() => setActiveCategory(cat)}>
                  {getProductIcon(cat, 22)}
                  <span>{cat === 'Todas' ? 'Todo el menú' : cat}</span>
                </button>
              );
            })}
          </nav>

          <section className="pos-sale-products" aria-label="Productos disponibles">
            <div className="pos-sale-products-heading">
              <div><span>Selecciona un producto</span><strong>{filteredProducts.length} disponibles</strong></div>
            </div>
            <div className="pos-sale-products-grid">
              {loading ? (
                <div className="pos-sale-feedback">Cargando menú...</div>
              ) : catalogError ? (
                <div className="pos-sale-feedback error">{catalogError}</div>
              ) : filteredProducts.length === 0 ? (
                <div className="pos-sale-feedback">No hay productos.</div>
              ) : (
                filteredProducts.map((product) => (
                  <button type="button" key={product.id} onClick={() => void selectProduct(product)} className="pos-sale-product-card">
                    <div className="pos-sale-product-visual">
                      {product.image_url ? (
                        <img src={product.image_url} alt={product.name} />
                      ) : (
                        getProductIcon(product.category, 48)
                      )}
                    </div>
                    <span>{product.name}</span>
                    <strong>{formatMxnCents(product.price_cents)}</strong>
                  </button>
                ))
              )}
            </div>
          </section>

          <section className={modifierProduct ? 'pos-sale-complements is-open' : 'pos-sale-complements'} aria-label="Complementos del producto">
            <div className="pos-sale-complements-header">
              <div><span>Complementos</span><strong>{modifierProduct ? modifierProduct.name : 'Personaliza tu producto'}</strong></div>
              {modifierProduct && <button type="button" onClick={resetModifierModal} aria-label="Cerrar complementos"><X size={17} /></button>}
            </div>
            {!modifierProduct ? (
              <p className="pos-sale-complements-empty">Selecciona un producto con opciones para ver aquí sus complementos e indicaciones.</p>
            ) : modifierLoadError ? (
              <div role="alert" className="pos-sale-complements-error"><span>{modifierLoadError}</span><button type="button" onClick={() => void selectProduct(modifierProduct)}>Reintentar</button></div>
            ) : (
              <div className="pos-sale-complement-content">
                <div className="pos-sale-complement-groups">
                  {modifierGroups.map((group) => (
                    <section key={group.id}>
                      <div className="pos-sale-complement-group-title">
                        <strong>{group.name}</strong>
                        <small>{group.minimum_selections > 0 ? 'Obligatorio · ' + group.minimum_selections + '-' + group.maximum_selections : 'Hasta ' + group.maximum_selections}</small>
                      </div>
                      <div className="pos-sale-complement-options">
                        {group.options.map((option) => {
                          const checked = (modifierSelections[group.id] || []).includes(option.id);
                          return (
                            <div key={option.id} className="pos-sale-complement-option">
                              <button type="button" className={checked ? 'active' : ''} aria-pressed={checked} onClick={() => toggleModifier(group, option.id)}>
                                {checked && <Check size={15} />}
                                {option.name}{option.price_delta_cents > 0 ? ' +' + formatMxnCents(option.price_delta_cents) : ''}
                              </button>
                              {checked && option.effect_type === 'instruction' && (
                                <input value={modifierText[option.id] || ''} onChange={(event) => setModifierText({ ...modifierText, [option.id]: event.target.value })} placeholder="Instrucción para cocina" maxLength={240} />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
                <div className="pos-sale-complement-action">
                  {modifierError && <span>{modifierError}</span>}
                  <button type="button" onClick={confirmModifiers}>Agregar al pedido</button>
                </div>
              </div>
            )}
          </section>
        </main>

        <aside className="pos-sale-cart">
          <div className="pos-sale-cart-heading">
            <div><span>Cuenta actual</span><strong>Detalle del pedido</strong></div>
            <div className="pos-sale-cart-actions">
              <button type="button" onClick={() => setPaymentOpen(true)}><Users size={17} /><span>{selectedCustomer?.name || 'Cliente'}</span></button>
              <button type="button" onClick={() => void openIngredientExtras()} disabled={cart.length === 0 || extrasLoading}><Plus size={17} /><span>Adicionales</span></button>
            </div>
          </div>

          <div className="pos-sale-order-types">
            {ORDER_TYPES.map((type) => (
              <button key={type.value} type="button" className={orderType === type.value ? 'active' : ''} onClick={() => setOrderType(type.value)}>{type.label}</button>
            ))}
          </div>

          <div className="pos-sale-cart-items">
            {cart.length === 0 ? (
              <div className="pos-sale-empty-cart">
                <span><ShoppingBag size={32} /></span>
                <strong>La cuenta está vacía</strong>
                <p>Toca un producto para agregarlo</p>
              </div>
            ) : (
              cart.map((item) => (
                <div key={item.lineId} className="pos-sale-cart-item">
                  <div className="pos-sale-cart-icon">{item.image_url ? <img src={item.image_url} alt={item.name} /> : getProductIcon(item.category, 22)}</div>
                  <div className="pos-sale-cart-copy">
                    <strong>{item.name}</strong>
                    <span>{formatMxnCents(item.price_cents)}</span>
                    {item.commentPresets.map((comment) => <small key={comment.id}>Comentario: {comment.text}</small>)}
                    {item.modifiers.map((modifier) => <small key={modifier.option_id}>+ {modifier.text || modifier.option_name}</small>)}
                    {item.ingredientExtras.map((extra) => (
                      <small key={extra.extra_id}>
                        + {extra.name} × {extra.portions}
                        <button type="button" aria-label={`Quitar ${extra.name}`} onClick={() => removeIngredientExtra(item.lineId, extra.extra_id)}><X size={12} /></button>
                      </small>
                    ))}
                  </div>
                  <div className="pos-sale-cart-controls">
                    <strong>{formatMxnCents(cartLineTotalCents(item))}</strong>
                    <div>
                      <button type="button" onClick={() => updateQuantity(item.lineId, -1)} aria-label="Restar producto"><Minus size={14} /></button>
                      <span>{item.quantity}</span>
                      <button type="button" onClick={() => updateQuantity(item.lineId, 1)} aria-label="Sumar producto"><Plus size={14} /></button>
                      <button type="button" className="remove" onClick={() => removeCartLine(item.lineId)} aria-label={`Eliminar ${item.name} del pedido`}><Trash2 size={14} /></button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="pos-sale-summary">
            <div><span>Subtotal</span><span>{formatMxnCents(subtotalCents)}</span></div>
            <div><span>IVA incluido</span><span>{formatMxnCents(taxCents)}</span></div>
            <div className="total"><strong>Total</strong><strong>{formatMxnCents(totalCents)}</strong></div>
          </div>

          <button
            type="button"
            className="pos-sale-pay"
            onClick={() => {
              setPaymentMethod(null);
              setPaymentOpen(true);
            }}
            disabled={cart.length === 0}
          >
            {editingOrder
              ? 'Guardar cambios'
              : orderType === 'dine-in'
                ? `Pagar ${cart.length > 0 ? formatMxnCents(totalCents) : ''}`
                : `Guardar pedido pendiente ${cart.length > 0 ? formatMxnCents(totalCents) : ''}`}
          </button>
        </aside>
      </div>
      <Modal isOpen={extraModalOpen} onClose={closeExtraModal} title="Ingredientes adicionales">
        <div style={{ display: 'grid', gap: 14, maxHeight: '65vh', overflowY: 'auto' }}>
          <p style={{ margin: 0, color: '#64748b' }}>Los adicionales son corporativos y se aplican a una línea específica del pedido. El backend recalcula precio, cantidad e inventario al confirmar.</p>
          {cart.length > 1 ? <label>Línea destino<select value={extraTargetLineId} onChange={(event) => selectExtraTarget(event.target.value)} style={{ width: '100%', padding: 10, border: '1px solid #cbd5e1', borderRadius: 8 }}><option value="">Selecciona una línea</option>{cart.map((item) => <option key={item.lineId} value={item.lineId}>{item.name} · {item.quantity} pieza(s)</option>)}</select></label> : <p style={{ margin: 0 }}><strong>Línea destino:</strong> {cart[0]?.name}</p>}
          {extraError && <div role="alert" style={{ color: '#b91c1c' }}>{extraError}</div>}
          {extrasLoading ? <p>Cargando ingredientes adicionales…</p> : availableExtras.length === 0 ? <p style={{ color: '#64748b' }}>No hay ingredientes adicionales corporativos disponibles.</p> : <div style={{ display: 'grid', gap: 8 }}>{availableExtras.map((extra) => { const extraId = extra.extra_id || extra.id || ''; const portions = extraSelections[extraId] || 0; return <div key={extraId} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', padding: 10, border: `1px solid ${portions > 0 ? '#10b981' : '#e2e8f0'}`, borderRadius: 8 }}><div><strong>{extra.name}</strong><div style={{ color: '#64748b', fontSize: 13 }}>{extra.portion_quantity} {extra.unit_code || 'unidad'} · {formatMxnCents(extra.sale_price_cents)} · {extra.station}</div></div><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><button type="button" aria-label={`Quitar ${extra.name}`} onClick={() => updateExtraSelection(extra, portions - 1)} disabled={portions === 0} style={{ width: 32, height: 32 }}>−</button><span aria-label={`Porciones de ${extra.name}`}>{portions}</span><button type="button" aria-label={`Agregar ${extra.name}`} onClick={() => updateExtraSelection(extra, portions + 1)} style={{ width: 32, height: 32 }}>+</button></div></div>; })}</div>}
          <button type="button" onClick={applyIngredientExtras} disabled={extrasLoading || availableExtras.length === 0} style={{ padding: 14, border: 0, borderRadius: 8, background: '#10b981', color: '#fff', fontWeight: 700 }}>Aplicar a la línea</button>
        </div>
      </Modal>
      {/* Payment Modal */}
      <Modal isOpen={isPaymentOpen} onClose={() => setPaymentOpen(false)} title="Cobrar pedido">
        <div style={{ marginBottom: 18 }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>
            Tipo de pedido
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
            {ORDER_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => setOrderType(type.value)}
                style={{
                  padding: '9px 6px',
                  borderRadius: 8,
                  border: `1px solid ${orderType === type.value ? '#10b981' : '#d1d5db'}`,
                  background: orderType === type.value ? '#ecfdf5' : '#fff',
                  color: orderType === type.value ? '#047857' : '#64748b',
                  fontWeight: orderType === type.value ? 700 : 500,
                  cursor: 'pointer',
                }}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>

        {/* Cliente seleccionado o búsqueda */}
        {selectedCustomer ? (
          <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, border: '1px solid #e2e8f0', background: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>{selectedCustomer.name}</strong>
              <button
                onClick={clearCustomer}
                aria-label="Quitar cliente seleccionado"
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#64748b' }}
              >
                <X size={16} />
              </button>
            </div>
            {selectedCustomer.phones && selectedCustomer.phones.length > 0 && (
              <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                {selectedCustomer.phones[0].captured_number || selectedCustomer.phones[0].normalized_number}
              </div>
            )}
            {selectedCustomer.legacy_address_reference && (
              <div style={{ marginTop: 8, padding: 8, borderRadius: 6, border: '1px dashed #cbd5e1', fontSize: '0.8rem', color: '#64748b' }}>
                <strong>Domicilio heredado por confirmar:</strong> {selectedCustomer.legacy_address_reference}
                <div style={{ marginTop: 4 }}>
                  No se usará para entregar hasta que captures y guardes un domicilio estructurado.
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>
              Teléfono del cliente
            </label>
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={customerPhone}
              onChange={(e) => {
                setCustomerPhone(e.target.value);
                setNewCustomerName('');
                setNewCustomerEmail('');
                setCreateCustomerError('');
              }}
              placeholder="10 dígitos, por ejemplo 6691234567"
              style={{ width: '100%', padding: '12px 16px', borderRadius: 12, border: '1px solid var(--glass-border)' }}
            />
            {!validMexicanPhone(customerPhone) && customerPhone.trim() && (
              <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: 8 }}>
                Completa un teléfono mexicano de 10 dígitos.
              </div>
            )}
            {customerLookupStatus === 'searching' && (
              <div style={{ color: '#64748b', fontSize: '0.85rem', marginTop: 8 }}>
                Buscando el teléfono…
              </div>
            )}
            {customerSearchError && <div style={{ color: '#dc2626', fontSize: '0.85rem', marginTop: 8 }}>{customerSearchError}</div>}
            {customerLookupStatus === 'found' && searchResults.length > 0 && (
              <section
                aria-label="Clientes encontrados por teléfono"
                style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}
              >
                {searchResults.map((c) => {
                  const phone = c.phones?.[0]?.captured_number || c.phones?.[0]?.normalized_number || '';
                  const addrCount = (c.addresses || []).filter((a) => a.status === 'active').length;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => selectCustomer(c)}
                      style={{ textAlign: 'left', padding: '10px 12px', border: '1px solid #cbd5e1', borderRadius: 8, background: '#fff', cursor: 'pointer' }}
                    >
                      <div style={{ fontWeight: 600 }}>{c.name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                        {phone && <span>{phone} · </span>}
                        {addrCount} domicilio(s)
                      </div>
                    </button>
                  );
                })}
              </section>
            )}
            {customerLookupStatus === 'not-found' && (
              <div style={{ marginTop: 12, padding: 12, borderRadius: 8, border: '1px solid #d1fae5', background: '#f0fdf4' }}>
                <strong style={{ fontSize: '0.9rem', color: '#166534' }}>
                  Teléfono no registrado
                </strong>
                <p style={{ margin: '4px 0 10px', color: '#64748b', fontSize: '0.8rem' }}>
                  Captura el nombre para dar de alta al cliente sin perder esta venta.
                </p>
                <div style={{ display: 'grid', gap: 8 }}>
                  <input
                    type="text"
                    value={newCustomerName}
                    onChange={(e) => setNewCustomerName(e.target.value)}
                    placeholder="Nombre completo"
                    autoComplete="name"
                    style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #d1d5db', boxSizing: 'border-box' }}
                  />
                  <input
                    type="email"
                    value={newCustomerEmail}
                    onChange={(e) => setNewCustomerEmail(e.target.value)}
                    placeholder="Correo (opcional)"
                    autoComplete="email"
                    style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #d1d5db', boxSizing: 'border-box' }}
                  />
                  {createCustomerError && (
                    <div style={{ color: '#dc2626', fontSize: '0.8rem' }}>{createCustomerError}</div>
                  )}
                  <button
                    type="button"
                    onClick={() => void registerCustomer()}
                    disabled={creatingCustomer || !newCustomerName.trim()}
                    style={{ padding: '10px 12px', border: 0, borderRadius: 8, background: '#10b981', color: '#fff', fontWeight: 700, cursor: creatingCustomer || !newCustomerName.trim() ? 'not-allowed' : 'pointer', opacity: creatingCustomer || !newCustomerName.trim() ? 0.6 : 1 }}
                  >
                    {creatingCustomer ? 'Registrando…' : 'Registrar y seleccionar cliente'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Domicilios para delivery */}
        {orderType === 'delivery' && selectedCustomer && (
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>Domicilio de entrega</label>
            {activeAddresses.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: '0.85rem' }}>Este cliente todavía no tiene domicilios confirmados.</p>
            ) : (
              <div style={{ display: 'grid', gap: 8 }}>
                {activeAddresses.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => setSelectedAddressId(a.id)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: `1px solid ${selectedAddressId === a.id ? '#10b981' : '#d1d5db'}`,
                      background: selectedAddressId === a.id ? '#ecfdf5' : '#fff',
                      textAlign: 'left',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <strong>{a.alias}</strong>
                      {a.is_default && <span style={{ color: '#047857', fontSize: '0.75rem' }}>Predeterminado</span>}
                    </div>
                    <div style={{ color: '#475569', fontSize: '0.82rem', marginTop: 2 }}>
                      {a.street} {a.exterior_number}
                      {a.interior_number ? ` Int. ${a.interior_number}` : ''}, {a.neighborhood}
                    </div>
                  </button>
                ))}
              </div>
            )}
            {!showAddressForm && (
              <button onClick={() => setShowAddressForm(true)} style={{ marginTop: 8, padding: '6px 12px', border: '1px solid #10b981', borderRadius: 6, background: '#fff', color: '#10b981', cursor: 'pointer', fontSize: '0.85rem' }}>
                + Agregar domicilio
              </button>
            )}
            {showAddressForm && (
              <CustomerAddressForm
                customerId={selectedCustomer.id}
                branchId={branchId}
                legacyAddressReference={selectedCustomer.legacy_address_reference || ''}
                onSaved={(addr) => {
                  setSelectedCustomer((prev) => prev ? { ...prev, addresses: [...(prev.addresses || []), addr] } : prev);
                  setSelectedAddressId(addr.id);
                  setShowAddressForm(false);
                }}
                onCancel={() => setShowAddressForm(false)}
              />
            )}
          </div>
        )}

        {/* Validación delivery */}
        {orderType === 'delivery' && !editingOrder && !canCheckout && (
          <div style={{ marginBottom: 12, color: '#b91c1c', fontSize: '0.85rem' }}>
            {!selectedCustomer ? 'Falta seleccionar cliente. ' : ''}
            {!selectedAddressId ? 'Falta seleccionar domicilio de entrega.' : ''}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>Nombre del cliente</label>
          <input
            type="text"
            value={ownerName}
            onChange={(e) => setOwnerName(e.target.value)}
            placeholder="Ej. Juan Pérez"
            style={{ width: '100%', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--glass-border)', fontSize: '1rem', outline: 'none' }}
          />
        </div>
        <section className="pos-payment-methods" aria-labelledby="payment-method-title">
          <div className="pos-payment-heading">
            <div><span>Paso final</span><strong id="payment-method-title">¿Cómo pagará el cliente?</strong></div>
            <strong>{formatMxnCents(totalCents)}</strong>
          </div>
          <div className="pos-payment-grid">
            {PAYMENT_METHODS.map((method) => {
              const Icon = method.icon;
              const selected = paymentMethod === method.value;
              return (
                <button key={method.value} type="button" className={selected ? 'active' : ''} aria-pressed={selected} onClick={() => setPaymentMethod(method.value)}>
                  <span><Icon size={21} /></span>
                  <div><strong>{method.label}</strong><small>{method.description}</small></div>
                  {selected && <Check size={17} />}
                </button>
              );
            })}
          </div>
        </section>
        <button
          onClick={() => void processTransaction()}
          disabled={!canCheckout || (!paymentMethod && !editingOrder)}
          className="pos-payment-confirm"
        >
          {editingOrder
            ? 'Guardar cambios sin confirmar pago'
            : paymentMethod
              ? orderType === 'dine-in'
                ? `Confirmar cobro · ${formatMxnCents(totalCents)}`
                : `Guardar pendiente · ${formatMxnCents(totalCents)}`
              : 'Selecciona un método de pago'}
        </button>
      </Modal>
    </div>
  );
};

// ---------------------------------------------------------------------------
// CustomerAddressForm — crear domicilio desde el checkout
// ---------------------------------------------------------------------------

interface CustomerAddressFormProps {
  customerId: string;
  branchId: string;
  legacyAddressReference: string;
  onSaved: (addr: PosCustomerAddress) => void;
  onCancel: () => void;
}

function CustomerAddressForm({
  customerId,
  branchId,
  legacyAddressReference,
  onSaved,
  onCancel,
}: CustomerAddressFormProps) {
  const [form, setForm] = useState({
    alias: '',
    street: '',
    exterior_number: '',
    interior_number: '',
    neighborhood: '',
    postal_code: '',
    city: '',
    municipality: '',
    state: '',
    cross_streets: '',
    references: '',
    delivery_instructions: '',
    is_default: false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (key: keyof typeof form, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async () => {
    const required = ['alias', 'street', 'exterior_number', 'neighborhood', 'postal_code', 'city', 'municipality', 'state'];
    if (required.some((f) => !String(form[f as keyof typeof form]).trim())) {
      setError('Completa todos los campos obligatorios.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await fetchApi<PosCustomerAddress>(
        `/customers/${encodeURIComponent(customerId)}/addresses`,
        { method: 'POST', body: JSON.stringify({ ...form, branch_id: branchId }) },
      );
      onSaved(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('No se pudo guardar el domicilio.');
      }
    } finally {
      setSaving(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 12px',
    borderRadius: 6,
    border: '1px solid #d1d5db',
    fontSize: '0.9rem',
    boxSizing: 'border-box',
  };

  return (
    <div style={{ marginTop: 8, padding: 12, border: '1px solid #e2e8f0', borderRadius: 8, display: 'grid', gap: 8 }}>
      <input placeholder="Alias (ej. Casa)" value={form.alias} onChange={(e) => set('alias', e.target.value)} style={inputStyle} />
      <input placeholder="Calle" value={form.street} onChange={(e) => set('street', e.target.value)} style={inputStyle} />
      <div style={{ display: 'flex', gap: 8 }}>
        <input placeholder="No. exterior" value={form.exterior_number} onChange={(e) => set('exterior_number', e.target.value)} style={inputStyle} />
        <input placeholder="No. interior (opcional)" value={form.interior_number} onChange={(e) => set('interior_number', e.target.value)} style={inputStyle} />
      </div>
      <input placeholder="Colonia" value={form.neighborhood} onChange={(e) => set('neighborhood', e.target.value)} style={inputStyle} />
      <input placeholder="Código postal" value={form.postal_code} onChange={(e) => set('postal_code', e.target.value)} style={inputStyle} />
      <input placeholder="Ciudad" value={form.city} onChange={(e) => set('city', e.target.value)} style={inputStyle} />
      <input placeholder="Municipio" value={form.municipality} onChange={(e) => set('municipality', e.target.value)} style={inputStyle} />
      <input placeholder="Estado" value={form.state} onChange={(e) => set('state', e.target.value)} style={inputStyle} />
      <input placeholder="Entre calles (opcional)" value={form.cross_streets} onChange={(e) => set('cross_streets', e.target.value)} style={inputStyle} />
      <input placeholder="Referencias (opcional)" value={form.references} onChange={(e) => set('references', e.target.value)} style={inputStyle} />
      {legacyAddressReference && form.references !== legacyAddressReference && (
        <button
          type="button"
          onClick={() => set('references', legacyAddressReference)}
          style={{ justifySelf: 'start', padding: '6px 10px', border: '1px solid #10b981', borderRadius: 6, background: '#fff', color: '#047857', cursor: 'pointer' }}
        >
          Copiar domicilio heredado a Referencias
        </button>
      )}
      <textarea
        placeholder="Instrucciones de entrega (opcional)"
        value={form.delivery_instructions}
        onChange={(e) => set('delivery_instructions', e.target.value)}
        style={{ ...inputStyle, minHeight: 64, resize: 'vertical' }}
      />
      <label style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 4 }}>
        <input type="checkbox" checked={form.is_default} onChange={(e) => set('is_default', e.target.checked)} />
        Marcar como predeterminado
      </label>
      {error && <div style={{ color: '#dc2626', fontSize: '0.85rem' }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => void submit()} disabled={saving} style={{ flex: 1, padding: '8px', borderRadius: 6, border: 'none', background: '#10b981', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
          {saving ? 'Guardando…' : 'Guardar domicilio'}
        </button>
        <button onClick={onCancel} style={{ padding: '8px 16px', borderRadius: 6, border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer' }}>
          Cancelar
        </button>
      </div>
    </div>
  );
}

export default PointOfSale;
