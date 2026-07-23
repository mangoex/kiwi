import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Modal } from '@restaurantos/ui';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { ShoppingBag, Search, Plus, Minus, Coffee, CupSoda, Sandwich, Salad, Wheat, Package, Utensils, Users, X, Check, Banknote, CreditCard, Landmark, ChevronRight } from 'lucide-react';
import { usePosSession } from '../../session';

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
  price: number;
  description: string;
  station: string;
  image_url?: string;
}

interface CartItem extends Product {
  lineId: string;
  quantity: number;
  modifiers: SelectedModifier[];
  modifierPrice: number;
}

interface ModifierOption { id: string; name: string; effect_type: string; price_delta_cents: number; kitchen_text: string; variation_kind?: 'ingredient_extra'; variation_id?: string; action?: 'add'; }
interface ModifierGroup { id: string; name: string; minimum_selections: number; maximum_selections: number; options: ModifierOption[]; }
interface SelectedModifier { option_id: string; option_name: string; price_delta_cents: number; text?: string; }

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
            .filter((p: any) => p.status === 'active' && p.is_available !== false && Number(p.price_cents) > 0)
            .map((p: any) => ({
              id: p.id,
              name: p.name,
              sku: p.sku,
              category: p.category_name,
              price: p.price_cents / 100,
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

  const addToCart = (product: Product, modifiers: SelectedModifier[] = []) => {
    setCart(prev => {
      const existing = modifiers.length === 0 ? prev.find(item => item.id === product.id && item.modifiers.length === 0) : undefined;
      if (existing) {
        return prev.map(item => item.lineId === existing.lineId ? { ...item, quantity: item.quantity + 1 } : item);
      }
      return [...prev, {
        ...product,
        lineId: crypto.randomUUID(),
        quantity: 1,
        modifiers,
        modifierPrice: modifiers.reduce((sum, modifier) => sum + modifier.price_delta_cents / 100, 0),
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
    addToCart(modifierProduct, selected);
    resetModifierModal();
  };

  const updateQuantity = (lineId: string, delta: number) => {
    setCart(prev => prev.map(item => {
      if (item.lineId === lineId) {
        const newQty = item.quantity + delta;
        return newQty > 0 ? { ...item, quantity: newQty } : item;
      }
      return item;
    }).filter(item => item.quantity > 0));
  };

  const processTransaction = async () => {
    const registerId = localStorage.getItem('pos_register_id') || 'CAJA-01';
    if (!paymentMethod) return;
    if (!branchId) {
      alert('No hay sucursal asignada para este POS. Inicia sesión de nuevo o configura la sucursal.');
      return;
    }

    const payload = {
      owner_name: ownerName || 'Cliente General',
      customer_id: selectedCustomer?.id || undefined,
      delivery_address_id: selectedAddressId || undefined,
      order_type: orderType,
      branch_id: branchId || undefined,
      register_id: registerId || undefined,
      lines: cart.map((item) => ({
        product_id: item.id,
        quantity: item.quantity,
        notes: '',
        modifiers: item.modifiers.map((m) => ({ option_id: m.option_id, text: m.text })),
      })),
    };

    try {
      const orderData = await fetchApi<{ id: string; folio: string; total_cents: number }>(
        '/orders',
        { method: 'POST', body: JSON.stringify(payload) },
      );
      // Pago
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

  const subtotal = cart.reduce((sum, item) => sum + ((item.price + item.modifierPrice) * item.quantity), 0);
  const tax = 0;
  const total = subtotal + tax;
  const activeAddresses = (selectedCustomer?.addresses || []).filter((a) => a.status === 'active');
  const canCheckout = Boolean(
    orderType !== 'delivery' || (selectedCustomer && selectedAddressId),
  );

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(amount);
  };

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

          <div className="pos-sale-submenu">
            <div className="pos-sale-submenu-title"><span>Productos</span><strong>{activeCategory === 'Todas' ? 'Todos' : activeCategory}</strong></div>
            <div className="pos-sale-product-links">
              {filteredProducts.slice(0, 12).map((product) => (
                <button key={product.id} type="button" onClick={() => void selectProduct(product)}>{product.name}</button>
              ))}
            </div>
            <ChevronRight size={18} aria-hidden="true" />
          </div>

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
                    <strong>{formatCurrency(product.price)}</strong>
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
                                {option.name}{option.price_delta_cents > 0 ? ' +' + formatCurrency(option.price_delta_cents / 100) : ''}
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
            <button type="button" onClick={() => setPaymentOpen(true)}><Users size={19} /><span>{selectedCustomer?.name || 'Cliente'}</span></button>
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
                    <span>{formatCurrency(item.price)}</span>
                    {item.modifiers.map((modifier) => <small key={modifier.option_id}>+ {modifier.text || modifier.option_name}</small>)}
                  </div>
                  <div className="pos-sale-cart-controls">
                    <strong>{formatCurrency((item.price + item.modifierPrice) * item.quantity)}</strong>
                    <div>
                      <button type="button" onClick={() => updateQuantity(item.lineId, -1)} aria-label="Restar producto"><Minus size={14} /></button>
                      <span>{item.quantity}</span>
                      <button type="button" onClick={() => updateQuantity(item.lineId, 1)} aria-label="Sumar producto"><Plus size={14} /></button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="pos-sale-summary">
            <div><span>Subtotal</span><span>{formatCurrency(subtotal)}</span></div>
            <div><span>IVA incluido</span><span>{formatCurrency(tax)}</span></div>
            <div className="total"><strong>Total</strong><strong>{formatCurrency(total)}</strong></div>
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
            Pagar {cart.length > 0 ? formatCurrency(total) : ''}
          </button>
        </aside>
      </div>
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
        {orderType === 'delivery' && !canCheckout && (
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
            <strong>{formatCurrency(total)}</strong>
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
          disabled={!canCheckout || !paymentMethod}
          className="pos-payment-confirm"
        >
          {paymentMethod ? `Confirmar cobro · ${formatCurrency(total)}` : 'Selecciona un método de pago'}
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
