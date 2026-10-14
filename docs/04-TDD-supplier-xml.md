# TDD de la frontera XML de proveedor

## TDD-TS-144 XML de proveedor

### TDD-TC-392 Parser sintáctico seguro y acotado

BDD-SC-689: bytes benignos/UTF-16, entrada inválida, DTD interno/externo y expansión, PI,
profundidad/elementos/atributos/texto, motor incompatible. Refutar con acceso a red/archivo
instrumentado y mensajes sin payload. Los límites se prueban a ambos lados cuando corresponde.
El parser no certifica XSD/UUID/RFC, cifrado, deduplicación, locks, API o importación transaccional;
estos gates se agregarán a X01 antes de afirmar su terminación. Sin cambios SQL en esta capa.
CI Docker debe comprobar carga/parseo benigno y rechazo DTD UTF-8/UTF-16 dentro de las dos imágenes
API construidas; un build sin ejecutar el parser no acredita compatibilidad del libexpat empaquetado.

### TDD-TC-393 Identidad declarada y original

BDD-SC-690: root/namespace/version, cardinalidad directa, receptor explícito/incompatible,
UUID mal formado/canónico, DTO congelado con unverified fijo, original SHA256 distinto ante cambio
de bytes sin mutar entrada. Identidad declarada no es verificación SAT ni permiso de razón social.
