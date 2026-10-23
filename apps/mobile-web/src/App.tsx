import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Product, Category, CartItem, CustomerOrderInfo, OrderType, CreatedOrderResult, BranchInfo, SelectedModifier } from './types';
import { fetchMobileMenu, submitMobileOrder, fetchPublicBranches } from './api';
import { HeroHeader } from './components/HeroHeader';
import { CategoryCircles } from './components/CategoryCircles';
import { SizeSelectorFilter } from './components/SizeSelectorFilter';
import { ProductCard } from './components/ProductCard';
import { ProductModal } from './components/ProductModal';
import { CartDrawer } from './components/CartDrawer';
import { OrderSuccessModal } from './components/OrderSuccessModal';
import { FavoritesView } from './components/FavoritesView';
import { BottomNav, NavTab } from './components/BottomNav';
import { FloatingCartBar } from './components/FloatingCartBar';
import { BranchSelectorModal } from './components/BranchSelectorModal';
import { detectProductSize } from './imageMap';
import { usePublicOrderTracking } from './hooks/usePublicOrderTracking';
import { ActiveOrderTracker } from './components/ActiveOrderTracker';
import { CustomerAccess, ProfileEditor, PhoneChange, PasswordChange } from './components/CustomerProfile';
import { CustomerProfile, customerRequest, CustomerAccessError, accessErrorMessage } from './customerProfile';

const EXCLUDED_CATEGORY_KEYWORDS = [
  'servicio a domicilio',
  'domicilio',
  'envio',
  'envío',
  'delivery',
  'extra',
  'extras',
  'adicional',
  'adicionales',
  'modificador',
  'modificadores',
];

function saveLocalPreference(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* Keep the current screen usable. */ }
}

