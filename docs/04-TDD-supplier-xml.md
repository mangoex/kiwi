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

### TDD-TC-394 Original cifrado y comando idempotente

BDD-SC-691: original/UTF16/1MiB, AES-GCM/AAD/hash/tamaño, key ausente/rotación, no texto plano,
replay y conflicto de key/cuerpo/UUID; conflicto append-only y rollback tras cada inserción/auditoría.
COMMIT ejecutado con acuse perdido se recupera desde una Session nueva sin duplicar efectos.

### TDD-TC-395 Descarga y privacidad

BDD-SC-692: scoped metadata/attachment, actor revocado/config-only/otra branch/org, branch inactiva
asignada/corporativo, bytes/hash exactos, tampering/AAD/intercambio de evidencia, auditoría falla
sin bytes; respuesta/auditoría/log sin RFC/XML/secretos, incluyendo StatementError con parámetros.
Resolve acepta header/cuerpo vacío, rechaza JSON sin eco; UUID inválido tampoco refleja input.
Cipher fiscal64KiB y fixtures originales siguen verdes.

### TDD-TC-396 Autoridad y concurrencia real

BDD-SC-693: preflight antes de lectura, MIME/compresión/size/deadline/UTF16DTD negativos;
contexto cambiado durante upload y dos imports UUID/key concurrentes. Instrumentar operaciones SQL
de rutas async: se ejecutan fuera del event loop, sin compartir Session simultáneamente.
PostgreSQL debe observar
locks reales de importación frente a selección/revocación y conservar cero efectos contables.

### TDD-TC-397 Migración e historia

BDD-SC-694: upgrade/downgrade vacío SQLite/PostgreSQL desde0091, FKs scopes/hash/estado/unique,
downgrade bloqueado con historia y mismas filas tras el intento. Integrar módulo PG obligatorio
en CI/collection/JUnit, ausenciaURL gate no aprobado; no apagar otras suites ni relajar verifier.
