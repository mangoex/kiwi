/**
 * Realistic Product Image Mapper (Bundled Static Assets)
 * Maps real Kiwi catalog items to high-resolution realistic culinary photography.
 */

import jugoVerdeImg from './assets/products/jugo_verde.jpg';
import smoothieRosaImg from './assets/products/smoothie_rosa.jpg';
import macchaPinkuImg from './assets/products/maccha_pinku.jpg';
import ensaladaFrutosImg from './assets/products/ensalada_frutos.jpg';
import sandoKyotoImg from './assets/products/sando_kyoto.jpg';
import cuernitoJamonImg from './assets/products/cuernito_jamon.jpg';
import extractoRojoImg from './assets/products/extracto_rojo.jpg';

const SKU_IMAGE_MAP: Record<string, string> = {
  // Direct SKU matches
  'JUG-VER': jugoVerdeImg,
  'EXT-VER': jugoVerdeImg,
  'EXT-ROJ': extractoRojoImg,
  'JUG-ANT': extractoRojoImg,
  'SHO-JEN': jugoVerdeImg,
  'SMO-ROS': smoothieRosaImg,
  'SMO-FRE': smoothieRosaImg,
  'SMO-CAC': smoothieRosaImg,
  'SMO-PRO': smoothieRosaImg,
  'MAT-PIN': macchaPinkuImg,
  'MAT-SHI': macchaPinkuImg,
  'CAF-LAT': macchaPinkuImg,
  'CAF-LAT-FRE': macchaPinkuImg,
  'CAF-SOL': macchaPinkuImg,
  'ENS-FRU': ensaladaFrutosImg,
  'ENS-MAN': ensaladaFrutosImg,
  'ENS-CHE': ensaladaFrutosImg,
  'SAN-KYO-BBQ': sandoKyotoImg,
  'EMP-POL': sandoKyotoImg,
  'PAN-CUE': cuernitoJamonImg,
  'PAN-BAG': cuernitoJamonImg,
  'PAN-BIS': cuernitoJamonImg,
  'COM-LIG': cuernitoJamonImg,
  'COM-PRE': sandoKyotoImg,
};

export function getProductImage(product: { sku?: string; name?: string; category_name?: string; image_url?: string }): string {
  if (product.image_url && product.image_url.trim() !== '') {
    return product.image_url;
  }
  if (product.sku && SKU_IMAGE_MAP[product.sku]) {
    return SKU_IMAGE_MAP[product.sku];
  }

  const nameLower = (product.name || '').toLowerCase();
  const catLower = (product.category_name || '').toLowerCase();

  if (nameLower.includes('verde') || nameLower.includes('apio') || nameLower.includes('nopal')) {
    return jugoVerdeImg;
  }
  if (nameLower.includes('rojo') || nameLower.includes('betabel') || nameLower.includes('anemia')) {
    return extractoRojoImg;
  }
  if (nameLower.includes('smoothie') || nameLower.includes('rosa') || nameLower.includes('fresa')) {
    return smoothieRosaImg;
  }
  if (nameLower.includes('matcha') || nameLower.includes('maccha') || nameLower.includes('latte') || nameLower.includes('café') || nameLower.includes('cafe')) {
    return macchaPinkuImg;
  }
  if (nameLower.includes('ensalada') || nameLower.includes('frutos') || nameLower.includes('salad')) {
    return ensaladaFrutosImg;
  }
  if (nameLower.includes('sando') || nameLower.includes('sandwich') || nameLower.includes('emparedado') || nameLower.includes('pollo')) {
    return sandoKyotoImg;
  }
  if (nameLower.includes('cuernito') || nameLower.includes('pan') || nameLower.includes('baguette') || nameLower.includes('bisquet') || nameLower.includes('combo')) {
    return cuernitoJamonImg;
  }
  if (catLower.includes('jugo') || catLower.includes('extracto')) {
    return jugoVerdeImg;
  }
  if (catLower.includes('ensalada')) {
    return ensaladaFrutosImg;
  }
  if (catLower.includes('sando') || catLower.includes('emparedado')) {
    return sandoKyotoImg;
  }
  if (catLower.includes('smoothie')) {
    return smoothieRosaImg;
  }
  if (catLower.includes('café') || catLower.includes('matcha')) {
    return macchaPinkuImg;
  }

  return jugoVerdeImg;
}