function readLocalPreference(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

export const App: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategoryId, setActiveCategoryId] = useState<string>('');
  const [activeSize, setActiveSize] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [orderType, setOrderType] = useState<OrderType>('takeaway');
  const feedContainerRef = useRef<HTMLDivElement>(null);

  // Branch & GPS Geolocation state
  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<BranchInfo | null>(null);
  const [isBranchModalOpen, setIsBranchModalOpen] = useState(false);
  const [isLoadingLocation, setIsLoadingLocation] = useState(false);
  const [customerCoords, setCustomerCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [returnToCartAfterBranch, setReturnToCartAfterBranch] = useState(false);
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [profileBranchKey, setProfileBranchKey] = useState<string | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [accessError, setAccessError] = useState('');
  const [accessUnavailable, setAccessUnavailable] = useState(false);
  const [returnToCartAfterProfile, setReturnToCartAfterProfile] = useState(false);
  const [accessRevision, setAccessRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setProfile(null); setProfileBranchKey(null); setProfileLoading(true); setAccessError(''); setAccessUnavailable(false);
    const key = selectedBranch?.public_key;
    if (!key) { setProfileLoading(false); return; }
    customerRequest<CustomerProfile>(key, 'profile', undefined, 'GET').then(value => {
      if (active) { setProfile(value); setProfileBranchKey(key); }
    }).catch(error => {
      if (active && !(error instanceof CustomerAccessError && error.status === 401)) {
        setAccessError(accessErrorMessage(error)); setAccessUnavailable(true);
      }
    }).finally(() => { if (active) setProfileLoading(false); });
    return () => { active = false; };
  }, [selectedBranch?.public_key, accessRevision]);

  // Favorites state with localStorage
  const [likedProductIds, setLikedProductIds] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem('kiwi_liked_products');
      return saved ? new Set(JSON.parse(saved)) : new Set(['prod-jug-ver', 'prod-san-kyo']);
    } catch {
      return new Set();
    }
  });

  // Cart state with localStorage
  const [cart, setCart] = useState<CartItem[]>(() => {
    try {
      const saved = localStorage.getItem('kiwi_mobile_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Modals & Navigation state
  const [currentTab, setCurrentTab] = useState<NavTab>('explore');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [createdOrderResult, setCreatedOrderResult] = useState<CreatedOrderResult | null>(null);
  const [createdOrderBranchId, setCreatedOrderBranchId] = useState<string | undefined>();
  const [orderSubmitError, setOrderSubmitError] = useState<string | null>(null);
  const tracking = usePublicOrderTracking(selectedBranch?.id);
  const selectedBranchRef = useRef(selectedBranch?.id);
  selectedBranchRef.current = selectedBranch?.id;

  // Geolocation detector
  const detectLocationAndFetchBranches = useCallback((forceNearest = false) => {
    setIsLoadingLocation(true);

    const applyBranchSelection = (branchList: BranchInfo[], isGps: boolean) => {
      setBranches(branchList);
      setIsLoadingLocation(false);
      if (branchList.length > 0) {
        if (forceNearest && isGps) {
          // When user explicitly clicks GPS button, choose the nearest branch
          setSelectedBranch(branchList[0]);
          saveLocalPreference('kiwi_selected_branch_id', branchList[0].id);
        } else {
          const savedId = readLocalPreference('kiwi_selected_branch_id');
          const match = branchList.find((b) => b.id === savedId);
          setSelectedBranch(match || branchList[0]);
        }
      }
    };

    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          setCustomerCoords({ lat, lng });
          const branchList = await fetchPublicBranches(lat, lng);
          applyBranchSelection(branchList, true);
        },
        async (err) => {
          console.warn('High accuracy geolocation failed or denied, retrying fallback...', err);
          navigator.geolocation.getCurrentPosition(
            async (fallbackPos) => {
              const lat = fallbackPos.coords.latitude;
              const lng = fallbackPos.coords.longitude;
              setCustomerCoords({ lat, lng });
              const branchList = await fetchPublicBranches(lat, lng);
              applyBranchSelection(branchList, true);
            },
            async (fallbackErr) => {
              console.warn('Geolocation unavailable, loading default branches:', fallbackErr);
              const branchList = await fetchPublicBranches();
              applyBranchSelection(branchList, false);
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
          );
        },
        { enableHighAccuracy: true, timeout: 5000, maximumAge: 60000 }
      );
    } else {
      fetchPublicBranches().then((branchList) => {
        applyBranchSelection(branchList, false);
      });
    }
  }, []);

  // Load branches on mount; the catalog follows the selected branch key exactly.
  useEffect(() => {
    detectLocationAndFetchBranches(false);
  }, [detectLocationAndFetchBranches]);

  useEffect(() => {
    let isMounted = true;
    let requestVersion = 0;
    const loadCatalog = async (showLoading: boolean) => {
      const version = ++requestVersion;
      if (showLoading) setLoading(true);
      if (!profile?.complete || profileBranchKey !== selectedBranch?.public_key) {
        if (!isMounted || version !== requestVersion) return;
        setProducts([]);
        setCategories([]);
        setLoading(false);
        return;
      }
      try {
        const { products: prods, categories: cats } = await fetchMobileMenu(selectedBranch?.public_key, true);
        if (!isMounted || version !== requestVersion) return;
        setProducts(prods);
        setCategories(cats);
        setLoading(false);
      } catch (error: unknown) {
        if (!isMounted || version !== requestVersion) return;
        setLoading(false);
        const status = (error as { status?: number }).status;
        if (status === 401) {
          setProfile(null);
          setIsCartOpen(false);
        }
        setProducts([]);
        setCategories([]);
        if (status !== 401) setAccessUnavailable(true);
        setAccessError(status === 401
          ? 'Tu sesión venció. Inicia sesión para continuar.'
          : 'No pudimos cargar el menú. Reintenta en un momento.');
      }
    };
    const refreshVisibleCatalog = () => {
      if (document.visibilityState === 'visible') void loadCatalog(false);
    };
    void loadCatalog(true);
    document.addEventListener('visibilitychange', refreshVisibleCatalog);
    window.addEventListener('focus', refreshVisibleCatalog);
    return () => {
      isMounted = false;
      document.removeEventListener('visibilitychange', refreshVisibleCatalog);
      window.removeEventListener('focus', refreshVisibleCatalog);
    };
  }, [selectedBranch?.public_key, profile?.complete, profileBranchKey]);

  const handleSelectBranch = (branch: BranchInfo) => {
    setSelectedBranch(branch);
    saveLocalPreference('kiwi_selected_branch_id', branch.id);
    if (returnToCartAfterBranch) {
      setReturnToCartAfterBranch(false);
      setIsCartOpen(true);
    }
  };

  // Save favorites & cart to localStorage
  useEffect(() => {
    saveLocalPreference('kiwi_liked_products', JSON.stringify(Array.from(likedProductIds)));
  }, [likedProductIds]);

  useEffect(() => {
    saveLocalPreference('kiwi_mobile_cart', JSON.stringify(cart));
  }, [cart]);

  // Reset size filter when category changes
  useEffect(() => {
    setActiveSize('all');
  }, [activeCategoryId]);

  // Toggle Heart / Like
  const handleToggleLike = (productId: string) => {
    setLikedProductIds((prev) => {
      const next = new Set(prev);
      if (next.has(productId)) {
        next.delete(productId);
      } else {
        next.add(productId);
      }
      return next;
    });
  };

  // Add to Cart
  const handleAddToCart = (product: Product, quantity: number, notes?: string, modifiers: SelectedModifier[] = []) => {
    setCart((prev) => {
      const existingIndex = prev.findIndex(
        (item) => item.product.id === product.id
          && item.notes === (notes || '')
          && JSON.stringify(item.modifiers ?? []) === JSON.stringify(modifiers)
      );
      if (existingIndex > -1) {
        const updated = [...prev];
        const current = updated[existingIndex];
        const newQty = current.quantity + quantity;
        updated[existingIndex] = {
          ...current,
          quantity: newQty,
          line_total_cents: newQty * (product.price_cents + modifiers.reduce((sum, modifier) => sum + modifier.price_delta_cents, 0)),
        };
        return updated;
      } else {
        const newItem: CartItem = {
          cart_id: `${product.id}-${Date.now()}`,
          product,
          quantity,
          notes: notes || '',
          modifiers,
          line_total_cents: quantity * (product.price_cents + modifiers.reduce((sum, modifier) => sum + modifier.price_delta_cents, 0)),
        };
        return [...prev, newItem];
      }
    });
  };

  // Required catalog choices cannot be silently bypassed from the quick-add affordance.
  const handleQuickAddToCart = (product: Product) => {
    if ((product.modifier_groups ?? []).some((group) => group.minimum_selections > 0)) {
      setSelectedProduct(product);
      return;
    }
    handleAddToCart(product, 1);
  };

  const handleUpdateCartQuantity = (cartId: string, delta: number) => {
    setCart((prev) => {
      return prev
        .map((item) => {
          if (item.cart_id === cartId) {
            const newQty = item.quantity + delta;
            if (newQty <= 0) return null;
            return {
              ...item,
              quantity: newQty,
              line_total_cents: newQty * (item.product.price_cents + (item.modifiers ?? []).reduce((sum, modifier) => sum + modifier.price_delta_cents, 0)),
            };
          }
          return item;
        })
        .filter((item): item is CartItem => item !== null);
    });
  };

  const handleRemoveCartItem = (cartId: string) => {
    setCart((prev) => prev.filter((item) => item.cart_id !== cartId));
  };

  // Submit Order (Hybrid: System + WhatsApp with Branch & GPS)
  const handleSubmitOrder = async (info: CustomerOrderInfo) => {
    setIsSubmittingOrder(true);
    setOrderSubmitError(null);
    try {
      const result = await submitMobileOrder(
        info,
        cart,
        selectedBranch?.id,
        selectedBranch?.name,
        customerCoords || undefined,
        selectedBranch?.public_key,
        true,
      );
      if (result.kind === 'public_order_intent' && selectedBranch) {
        tracking.remember(result.public_reference, selectedBranch.id);
      }
      if (selectedBranchRef.current !== selectedBranch?.id) return;
      setCreatedOrderBranchId(selectedBranch?.id);
      setCreatedOrderResult(result);
      setCart([]);
      setIsCartOpen(false);
    } catch (err: unknown) {
      const errorObj = err as { status?: number; code?: string };
      let friendlyMessage = 'No fue posible confirmar el pedido. Conservamos tu carrito para que puedas reintentar.';
      if (errorObj?.status === 401) {
        setProfile(null); setIsCartOpen(false);
        setAccessError('Tu sesión venció. Verifica tu teléfono para continuar; tu carrito está guardado.');
      }
      if (errorObj?.code === 'mobile_delivery_profile_required') {
        friendlyMessage = 'Completa tu correo y domicilio desde Mi perfil para solicitar delivery.';
      } else if (errorObj?.code === 'product_unavailable') {
        friendlyMessage = 'Uno de los productos seleccionados no está disponible. Revisa tu carrito antes de reintentar.';
      } else if (errorObj?.code === 'public_order_rate_limited' || errorObj?.status === 429) {
        friendlyMessage = 'Demasiados intentos en poco tiempo. Conservamos tu carrito; espera un momento antes de reintentar.';
      }
      setOrderSubmitError(friendlyMessage);
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  // Filter visible categories: exclude empty categories, operational items, and the synthetic 'Todos' category
  const visibleCategories = useMemo(() => {
    return categories.filter((cat) => {
      const nameLower = (cat.name || '').toLowerCase().trim();
      if (cat.id === 'all' || nameLower === 'todos') return false;

      const isExcluded = EXCLUDED_CATEGORY_KEYWORDS.some((kw) => nameLower === kw || nameLower.includes(kw));
      if (isExcluded) return false;

      const count = products.filter((p) => p.category_name === cat.name || p.category_id === cat.id).length;
      return count > 0;
    });
  }, [categories, products]);

  // Ensure activeCategoryId stays valid among visible categories, defaulting to the first real category
  useEffect(() => {
    if (visibleCategories.length > 0) {
      const exists = visibleCategories.some((c) => c.id === activeCategoryId);
      if (!exists) {
        setActiveCategoryId(visibleCategories[0].id);
      }
    } else {
      setActiveCategoryId('');
    }
  }, [visibleCategories, activeCategoryId]);

  // Extract available sizes in current category
  const availableSizes = useMemo(() => {
    const sizeSet = new Set<string>();
    products.forEach((p) => {
      if (activeCategoryId) {
        const selectedCat = visibleCategories.find((c) => c.id === activeCategoryId);
        if (selectedCat && p.category_name !== selectedCat.name && p.category_id !== selectedCat.id) {
          return;
        }
      }
      const s = detectProductSize(p.name);
      if (s) sizeSet.add(s);
    });
    const order = ['CH', 'MED', 'GDE', '500ml', '1L'];
    return Array.from(sizeSet).sort((a, b) => {
      const idxA = order.indexOf(a);
      const idxB = order.indexOf(b);
      if (idxA !== -1 && idxB !== -1) return idxA - idxB;
      if (idxA !== -1) return -1;
      if (idxB !== -1) return 1;
      return a.localeCompare(b);
    });
  }, [products, visibleCategories, activeCategoryId]);

  const productsCountByCategory = useMemo(() => {
    const map: Record<string, number> = {};
    visibleCategories.forEach((cat) => {
      map[cat.id] = products.filter((p) => p.category_name === cat.name || p.category_id === cat.id).length;
    });
    return map;
  }, [visibleCategories, products]);

  // Handle clicking on category card -> smooth scroll down/up to feed
  const handleCategoryCardClick = useCallback((_categoryId: string) => {
    if (feedContainerRef.current) {
      feedContainerRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  // Filtered Products
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      // Category filter: always filter by active category
      if (activeCategoryId) {
        const selectedCat = visibleCategories.find((c) => c.id === activeCategoryId);
        if (selectedCat && p.category_name !== selectedCat.name && p.category_id !== selectedCat.id) {
          return false;
        }
      }
      // Size filter
      if (activeSize !== 'all') {
        const s = detectProductSize(p.name);
        if (s !== activeSize) return false;
      }
      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = p.name.toLowerCase().includes(q);
        const matchesDesc = (p.description || '').toLowerCase().includes(q);
        const matchesCat = (p.category_name || '').toLowerCase().includes(q);
        if (!matchesName && !matchesDesc && !matchesCat) return false;
      }
      return true;
    });
  }, [products, visibleCategories, activeCategoryId, activeSize, searchQuery]);

  const favoriteProducts = useMemo(() => {
    return products.filter((p) => likedProductIds.has(p.id));
  }, [products, likedProductIds]);

  const totalCartCount = cart.reduce((sum, item) => sum + item.quantity, 0);
  const totalCartCents = cart.reduce((sum, item) => sum + item.line_total_cents, 0);
  const currentCategory = visibleCategories.find((c) => c.id === activeCategoryId);

  const acceptProfile = (value: CustomerProfile) => {
    setProfile(value); setProfileBranchKey(selectedBranch?.public_key || null); setAccessError(''); setAccessUnavailable(false);
  };
  if (profileLoading || isLoadingLocation) {
    return <main className="customer-access"><p role="status">Preparando tu acceso a Kiwi…</p></main>;
  }
  if (!selectedBranch?.public_key) {
    return <main className="customer-access"><div className="customer-access-card"><h1>Kiwi</h1>
      <p role="alert">El acceso al menú no está disponible en esta sucursal por ahora.</p>
      <button onClick={() => detectLocationAndFetchBranches(false)}>Reintentar</button>
    </div></main>;
  }
  if (accessUnavailable) {
    return <main className="customer-access"><div className="customer-access-card customer-profile-form">
      <span className="customer-brand">🥝 Kiwi</span><h1>No pudimos preparar tu acceso</h1>
      <p role="alert">{accessError}</p>
      <button className="customer-primary" onClick={() => setAccessRevision(value => value + 1)}>Reintentar acceso</button>
    </div></main>;
  }
  if (!profile?.complete || profileBranchKey !== selectedBranch.public_key) {
    return <>{accessError && <p role="alert" className="customer-error">{accessError}</p>}
      <CustomerAccess key={selectedBranch.public_key} publicKey={selectedBranch.public_key} profile={profile} onSaved={acceptProfile} onSessionExpired={() => setProfile(null)} />
    </>;
  }

  return (
    <div className="mobile-app-shell">
      {accessError && currentTab !== 'profile' && <p role="alert">{accessError}</p>}
      {tracking.references.length > 0 && <div className="public-tracking-slot">
        <ActiveOrderTracker tracking={tracking} branchPhone={selectedBranch?.phone} />
      </div>}

      {currentTab === 'explore' && (
        <HeroHeader
          categories={visibleCategories}
          activeCategoryId={activeCategoryId}
          onSelectCategory={setActiveCategoryId}
          onCategoryCardClick={handleCategoryCardClick}
          productsCountByCategory={productsCountByCategory}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          selectedBranch={selectedBranch}
          onOpenBranchSelector={() => setIsBranchModalOpen(true)}
          onRefreshLocation={() => detectLocationAndFetchBranches(true)}
          isLoadingLocation={isLoadingLocation}
        />
      )}

      {currentTab === 'explore' && (
        <main className="mobile-main-content">
          {/* Circular Category Quick Scroll Bar (as in reference design) */}
          <CategoryCircles
            categories={visibleCategories}
            activeCategoryId={activeCategoryId}
            onSelectCategory={setActiveCategoryId}
            productsCountByCategory={productsCountByCategory}
          />

          {/* Size Filter Bar */}
          <SizeSelectorFilter
            availableSizes={availableSizes}
            activeSize={activeSize}
            onSelectSize={setActiveSize}
          />

          {/* Feed Content */}
          <div ref={feedContainerRef} className="feed-container" id="menu-feed">
            <div className="section-title-bar">
              <div className="section-title-wrapper">
                <span className="section-eyebrow">Selección de la casa</span>
                <h2>
                  {searchQuery ? `Resultados para "${searchQuery}"` : (
                    currentCategory?.name || 'Menú'
                  )}
                </h2>
              </div>
              <span className="section-count-badge">{filteredProducts.length}</span>
            </div>

            {loading ? (
              <div className="feed-loading-state">
                <div className="loading-spinner" />
                <p>Cargando menú fresco…</p>
              </div>
            ) : filteredProducts.length === 0 ? (
              <div className="feed-empty-state">
                <p className="empty-title">No encontramos productos con estos filtros.</p>
                <button
                  type="button"
                  className="btn-reset-filters"
                  onClick={() => {
                    setSearchQuery('');
                    if (visibleCategories.length > 0) setActiveCategoryId(visibleCategories[0].id);
                    setActiveSize('all');
                  }}
                >
                  Restablecer filtros
                </button>
              </div>
            ) : (
              <div className="product-items-grid">
                {filteredProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    isLiked={likedProductIds.has(product.id)}
                    onToggleLike={handleToggleLike}
                    onOpenDetail={setSelectedProduct}
                    onQuickAdd={handleQuickAddToCart}
                  />
                ))}
              </div>
            )}
          </div>
        </main>
      )}

      {currentTab === 'profile' && <main className="customer-profile-page">
        <ProfileEditor key={profile.id + profile.phone} publicKey={selectedBranch.public_key} profile={profile} onSessionExpired={() => setProfile(null)} onSaved={value => {
          acceptProfile(value);
          if (returnToCartAfterProfile) {
            setReturnToCartAfterProfile(false); setCurrentTab('explore'); setIsCartOpen(true);
          }
        }} />
        <PasswordChange publicKey={selectedBranch.public_key} hasPassword={profile.has_password ?? false} onSaved={acceptProfile} onSessionExpired={() => setProfile(null)} />
        {profile.has_password && <PhoneChange publicKey={selectedBranch.public_key} onSaved={acceptProfile} onSessionExpired={() => setProfile(null)} />}
        {accessError && <p role="alert">{accessError}</p>}
        <button type="button" onClick={async () => {
          try {
            await customerRequest(selectedBranch.public_key!, 'logout');
            setProfile(null); setCart([]); setIsCartOpen(false);
            tracking.references.forEach(ref => tracking.dismiss(ref.public_reference)); setCurrentTab('explore');
            setAccessRevision(value => value + 1);
          } catch (error) {
            if (error instanceof CustomerAccessError && error.status === 401) setProfile(null);
            setAccessError(accessErrorMessage(error));
          }
        }}>Cerrar sesión</button>
      </main>}

      {currentTab === 'favorites' && (
        <main className="mobile-main-content">
          <FavoritesView
            favoriteProducts={favoriteProducts}
            likedProductIds={likedProductIds}
            onToggleLike={handleToggleLike}
            onOpenDetail={setSelectedProduct}
            onQuickAdd={handleQuickAddToCart}
            onExploreMenu={() => setCurrentTab('explore')}
          />
        </main>
      )}

      {/* Floating Cart Bar on Feed when cart has items */}
      {!isCartOpen && currentTab !== 'profile' && (
        <FloatingCartBar
          totalCount={totalCartCount}
          totalCents={totalCartCents}
          onOpenCart={() => setIsCartOpen(true)}
        />
      )}

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductModal
          product={selectedProduct}
          isLiked={likedProductIds.has(selectedProduct.id)}
          onToggleLike={handleToggleLike}
          onClose={() => setSelectedProduct(null)}
          onAddToCart={handleAddToCart}
        />
      )}

      {/* Cart & Checkout Sheet */}
      {isCartOpen && (
        <CartDrawer
          profile={profile}
          onOrderTypeChange={setOrderType}
          onEditProfile={() => {
            setReturnToCartAfterProfile(true); setIsCartOpen(false); setCurrentTab('profile');
          }}
          items={cart}
          allProducts={products}
          orderType={orderType}
          selectedBranch={selectedBranch}
          onOpenBranchSelector={() => {
            setReturnToCartAfterBranch(true);
            setIsCartOpen(false);
            setIsBranchModalOpen(true);
          }}
          onClose={() => setIsCartOpen(false)}
          onUpdateQuantity={handleUpdateCartQuantity}
          onRemoveItem={handleRemoveCartItem}
          onQuickAddProduct={handleQuickAddToCart}
          onSubmitOrder={handleSubmitOrder}
          isSubmitting={isSubmittingOrder}
          submitError={orderSubmitError}
        />
      )}

      {/* Branch Selector Modal */}
      <BranchSelectorModal
        isOpen={isBranchModalOpen}
        onClose={() => setIsBranchModalOpen(false)}
        branches={branches}
        selectedBranchId={selectedBranch?.id || null}
        onSelectBranch={handleSelectBranch}
        onRefreshLocation={() => detectLocationAndFetchBranches(true)}
        isLoadingLocation={isLoadingLocation}
      />

      {/* Order Success & WhatsApp Modal */}
      {createdOrderResult && createdOrderBranchId === selectedBranch?.id && (
        <OrderSuccessModal
          orderResult={createdOrderResult}
          branch={selectedBranch}
          tracking={tracking}
          onClose={() => setCreatedOrderResult(null)}
          onNewOrder={() => setCreatedOrderResult(null)}
        />
      )}

      {/* Bottom Navigation */}
      <BottomNav
        currentTab={currentTab}
        onSelectTab={(tab) => {
          if (tab === 'cart') {
            setIsCartOpen(true);
          } else {
            setCurrentTab(tab);
          }
        }}
        cartCount={totalCartCount}
        favoritesCount={likedProductIds.size}
      />
    </div>
  );
};

export default App;
