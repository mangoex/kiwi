/**
 * Realistic Product Image Mapper
 * Maps real Kiwi catalog items to high-resolution realistic culinary photography.
 */

function resolveImg(relativePath: string): string {
  // If already absolute URL (http:// or https://)
  if (relativePath.startsWith('http://') || relativePath.startsWith('https://')) {
    return relativePath;
  }
  const clean = relativePath.replace(/^\/+/, '');
  // Using relative path './images/...' works seamlessly with Vite base './'
  return `./${clean}`;
}

const RAW_IMAGE_MAP: Record<string, string> = {
  // Direct SKU matches
  'JUG-VER': 'images/products/jugo_verde.jpg',
  'EXT-VER': 'images/products/jugo_verde.jpg',
  'EXT-ROJ': 'images/products/extracto_rojo.jpg',
  'JUG-ANT': 'images/products/extracto_rojo.jpg',
  'SHO-JEN': 'images/products/jugo_verde.jpg',
  'SMO-ROS': 'images/products/smoothie_rosa.jpg',
  'SMO-FRE': 'images/products/smoothie_rosa.jpg',
  'SMO-CAC': 'images/products/smoothie_rosa.jpg',
  'SMO-PRO': 'images/products/smoothie_rosa.jpg',
  'MAT-PIN': 'images/products/maccha_pinku.jpg',
  'MAT-SHI': 'images/products/maccha_pinku.jpg',
  'CAF-LAT': 'images/products/maccha_pinku.jpg',
  'CAF-LAT-FRE': 'images/products/maccha_pinku.jpg',
  'CAF-SOL': 'images/products/maccha_pinku.jpg',
  'ENS-FRU': 'images/products/ensalada_frutos.jpg',
  'ENS-MAN': 'images/products/ensalada_frutos.jpg',
  'ENS-CHE': 'images/products/ensalada_frutos.jpg',
  'SAN-KYO-BBQ': 'images/products/sando_kyoto.jpg',
  'EMP-POL': 'images/products/sando_kyoto.jpg',
  'PAN-CUE': 'images/products/cuernito_jamon.jpg',
  'PAN-BAG': 'images/products/cuernito_jamon.jpg',
  'PAN-BIS': 'images/products/cuernito_jamon.jpg',
  'COM-LIG': 'images/products/cuernito_jamon.jpg',
  'COM-PRE': 'images/products/sando_kyoto.jpg',
};

export function getProductImage(product: { sku?: string; name?: string; category_name?: string; image_url?: string }): string {
  if (product.image_url && product.image_url.trim() !== '') {
    return resolveImg(product.image_url);
  }
  if (product.sku && RAW_IMAGE_MAP[product.sku]) {
    return resolveImg(RAW_IMAGE_MAP[product.sku]);
  }

  const nameLower = (product.name || '').toLowerCase();
  const catLower = (product.category_name || '').toLowerCase();

  if (nameLower.includes('verde') || nameLower.includes('apio') || nameLower.includes('nopal')) {
    return resolveImg('images/products/jugo_verde.jpg');
  }
  if (nameLower.includes('rojo') || nameLower.includes('betabel') || nameLower.includes('anemia')) {
    return resolveImg('images/products/extracto_rojo.jpg');
  }
  if (nameLower.includes('smoothie') || nameLower.includes('rosa') || nameLower.includes('fresa')) {
    return resolveImg('images/products/smoothie_rosa.jpg');
  }
  if (nameLower.includes('matcha') || nameLower.includes('maccha') || nameLower.includes('latte') || nameLower.includes('café') || nameLower.includes('cafe')) {
    return resolveImg('images/products/maccha_pinku.jpg');
  }
  if (nameLower.includes('ensalada') || nameLower.includes('frutos') || nameLower.includes('salad')) {
    return resolveImg('images/products/ensalada_frutos.jpg');
  }
  if (nameLower.includes('sando') || nameLower.includes('sandwich') || nameLower.includes('emparedado') || nameLower.includes('pollo')) {
    return resolveImg('images/products/sando_kyoto.jpg');
  }
  if (nameLower.includes('cuernito') || nameLower.includes('pan') || nameLower.includes('baguette') || nameLower.includes('bisquet') || nameLower.includes('combo')) {
    return resolveImg('images/products/cuernito_jamon.jpg');
  }
  if (catLower.includes('jugo') || catLower.includes('extracto')) {
    return resolveImg('images/products/jugo_verde.jpg');
  }
  if (catLower.includes('ensalada')) {
    return resolveImg('images/products/ensalada_frutos.jpg');
  }
  if (catLower.includes('sando') || catLower.includes('emparedado')) {
    return resolveImg('images/products/sando_kyoto.jpg');
  }
  if (catLower.includes('smoothie')) {
    return resolveImg('images/products/smoothie_rosa.jpg');
  }
  if (catLower.includes('café') || catLower.includes('matcha')) {
    return resolveImg('images/products/maccha_pinku.jpg');
  }

  return resolveImg('images/products/jugo_verde.jpg');
}

export function getProductNutritionMeta(productName: string): { calories: string; prep_time: string; tag: string } {
  const name = productName.toLowerCase();
  if (name.includes('jugo') || name.includes('extracto') || name.includes('shot')) {
    return { calories: '120 kcal', prep_time: '5-8 min', tag: 'Cold Pressed' };
  }
  if (name.includes('smoothie')) {
    return { calories: '260 kcal', prep_time: '6-10 min', tag: 'Energizante' };
  }
  if (name.includes('matcha') || name.includes('latte') || name.includes('café')) {
    return { calories: '140 kcal', prep_time: '4-7 min', tag: 'Especialidad' };
  }
  if (name.includes('ensalada')) {
    return { calories: '320 kcal', prep_time: '10-15 min', tag: 'Gourmet' };
  }
  if (name.includes('sando') || name.includes('emparedado')) {
    return { calories: '480 kcal', prep_time: '12-15 min', tag: 'Chef Choice' };
  }
  if (name.includes('cuernito') || name.includes('pan')) {
    return { calories: '290 kcal', prep_time: '3-5 min', tag: 'Artesanal' };
  }
  return { calories: '180 kcal', prep_time: '5-10 min', tag: 'Fresco' };
}
