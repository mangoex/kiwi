# WorkOS + MCP de RestaurantOS

Esta guía prepara el primer canary de sólo lectura con WorkOS AuthKit/Connect. No autoriza aplicar
variables en Easypanel, ejecutar la migración, desplegar ni habilitar producción. No copies API keys,
client secrets, access tokens o refresh tokens en el repositorio, tickets, logs o payloads de Kiwi.

## 1. Contrato del primer canary

- WorkOS emite el token; Kiwi sólo valida JWT/JWKS y no necesita `WORKOS_API_KEY`.
- El resource indicator y audience deben ser la URL pública exacta `https://<host>/mcp`.
- El scope mínimo es `restaurantos:mcp.read`; `openid` no lo sustituye.
- El flujo inicial es Authorization Code con PKCE. M2M queda fuera porque su audience de WorkOS no
  representa el resource indicator por aplicación.
- Kiwi enlaza el tuple exacto `(iss, client_id, sub)` con una identidad interna. `org_id` de WorkOS
  no concede organización, perfil, capacidades ni sucursales en Kiwi.
- El vínculo no almacena tokens. Crear, reemplazar o revocar un vínculo deshabilita la identidad
  hasta que un administrador revise y reactive su política.

Referencias oficiales: [WorkOS MCP](https://workos.com/docs/authkit/mcp),
[claims de tokens](https://workos.com/docs/authkit/connect/token-claims) y
[token Connect](https://workos.com/docs/reference/workos-connect/token).

## 2. Preparar WorkOS

1. Configura un dominio AuthKit HTTPS para el ambiente canary.
2. En **Connect → Configuration**, habilita CIMD. Habilita DCR porque Grok y clientes similares
   pueden usar registro dinámico cuando no conocen un client ID previamente.
3. Registra `https://<host>/mcp` como Resource Indicator y como recurso default para clientes que no
   envíen `resource`.
4. Solicita a WorkOS que `restaurantos:mcp.read` sea scope default del ambiente para clientes
   CIMD/DCR, o asígnalo al cliente registrado. No habilites Kiwi si el token canary no contiene ese
   scope.
5. Conserva estos valores no secretos:

   - issuer: `https://<dominio-authkit>` (usa exactamente el valor publicado, sin `/` final)
   - JWKS: `https://<dominio-authkit>/oauth2/jwks`
   - resource: `https://<host>/mcp`

## 3. Variables de Kiwi, todavía con MCP apagado

Preparar no equivale a aplicar. En una ventana de configuración autorizada, los nombres esperados
son:

```text
RESTAURANTOS_GROKBOT_AGENT_TOOLS_ENABLED=true
RESTAURANTOS_MCP_ENABLED=false
RESTAURANTOS_MCP_ISSUER_URL=https://<dominio-authkit>
RESTAURANTOS_MCP_JWKS_URL=https://<dominio-authkit>/oauth2/jwks
RESTAURANTOS_MCP_RESOURCE_SERVER_URL=https://<host>/mcp
RESTAURANTOS_MCP_REQUIRED_SCOPE=restaurantos:mcp.read
```

Agent Tools en producción también exige Redis y su secreto HMAC de rate limit. Esos secretos se
gestionan en el proveedor de despliegue, nunca en Git. El arranque debe conservar
`RESTAURANTOS_MCP_ENABLED=false` hasta completar migración, vínculo, pruebas y aprobación de canary.

## 4. Obtener el tuple sin entregar el token a Kiwi

1. Agrega el MCP público en Grok o el cliente compatible e inicia **Connect/OAuth**.
2. Completa AuthKit. La primera llamada puede quedar denegada porque aún no existe vínculo interno;
   eso es fail-closed esperado.
3. En WorkOS, identifica la aplicación/cliente creado por CIMD o DCR y el usuario autenticado.
4. Copia únicamente el issuer, el `client_id` público y el ID de usuario usado como `sub`. Si hace
   falta inspeccionar el JWT canary, hazlo en una estación autorizada y descártalo; nunca lo pegues
   en la API de configuración ni en logs.

## 5. Vincular y reactivar la identidad

Con una sesión humana que tenga `admin.manage`, consulta primero
`GET /api/v1/integrations/grokbot/config` y toma la versión vigente del perfil. Luego ejecuta:

```http
PUT /api/v1/integrations/grokbot/identities/administrator/oauth-binding
Authorization: Bearer <sesion-humana>
Content-Type: application/json

{
  "issuer": "https://<dominio-authkit>",
  "subject": "<workos-user-id>",
  "client_id": "<workos-oauth-client-id>",
  "expected_authorization_version": 1
}
```

La respuesta sólo muestra los últimos cuatro caracteres de `subject` y deja la identidad inactiva.
Revisa capacidades y sucursales, y reactívala con el endpoint de política existente usando la nueva
`authorization_version`. Para revocar sólo este mecanismo:

```http
POST /api/v1/integrations/grokbot/identities/administrator/oauth-binding/revoke
Authorization: Bearer <sesion-humana>
Content-Type: application/json

{"expected_authorization_version": 2}
```

No uses una sesión humana como bearer de `/mcp` y no reutilices el mismo tuple para dos identidades.

## 6. Canary y criterios de salida

Después de autorización separada para migración, configuración y despliegue:

1. Verifica `/.well-known/oauth-protected-resource/mcp`, issuer, JWKS, audience y scope.
2. Habilita sólo el perfil Administrador, una sucursal y capacidades de lectura no sensibles.
3. Confirma `tools/list`, `context` y una lectura conocida; compara su resultado con Agent Tools REST.
4. Niega otra sucursal, otra herramienta, otro `client_id` y un token sin scope.
5. Revoca el vínculo y confirma que la siguiente llamada deja de resolver.
6. Observa errores, rate limit y logs redactados antes de ampliar el canary.

Limitación actual: esta revisión permite un vínculo OAuth por cada uno de los cuatro perfiles
existentes. Grok y Rakazo no deben compartir simultáneamente el mismo perfil. El aislamiento de dos
bots con el mismo perfil requiere la migración multibot de fase B definida en MCP-001; no se considera
resuelto por este paquete.
