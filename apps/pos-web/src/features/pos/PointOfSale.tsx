import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Modal } from '@restaurantos/ui';
import { fetchApi, ApiError } from '@restaurantos/api-client';
import { ShoppingBag, Search, Plus, Minus, Coffee, CupSoda, Sandwich, Salad, Wheat, Package, Utensils, Menu as MenuIcon, Users, MapPin, X } from 'lucide-react';
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

interface ModifierOption { id: string; name: string; effect_type: string; price_delta_cents: number; kitchen_text: string; }
interface ModifierGroup { id: string; name: string; minimum_selections: number; maximum_selections: number; options: ModifierOption[]; }
interface SelectedModifier { option_id: string; option_name: string; price_delta_cents: number; text?: string; }

interface PosCustomerAddress {
  id: string;
  alias: string;
  street: string;
  exterior_number: string;
  neighborhood: string;
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
  const [isCategoriesCollapsed, setCategoriesCollapsed] = useState(false);
  const [isPaymentOpen, setPaymentOpen] = useState(false);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [modifierProduct, setModifierProduct] = useState<Product | null>(null);
  const [modifierGroups, setModifierGroups] = useState<ModifierGroup[]>([]);
  const [modifierSelections, setModifierSelections] = useState<Record<string, string[]>>({});
  const [modifierText, setModifierText] = useState<Record<string, string>>({});
  const [modifierError, setModifierError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const [ownerName, setOwnerName] = useState('');
  const [orderType, setOrderType] = useState('dine-in');
  const [customerSearch, setCustomerSearch] = useState('');
  const [searchResults, setSearchResults] = useState<PosCustomer[]>([]);
  const [searchingCustomers, setSearchingCustomers] = useState(false);
  const [customerSearchError, setCustomerSearchError] = useState('');
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

  // Búsqueda remota de clientes con debounce y AbortController
  useEffect(() => {
    const query = customerSearch.trim();
    if (!branchId || query.length < 2) {
      setSearchResults([]);
      setSearchingCustomers(false);
      setCustomerSearchError('');
      return undefined;
    }
    setSearchingCustomers(true);
    setCustomerSearchError('');
    // Cancelar solicitud anterior
    if (searchControllerRef.current) {
      searchControllerRef.current.abort();
    }
    const controller = new AbortController();
    searchControllerRef.current = controller;
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({
        branch_id: branchId,
        q: query,
        limit: '20',
      });
      fetchApi<PosCustomerPage>(`/customers?${params.toString()}`, {
        signal: controller.signal,
      })
        .then((page) => {
          setSearchResults(page.items || []);
          setSearchingCustomers(false);
        })
        .catch((err) => {
          if (err instanceof DOMException && err.name === 'AbortError') return;
          setCustomerSearchError('No fue posible buscar clientes.');
          setSearchingCustomers(false);
        });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [customerSearch, branchId]);

  const selectCustomer = useCallback((customer: PosCustomer) => {
    setSelectedCustomer(customer);
    setOwnerName(customer.name || '');
    setCustomerSearch('');
    setSearchResults([]);
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
    setCustomerSearch('');
    setSearchResults([]);
    setShowAddressForm(false);
  }, []);

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

  const selectProduct = async (product: Product) => {
    try {
      const groups = await fetchApi<ModifierGroup[]>(
        `/products/${product.id}/modifiers?branch_id=${encodeURIComponent(branchId)}`,
      );
      if (!Array.isArray(groups) || groups.length === 0) {
        addToCart(product);
        return;
      }
      setModifierProduct(product);
      setModifierGroups(groups);
      setModifierSelections({});
      setModifierText({});
      setModifierError('');
    } catch {
      addToCart(product);
    }
  };

  const toggleModifier = (group: ModifierGroup, optionId: string) => {
    setModifierSelections((current) => {
      const selected = current[group.id] || [];
      if (selected.includes(optionId)) return { ...current, [group.id]: selected.filter((id) => id !== optionId) };
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
    setModifierProduct(null);
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
          body: JSON.stringify({ amount_cents: orderData.total_cents, method: 'cash' }),
        });
      } catch (payErr) {
        const msg = payErr instanceof ApiError ? payErr.message : 'Error desconocido';
        alert(`Orden creada, pero el pago falló: ${msg}`);
        return;
      }
      alert(`¡Venta finalizada! Orden #${orderData.folio}`);
      setCart([]);
      setPaymentOpen(false);
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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', backgroundColor: '#f0f2f5', overflow: 'hidden' }}>
      
      {/* Top Navigation Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px', background: 'white', borderBottom: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button 
            onClick={() => setCategoriesCollapsed(!isCategoriesCollapsed)}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <MenuIcon size={24} color="#64748b" />
          </button>
          <div style={{ color: '#10b981', fontWeight: 800, fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>🥝</span> <span style={{ color: '#1e293b' }}>Kiwi POS</span>
          </div>
        </div>

        <div style={{ width: '400px', position: 'relative' }}>
          <div style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}>
            <Search size={20} />
          </div>
          <input 
            type="text" 
            placeholder="Buscar producto…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%', padding: '12px 16px 12px 48px', borderRadius: 8, border: '1px solid #e2e8f0', background: 'white', fontSize: '1rem', outline: 'none', boxSizing: 'border-box' }} 
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center' }}>
           {/* Space for future icons or profile */}
           <div style={{ width: 40, height: 40, borderRadius: '50%', background: '#f1f5f9' }}></div>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* Left Category Sidebar */}
        <div style={{ 
          width: isCategoriesCollapsed ? '90px' : '140px', 
          background: 'white', 
          borderRight: '1px solid #e2e8f0', 
          display: 'flex', 
          flexDirection: 'column', 
          overflowY: 'auto',
          padding: '16px 0',
          transition: 'width 0.3s'
        }}>
          {categories.map(cat => {
            const isActive = activeCategory === cat;
            return (
              <div 
                key={cat}
                onClick={() => setActiveCategory(cat)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  padding: '16px 8px',
                  cursor: 'pointer',
                  position: 'relative',
                  background: isActive ? '#f8fafc' : 'transparent',
                }}
              >
                {isActive && (
                  <div style={{ position: 'absolute', left: 0, top: '20%', bottom: '20%', width: 4, background: '#10b981', borderRadius: '0 4px 4px 0' }} />
                )}
                <div style={{ 
                  color: isActive ? '#10b981' : '#64748b',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  {getProductIcon(cat, 32)}
                </div>
                {!isCategoriesCollapsed && (
                  <span style={{ fontSize: '0.85rem', fontWeight: isActive ? 600 : 500, color: isActive ? '#1e293b' : '#64748b', textAlign: 'center' }}>
                    {cat === 'Todas' ? 'Todo el menú' : cat}
                  </span>
                )}
              </div>
            )
          })}
        </div>

        {/* Center Products Area */}
        <div style={{ flex: 1, padding: 24, overflowY: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 20 }}>
            {loading ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>Cargando menú...</div>
            ) : catalogError ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#b91c1c', gridColumn: '1 / -1' }}>
                {catalogError}
              </div>
            ) : filteredProducts.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>No hay productos.</div>
            ) : (
              filteredProducts.map(product => (
                <div 
                  key={product.id} 
                  onClick={() => void selectProduct(product)}
                  style={{ 
                    background: 'white', borderRadius: 12, padding: 16, cursor: 'pointer', 
                    boxShadow: '0 2px 4px rgba(0,0,0,0.02)', display: 'flex', flexDirection: 'column', alignItems: 'center'
                  }}
                >
                  <div style={{ width: '100%', height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 12 }}>
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                    ) : (
                      getProductIcon(product.category, 64)
                    )}
                  </div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: '#1e293b', marginBottom: 4, textAlign: 'center' }}>{product.name}</div>
                  <div style={{ fontSize: '1rem', fontWeight: 500, color: '#64748b' }}>{formatCurrency(product.price)}</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Cart Area */}
        <div style={{ width: '400px', background: 'white', borderLeft: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', padding: 24, flexShrink: 0 }}>
          
          {/* Action Buttons Top */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12, marginBottom: 24 }}>
             <button onClick={() => setPaymentOpen(true)} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '16px', background: 'white', border: '1px solid #e2e8f0', borderRadius: 8, cursor: 'pointer', color: '#64748b' }}>
               <Users size={24} style={{ marginBottom: 8 }} />
               <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Cliente</span>
             </button>
          </div>

          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e293b', margin: '0 0 16px 0' }}>Detalle del pedido</h2>

          {/* Dine In / Take Away Toggle */}
          <div style={{ display: 'flex', background: '#f8fafc', borderRadius: 8, padding: 4, marginBottom: 24 }}>
            <button 
              onClick={() => setOrderType('dine-in')}
              style={{ flex: 1, padding: '8px', background: orderType === 'dine-in' ? 'white' : 'transparent', border: 'none', borderRadius: 6, fontWeight: 600, color: orderType === 'dine-in' ? '#10b981' : '#64748b', cursor: 'pointer', boxShadow: orderType === 'dine-in' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', borderBottom: orderType === 'dine-in' ? '2px solid #10b981' : 'none' }}
            >
              En sucursal
            </button>
            <button
              onClick={() => setOrderType('takeout')}
              style={{ flex: 1, padding: '8px', background: orderType === 'takeout' ? 'white' : 'transparent', border: 'none', borderRadius: 6, fontWeight: 600, color: orderType === 'takeout' ? '#10b981' : '#64748b', cursor: 'pointer', boxShadow: orderType === 'takeout' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', borderBottom: orderType === 'takeout' ? '2px solid #10b981' : 'none' }}
            >
              Para llevar
            </button>
            <button
              onClick={() => setOrderType('delivery')}
              style={{ flex: 1, padding: '8px', background: orderType === 'delivery' ? 'white' : 'transparent', border: 'none', borderRadius: 6, fontWeight: 600, color: orderType === 'delivery' ? '#10b981' : '#64748b', cursor: 'pointer', boxShadow: orderType === 'delivery' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', borderBottom: orderType === 'delivery' ? '2px solid #10b981' : 'none' }}
            >
              A domicilio
            </button>
          </div>

          {/* Cart Items */}
          <div style={{ flex: 1, overflowY: 'auto', marginBottom: 24 }}>
            {cart.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                <div style={{ width: 80, height: 80, borderRadius: '50%', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                  <ShoppingBag size={40} opacity={0.5} />
                </div>
                <h3 style={{ margin: '0 0 8px 0', color: '#1e293b' }}>Sin pedido</h3>
                <p style={{ margin: 0, fontSize: '0.85rem' }}>Toca un producto para agregarlo</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {cart.map(item => (
                  <div key={item.lineId} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 48, height: 48, borderRadius: 8, background: '#f8fafc', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      {item.image_url ? (
                        <img src={item.image_url} alt={item.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                      ) : (
                        getProductIcon(item.category, 24)
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#1e293b', marginBottom: 4 }}>{item.name}</div>
                      <div style={{ fontSize: '0.85rem', color: '#64748b' }}>{formatCurrency(item.price)}</div>
                      {item.modifiers.map((modifier) => <div key={modifier.option_id} style={{ fontSize: '0.72rem', color: '#059669' }}>+ {modifier.text || modifier.option_name}</div>)}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                       <div style={{ fontWeight: 600, color: '#1e293b' }}>{formatCurrency((item.price + item.modifierPrice) * item.quantity)}</div>
                       <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#f1f5f9', borderRadius: 4, padding: '2px 4px' }}>
                         <button onClick={() => updateQuantity(item.lineId, -1)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#64748b' }}><Minus size={14} /></button>
                         <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{item.quantity}</span>
                         <button onClick={() => updateQuantity(item.lineId, 1)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#64748b' }}><Plus size={14} /></button>
                       </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Totals & Process */}
          <div style={{ background: '#f8fafc', borderRadius: 12, padding: 16, marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, color: '#64748b', fontSize: '0.9rem' }}>
              <span>Subtotal</span>
              <span>{formatCurrency(subtotal)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, color: '#64748b', fontSize: '0.9rem' }}>
              <span>IVA incluido</span>
              <span>{formatCurrency(tax)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e2e8f0', paddingTop: 16, fontSize: '1.25rem', fontWeight: 800, color: '#1e293b' }}>
              <span>Total</span>
              <span>{formatCurrency(total)}</span>
            </div>
          </div>

          <button
            onClick={() => setPaymentOpen(true)}
            disabled={cart.length === 0}
            style={{
              width: '100%', padding: '16px', borderRadius: 8, border: 'none', fontSize: '1rem', fontWeight: 600,
              background: cart.length === 0 ? '#e2e8f0' : '#10b981',
              color: cart.length === 0 ? '#94a3b8' : 'white',
              cursor: cart.length === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            Finalizar venta
          </button>
        </div>
      </div>

      {/* Payment Modal */}
      <Modal isOpen={isPaymentOpen} onClose={() => setPaymentOpen(false)} title="Finalizar venta">
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
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>Buscar cliente</label>
            <input
              type="search"
              value={customerSearch}
              onChange={(e) => setCustomerSearch(e.target.value)}
              placeholder="Escribe al menos dos caracteres…"
              style={{ width: '100%', padding: '12px 16px', borderRadius: 12, border: '1px solid var(--glass-border)' }}
            />
            {searchingCustomers && <div style={{ color: '#64748b', fontSize: '0.85rem', marginTop: 8 }}>Buscando clientes…</div>}
            {customerSearchError && <div style={{ color: '#dc2626', fontSize: '0.85rem', marginTop: 8 }}>{customerSearchError}</div>}
            {!searchingCustomers && !customerSearchError && customerSearch.trim().length >= 2 && searchResults.length === 0 && (
              <div style={{ color: '#64748b', fontSize: '0.85rem', marginTop: 8 }}>No se encontraron clientes.</div>
            )}
            {searchResults.length > 0 && (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {searchResults.map((c) => {
                  const phone = c.phones?.[0]?.captured_number || c.phones?.[0]?.normalized_number || '';
                  const addrCount = (c.addresses || []).filter((a) => a.status === 'active').length;
                  return (
                    <button
                      key={c.id}
                      onClick={() => selectCustomer(c)}
                      style={{ textAlign: 'left', padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff', cursor: 'pointer' }}
                    >
                      <div style={{ fontWeight: 600 }}>{c.name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                        {phone && <span>{phone} · </span>}
                        {addrCount} domicilio(s)
                      </div>
                    </button>
                  );
                })}
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
              <select
                value={selectedAddressId}
                onChange={(e) => setSelectedAddressId(e.target.value)}
                style={{ width: '100%', padding: '12px 16px', borderRadius: 12, border: '1px solid var(--glass-border)' }}
              >
                <option value="">Selecciona un domicilio</option>
                {activeAddresses.map((a) => (
                  <option key={a.id} value={a.id}>{a.alias} · {a.street} {a.exterior_number}</option>
                ))}
              </select>
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
        <button
          onClick={() => void processTransaction()}
          disabled={!canCheckout}
          style={{ width: '100%', padding: '16px', borderRadius: 8, border: 'none', fontSize: '1rem', fontWeight: 600, background: canCheckout ? '#10b981' : '#e2e8f0', color: canCheckout ? 'white' : '#94a3b8', cursor: canCheckout ? 'pointer' : 'not-allowed' }}
        >
          Confirmar y pagar {formatCurrency(total)}
        </button>
      </Modal>

      <Modal isOpen={Boolean(modifierProduct)} onClose={() => setModifierProduct(null)} title={`Personalizar ${modifierProduct?.name || ''}`}>
        <div style={{ display: 'grid', gap: 18, maxHeight: '60vh', overflowY: 'auto' }}>
          {modifierGroups.map((group) => <section key={group.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}><strong>{group.name}</strong><small>{group.minimum_selections > 0 ? `Obligatorio · ${group.minimum_selections}-${group.maximum_selections}` : `Hasta ${group.maximum_selections}`}</small></div>
            <div style={{ display: 'grid', gap: 8 }}>{group.options.map((option) => {
              const checked = (modifierSelections[group.id] || []).includes(option.id);
              return <div key={option.id} style={{ padding: 10, border: `1px solid ${checked ? '#10b981' : '#e2e8f0'}`, borderRadius: 8 }}>
                <label style={{ display: 'flex', justifyContent: 'space-between', cursor: 'pointer' }}><span><input type={group.maximum_selections === 1 ? 'radio' : 'checkbox'} checked={checked} onChange={() => toggleModifier(group, option.id)} /> {option.name}</span><span>{option.price_delta_cents ? `+${formatCurrency(option.price_delta_cents / 100)}` : ''}</span></label>
                {checked && option.effect_type === 'instruction' && <input value={modifierText[option.id] || ''} onChange={(event) => setModifierText({ ...modifierText, [option.id]: event.target.value })} placeholder="Instrucción para cocina" maxLength={240} style={{ width: '100%', marginTop: 8, padding: 8, boxSizing: 'border-box' }} />}
              </div>;
            })}</div>
          </section>)}
          {modifierError && <div style={{ color: '#b91c1c' }}>{modifierError}</div>}
          <button onClick={confirmModifiers} style={{ padding: 14, border: 0, borderRadius: 8, background: '#10b981', color: 'white', fontWeight: 700 }}>Agregar al pedido</button>
        </div>
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