export function getCategoryCover(categoryName: string): string {
  const cat = (categoryName || '').toLowerCase();
  if (cat.includes('ensalada')) return ensaladaFrutosImg;
  if (cat.includes('sando') || cat.includes('sandwich') || cat.includes('emparedado') || cat.includes('baguette')) return sandoKyotoImg;
  if (cat.includes('smoothie') || cat.includes('licuado') || cat.includes('bowl')) return smoothieRosaImg;
  if (cat.includes('café') || cat.includes('cafe') || cat.includes('matcha') || cat.includes('latte')) return macchaPinkuImg;
  if (cat.includes('pan') || cat.includes('croissant') || cat.includes('cuernito') || cat.includes('repostería')) return cuernitoJamonImg;
  if (cat.includes('agua') || cat.includes('bebida') || cat.includes('refresco')) return extractoRojoImg;
  if (cat.includes('jugo') || cat.includes('extracto') || cat.includes('shot')) return jugoVerdeImg;
  return jugoVerdeImg;
}

export function getCategoryIcon(categoryName: string): string {
  const cat = (categoryName || '').toLowerCase();
  if (cat.includes('ensalada')) return '🥗';
  if (cat.includes('sando') || cat.includes('sandwich') || cat.includes('emparedado') || cat.includes('baguette')) return '🥪';
  if (cat.includes('smoothie') || cat.includes('licuado')) return '🍓';
  if (cat.includes('café') || cat.includes('cafe') || cat.includes('matcha')) return '🍵';
  if (cat.includes('pan') || cat.includes('croissant') || cat.includes('cuernito')) return '🥐';
  if (cat.includes('agua') || cat.includes('bebida')) return '💧';
  if (cat.includes('jugo') || cat.includes('extracto')) return '🥤';
  if (cat.includes('postre') || cat.includes('dulce')) return '🍰';
  if (cat.includes('combo') || cat.includes('paquete')) return '🍱';
  if (cat.includes('extra') || cat.includes('adicional')) return '✨';
  return '🥝';
}

export function detectProductSize(productName: string): string | null {
  const upper = productName.toUpperCase().trim();
  if (/(?:\s+|\()(?:GDE|GRANDE|GD|LARGE|L)(?:\)|\s*$)/i.test(upper)) return 'GDE';
  if (/(?:\s+|\()(?:MED|MEDIANO|MEDIANA|MD|MEDIUM|M)(?:\)|\s*$)/i.test(upper)) return 'MED';
  if (/(?:\s+|\()(?:CH|CHICO|CHICA|CHI|SMALL|S)(?:\)|\s*$)/i.test(upper)) return 'CH';
  if (/(?:\s+|\()(?:1L|1\s*LITRO|LITRO|LT)(?:\)|\s*$)/i.test(upper)) return '1L';
  if (/(?:\s+|\()(?:500ML|1\/2L|1\/2\s*LITRO|MEDIO\s*LITRO)(?:\)|\s*$)/i.test(upper)) return '500ml';
  return null;
}

