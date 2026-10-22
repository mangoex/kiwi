/** Validator for the closed, bundled projection schemas (never accepts remote schemas).
 * Unsupported schema keywords fail closed rather than silently relaxing a contract.
 */
interface Schema {
  $ref?:string; $defs?:Record<string,Schema>; $schema?:string; title?:string; description?:string;
  type?:string; const?:unknown; enum?:unknown[]; default?:unknown; anyOf?:Schema[];
  properties?:Record<string,Schema>; required?:string[]; additionalProperties?:boolean;
  items?:Schema; minItems?:number; maxItems?:number; minLength?:number; maxLength?:number;
  minimum?:number; maximum?:number; exclusiveMinimum?:number; exclusiveMaximum?:number;
  pattern?:string; format?:string;
}
const keywords=new Set(['$ref','$defs','$schema','title','description','type','const','enum','default','anyOf','properties','required','additionalProperties','items','minItems','maxItems','minLength','maxLength','minimum','maximum','exclusiveMinimum','exclusiveMaximum','pattern','format']);
export function assertProjectionContract(value:unknown, bundledSchema:object):void {
  const root=bundledSchema as Schema;
  function valid(data:unknown,schema:Schema):boolean {
    if(Object.keys(schema).some(key=>!keywords.has(key))) throw new Error('Contrato no compatible.');
    if(schema.$ref) {
      if(!schema.$ref.startsWith('#/$defs/')) throw new Error('Referencia de contrato no compatible.');
      const target=root.$defs?.[schema.$ref.slice(8)];
      if(!target) throw new Error('Referencia de contrato ausente.');
      return valid(data,target);
    }
    if('const' in schema && data!==schema.const) return false;
    if(schema.enum && !schema.enum.includes(data)) return false;
    if(schema.anyOf && !schema.anyOf.some(option=>valid(data,option))) return false;
    if(schema.type==='null') return data===null;
    if(schema.type==='boolean') return typeof data==='boolean';
    if(schema.type==='string') {
      if(typeof data!=='string' || (schema.minLength!==undefined && data.length<schema.minLength)
        || (schema.maxLength!==undefined && data.length>schema.maxLength)
        || (schema.pattern && !new RegExp(schema.pattern).test(data))) return false;
      if(schema.format==='date-time') return Number.isFinite(Date.parse(data)) && /T.*(Z|[+-]\d\d:\d\d)$/.test(data);
      if(schema.format==='date') return /^\d{4}-\d{2}-\d{2}$/.test(data) && Number.isFinite(Date.parse(data)) && new Date(data).toISOString().slice(0,10)===data;
      if(schema.format && schema.format!=='date-time') throw new Error('Formato de contrato no compatible.');
      return true;
    }
    if(schema.type==='integer' || schema.type==='number') return typeof data==='number' && Number.isFinite(data)
      && (schema.type!=='integer' || Number.isSafeInteger(data))
      && (schema.minimum===undefined || data>=schema.minimum) && (schema.maximum===undefined || data<=schema.maximum)
      && (schema.exclusiveMinimum===undefined || data>schema.exclusiveMinimum) && (schema.exclusiveMaximum===undefined || data<schema.exclusiveMaximum);
    if(schema.type==='array') return Array.isArray(data) && Boolean(schema.items)
      && (schema.minItems===undefined || data.length>=schema.minItems) && (schema.maxItems===undefined || data.length<=schema.maxItems)
      && data.every(item=>valid(item,schema.items!));
    if(schema.type==='object') {
      if(!data || typeof data!=='object' || Array.isArray(data) || schema.additionalProperties!==false) return false;
      const row=data as Record<string,unknown>, properties=schema.properties || {};
      return (schema.required || []).every(key=>Object.hasOwn(row,key))
        && Object.keys(row).every(key=>Object.hasOwn(properties,key) && valid(row[key],properties[key]));
    }
    if(schema.type!==undefined) throw new Error('Tipo de contrato no compatible.');
    return Boolean(schema.anyOf || 'const' in schema || schema.enum);
  }
  if(!valid(value,root)) throw new Error('Respuesta fuera del contrato autorizado.');
}
