# RestaurantOS Harness

Repositorio base de especificación para construir en Codex una plataforma web, offline-first, para una cadena mexicana de restaurantes de comida rápida con siete sucursales y quince cajas.

## Objetivo

El repositorio separa producto, comportamiento, diseño y pruebas para evitar que el código se convierta en la única fuente de verdad.

La jerarquía documental es:

1. `docs/01-PRD.md`: qué debe resolver el producto y por qué.
2. `docs/02-SDD.md`: cómo debe diseñarse el sistema.
3. `docs/03-BDD.md`: cómo debe comportarse frente a usuarios y sistemas externos.
4. `docs/04-TDD.md`: cómo se verificará cada comportamiento.
5. `docs/05-matriz-trazabilidad.md`: relación entre requisito, comportamiento, diseño y prueba.
6. `docs/06-roadmap-entregas.md`: secuencia de construcción.
7. `docs/07-analisis-consistencia.md`: contradicciones, omisiones y riesgos detectados.
8. `docs/08-adrs-propuestas.md`: decisiones arquitectónicas propuestas para fase 0.
9. `docs/09-fase-0-y-vertical-slice.md`: alcance verificable de fase 0 y primer vertical slice.
10. `AGENTS.md`: instrucciones permanentes para Codex.
11. `codex/CODEX_IMPORT_PROMPT.md`: prompt inicial para importar este contexto a Codex.

## Regla principal

Ningún cambio funcional debe implementarse únicamente en código. Cada cambio debe actualizar, en este orden:

1. PRD, cuando cambie el alcance o el valor esperado.
2. SDD, cuando cambie la arquitectura, el modelo o las reglas técnicas.
3. BDD, cuando cambie un comportamiento observable.
4. TDD, cuando cambie la estrategia de verificación.
5. Matriz de trazabilidad.
6. Código y pruebas.

## Alcance de la versión 1

Incluye:

- Operación POS y caja.
- Pedidos de mostrador, para recoger y a domicilio.
- WhatsApp, chatbot y marketplaces.
- Cocina, bebidas, empaque y entrega.
- Inventarios, recetas, subrecetas y producción por lotes.
- Costeo promedio y costo estándar.
- Compras, XML de CFDI y cuentas por pagar.
- Repartidores propios y optimización simultánea de rutas.
- Operación offline mediante gateway local por sucursal.
- Impresión automática en Windows.
- Exportación configurable hacia CONTPAQi.
- Facturación individual y global mediante exportación.

No incluye inicialmente:

- Mesas, meseros o reservaciones.
- Facturación CFDI directa.
- Pago en línea.
- Aplicación móvil del repartidor.
- Operación multiempresa comercial abierta al mercado.
- Producción centralizada.

## Arquitectura resumida

```text
Nube central
├── Web admin
├── API central
├── PostgreSQL
├── Redis
├── Workers
├── Integraciones
├── Optimización de rutas
└── Reportes y exportaciones

Sucursal
├── Gateway Windows
├── SQLite local
├── Servicio de impresión
├── POS web/PWA
├── KDS cocina
├── KDS bebidas
├── KDS empaque
└── Pantalla de entrega
```

## Convención de identificadores

- `PRD-FR-xxx`: requisito funcional.
- `PRD-NFR-xxx`: requisito no funcional.
- `SDD-ADR-xxx`: decisión arquitectónica.
- `BDD-FEAT-xxx`: feature BDD.
- `BDD-SC-xxx`: escenario.
- `TDD-TS-xxx`: suite de pruebas.
- `TDD-TC-xxx`: caso de prueba.
- `RISK-xxx`: riesgo.
- `OPEN-xxx`: decisión abierta.

## Uso inicial

1. Crear un repositorio privado en GitHub.
2. Copiar esta estructura al repositorio.
3. Ejecutar el prompt de `codex/CODEX_IMPORT_PROMPT.md`.
4. Pedir a Codex que valide la trazabilidad antes de escribir código.
5. Construir primero la fase 1 descrita en `docs/06-roadmap-entregas.md`.

## Bootstrap técnico

Fase 0 incluye scaffold mínimo para:

- API FastAPI con health checks en `apps/api`.
- Apps React + TypeScript + Vite para admin, POS y KDS.
- Placeholders de `worker` y `edge-gateway`.
- Contratos JSON Schema en `packages/contracts`.
- Docker Compose local en `infra/docker`.
- Plantilla Easypanel en `infra/easypanel`.
- CI en GitHub Actions.
- Pruebas de arquitectura y trazabilidad en `tests/architecture`.
- `Dockerfile` en la raíz para desplegar la API directamente desde Easypanel.

Comandos iniciales:

```bash
python -m pip install -r apps/api/requirements-dev.txt
python -m pytest
docker compose -f infra/docker/docker-compose.yml config
```
