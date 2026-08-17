export interface Product {
  id: string;
  name: string;
  sku: string;
  category_name?: string;
  category_id?: string;
  price_cents: number;
  description?: string;
  station?: string;
  image_url?: string;
  calories?: string;
  prep_time?: string;
  tags?: string[];
  is_available?: boolean;
}

export interface Category {
  id: string;
  name: string;
  icon?: string;
  display_order?: number;
}

export interface CartItem {
  cart_id: string;
  product: Product;
  quantity: number;
  notes?: string;
  line_total_cents: number;
}

export type OrderType = 'takeaway' | 'delivery' | 'dine-in';
export type PaymentMethod = 'cash' | 'card' | 'transfer';

export interface CustomerOrderInfo {
  name: string;
  phone: string;
  order_type: OrderType;
  address_street: string;
  address_number: string;
  address_neighborhood: string;
  address_notes: string;
  payment_method: PaymentMethod;
  cash_amount?: string;
  order_notes?: string;
}

export interface CreatedOrderResult {
  folio: string;
  id: string;
  created_at: string;
  customer_info: CustomerOrderInfo;
  items: CartItem[];
  total_cents: number;
  whatsapp_url: string;
}