export function cleanBaseProductName(productName: string): string {
  return productName
    .replace(/(?:\s+|\()(?:GDE|GRANDE|GD|MED|MEDIANO|MEDIANA|MD|CH|CHICO|CHICA|CHI|1L|1\s*LITRO|LITRO|LT|500ML|1\/2L|1\/2\s*LITRO|MEDIO\s*LITRO)(?:\)|\s*$)/gi, '')
    .trim();
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

export interface ProductIconMeta {
  emoji: string;
  badgeLabel: string;
  bgGradient: string;
  borderColor: string;
  textColor: string;
}

export function getProductIconMeta(product: { sku?: string; name?: string; category_name?: string }): ProductIconMeta {
  const name = (product.name || '').toLowerCase();
  const cat = (product.category_name || '').toLowerCase();
  const sku = (product.sku || '').toUpperCase();

  if (cat.includes('ensalada') || name.includes('ensalada') || sku.startsWith('ENS')) {
    return {
      emoji: '🥗',
      badgeLabel: 'Ensalada',
      bgGradient: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)',
      borderColor: '#a7f3d0',
      textColor: '#047857',
    };
  }

  if (cat.includes('smoothie') || name.includes('smoothie') || sku.startsWith('SMO') || name.includes('bowl')) {
    return {
      emoji: '🍓',
      badgeLabel: 'Smoothie',
      bgGradient: 'linear-gradient(135deg, #fdf2f8 0%, #fce7f3 100%)',
      borderColor: '#fbcfe8',
      textColor: '#be185d',
    };
  }

  if (cat.includes('sando') || cat.includes('sandwich') || name.includes('sando') || name.includes('sandwich') || name.includes('emparedado') || name.includes('baguette') || sku.startsWith('SAN') || sku.startsWith('EMP')) {
    return {
      emoji: '🥪',
      badgeLabel: 'Sándwich',
      bgGradient: 'linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%)',
      borderColor: '#fed7aa',
      textColor: '#c2410c',
    };
  }

  if (cat.includes('pan') || cat.includes('croissant') || name.includes('cuernito') || name.includes('bisquet') || name.includes('croissant') || sku.startsWith('PAN')) {
    return {
      emoji: '🥐',
      badgeLabel: 'Panadería',
      bgGradient: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
      borderColor: '#fde68a',
      textColor: '#b45309',
    };
  }

  if (cat.includes('café') || cat.includes('cafe') || cat.includes('matcha') || name.includes('matcha') || name.includes('latte') || name.includes('café') || name.includes('cafe') || sku.startsWith('CAF') || sku.startsWith('MAT')) {
    return {
      emoji: '🍵',
      badgeLabel: 'Café & Té',
      bgGradient: 'linear-gradient(135deg, #f0fdfa 0%, #ccfbf1 100%)',
      borderColor: '#99f6e4',
      textColor: '#0f766e',
    };
  }

  if (cat.includes('jugo') || cat.includes('extracto') || name.includes('jugo') || name.includes('extracto') || name.includes('shot') || sku.startsWith('JUG') || sku.startsWith('EXT') || sku.startsWith('SHO')) {
    return {
      emoji: '🥤',
      badgeLabel: 'Jugo / Extracto',
      bgGradient: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
      borderColor: '#bbf7d0',
      textColor: '#15803d',
    };
  }

  if (cat.includes('agua') || cat.includes('bebida') || name.includes('agua')) {
    return {
      emoji: '💧',
      badgeLabel: 'Bebida',
      bgGradient: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)',
      borderColor: '#bfdbfe',
      textColor: '#1d4ed8',
    };
  }

  if (cat.includes('postre') || name.includes('pastel') || name.includes('galleta') || name.includes('dulce')) {
    return {
      emoji: '🍰',
      badgeLabel: 'Postre',
      bgGradient: 'linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%)',
      borderColor: '#fecdd3',
      textColor: '#be123c',
    };
  }

  if (cat.includes('combo') || name.includes('combo') || name.includes('paquete') || sku.startsWith('COM')) {
    return {
      emoji: '🍱',
      badgeLabel: 'Combo',
      bgGradient: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
      borderColor: '#e9d5ff',
      textColor: '#7e22ce',
    };
  }

  return {
    emoji: '🥝',
    badgeLabel: 'Especialidad',
    bgGradient: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
    borderColor: '#bbf7d0',
    textColor: '#15803d',
  };
}
