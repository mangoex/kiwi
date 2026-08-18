import React, { useState, useEffect, useMemo } from 'react';
import { Product, Category, CartItem, CustomerOrderInfo, OrderType, CreatedOrderResult } from './types';
import { fetchMobileMenu, submitMobileOrder } from './api';
import { Header } from './components/Header';
import { CategoryStories } from './components/CategoryStories';
import { SizeSelectorFilter } from './components/SizeSelectorFilter';
import { ProductCard } from './components/ProductCard';
import { ProductModal } from './components/ProductModal';
import { CartDrawer } from './components/CartDrawer';
import { OrderSuccessModal } from './components/OrderSuccessModal';
import { FavoritesView } from './components/FavoritesView';
import { BottomNav, NavTab } from './components/BottomNav';
import { FloatingCartBar } from './components/FloatingCartBar';
import { getCategoryCover, detectProductSize } from './imageMap';

export const App: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategoryId, setActiveCategoryId] = useState<string>('all');
  const [activeSize, setActiveSize] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [orderType, setOrderType] = useState<OrderType>('takeaway');

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

  // Load catalog on mount
  useEffect(() => {
    let isMounted = true;
    fetchMobileMenu().then(({ products: prods, categories: cats }) => {
      if (isMounted) {
        setProducts(prods);
        setCategories(cats);
        setLoading(false);
      }
    });
    return () => { isMounted = false; };
  }, []);

  // Save favorites & cart to localStorage
  useEffect(() => {
    localStorage.setItem('kiwi_liked_products', JSON.stringify(Array.from(likedProductIds)));
  }, [likedProductIds]);

  useEffect(() => {
    localStorage.setItem('kiwi_mobile_cart', JSON.stringify(cart));
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
  const handleAddToCart = (product: Product, quantity: number, notes?: string) => {
    setCart((prev) => {
      const existingIndex = prev.findIndex(
        (item) => item.product.id === product.id && item.notes === (notes || '')
      );
      if (existingIndex > -1) {
        const updated = [...prev];
        const current = updated[existingIndex];
        const newQty = current.quantity + quantity;
        updated[existingIndex] = {
          ...current,
          quantity: newQty,
          line_total_cents: newQty * product.price_cents,
        };
        return updated;
      } else {
        const newItem: CartItem = {
          cart_id: `${product.id}-${Date.now()}`,
          product,
          quantity,
          notes: notes || '',
          line_total_cents: quantity * product.price_cents,
        };
        return [...prev, newItem];
      }
    });
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
              line_total_cents: newQty * item.product.price_cents,
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

  // Submit Order (Hybrid: System + WhatsApp)
  const handleSubmitOrder = async (info: CustomerOrderInfo) => {
    setIsSubmittingOrder(true);
    try {
      const totalCents = cart.reduce((acc, item) => acc + item.line_total_cents, 0);
      const result = await submitMobileOrder(info, cart, totalCents);
      setCreatedOrderResult(result);
      setCart([]);
      setIsCartOpen(false);
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  // Extract available sizes in current category
  const availableSizes = useMemo(() => {
    const sizeSet = new Set<string>();
    products.forEach((p) => {
      if (activeCategoryId !== 'all' && activeCategoryId !== '') {
        const selectedCat = categories.find((c) => c.id === activeCategoryId);
        if (selectedCat && p.category_name !== selectedCat.name) {
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
  }, [products, categories, activeCategoryId]);

  // Filtered Products
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      // Category filter
      if (activeCategoryId !== 'all' && activeCategoryId !== '') {
        const selectedCat = categories.find((c) => c.id === activeCategoryId);
        if (selectedCat && p.category_name !== selectedCat.name) {
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
  }, [products, categories, activeCategoryId, activeSize, searchQuery]);

  const favoriteProducts = useMemo(() => {
    return products.filter((p) => likedProductIds.has(p.id));
  }, [products, likedProductIds]);

  const totalCartCount = cart.reduce((sum, item) => sum + item.quantity, 0);
  const totalCartCents = cart.reduce((sum, item) => sum + item.line_total_cents, 0);

  const currentCategory = categories.find((c) => c.id === activeCategoryId);
  const categoryCoverImg = currentCategory && currentCategory.id !== 'all'
    ? getCategoryCover(currentCategory.name)
    : null;

  return (
    <>
      <Header
        orderType={orderType}
        onToggleOrderType={setOrderType}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {currentTab === 'explore' && (
        <main className="main-content-layout">
          {/* Stories Category Selector */}
          <CategoryStories
            categories={categories}
            activeCategoryId={activeCategoryId}
            onSelectCategory={setActiveCategoryId}
          />

          {/* Category Banner if specific category selected */}
          {categoryCoverImg && currentCategory && (
            <div className="category-hero-card">
              <img
                src={categoryCoverImg}
                alt={currentCategory.name}
                className="category-hero-bg"
                loading="lazy"
              />
              <div className="category-hero-overlay">
                <span className="category-hero-badge">Categoría</span>
                <h1 className="category-hero-title">{currentCategory.name}</h1>
                <p className="category-hero-count">{filteredProducts.length} productos disponibles</p>
              </div>
            </div>
          )}

          {/* Size Filter Bar */}
          <SizeSelectorFilter
            availableSizes={availableSizes}
            activeSize={activeSize}
            onSelectSize={setActiveSize}
          />

          {/* Feed Content */}
          <div className="feed-container">
            <div className="section-title-bar">
              <h2>
                {searchQuery ? `Resultados para "${searchQuery}"` : (
                  activeCategoryId === 'all'
                    ? 'Todo el Menú'
                    : (currentCategory?.name || 'Menú')
                )}
              </h2>
              <span className="section-count-badge">{filteredProducts.length}</span>
            </div>

            {loading ? (
              <div className="feed-loading-state">
                <div className="loading-spinner" />
                <p>Cargando menú fresco…</p>
              </div>
            ) : filteredProducts.length === 0 ? (
              <div className="feed-empty-state">
                <p className="empty-title">No encontramos productos en esta selección.</p>
                <button
                  type="button"
                  className="btn-reset-filters"
                  onClick={() => { setSearchQuery(''); setActiveCategoryId('all'); setActiveSize('all'); }}
                >
                  Ver todo el menú
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
                    onQuickAdd={(p) => handleAddToCart(p, 1)}
                  />
                ))}
              </div>
            )}
          </div>
        </main>
      )}

      {currentTab === 'favorites' && (
        <main>
          <FavoritesView
            favoriteProducts={favoriteProducts}
            likedProductIds={likedProductIds}
            onToggleLike={handleToggleLike}
            onOpenDetail={setSelectedProduct}
            onQuickAdd={(p) => handleAddToCart(p, 1)}
            onExploreMenu={() => setCurrentTab('explore')}
          />
        </main>
      )}

      {/* Floating Cart Bar on Feed when cart has items */}
      {!isCartOpen && (
        <FloatingCartBar
          itemCount={totalCartCount}
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
          items={cart}
          orderType={orderType}
          onClose={() => setIsCartOpen(false)}
          onUpdateQuantity={handleUpdateCartQuantity}
          onRemoveItem={handleRemoveCartItem}
          onSubmitOrder={handleSubmitOrder}
          isSubmitting={isSubmittingOrder}
        />
      )}

      {/* Order Success & WhatsApp Modal */}
      {createdOrderResult && (
        <OrderSuccessModal
          orderResult={createdOrderResult}
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
    </>
  );
};
