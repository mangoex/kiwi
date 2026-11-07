# Memoria Operativa Canónica — Kiwi RestaurantOS (`MEMORY.md`)

> **Propósito:** Este archivo almacena el contexto vivo de producción, identificadores de sucursales, estado de inventarios, repositorios satelitales y recursos en Google Drive. Cualquier agente que inicie una sesión debe leer este documento para operar sin pedir de nuevo datos ya establecidos.

---

## 1. Entorno Productivo & Organización

- **Organización:** Kiwi Ensaladas / Kipan (`organization_id`: `018f6f73-2d0a-74f0-8f1c-000000000001`)
- **URL Base de Producción:** `https://kiwipos.mimenu.onl`
- **Administrador Corporativo:** Miguel Gonzalez (`mangoex@gmail.com`)
- **Repositorios en GitHub:**
  - **Monorepo Principal (`RestaurantOS`):** `https://github.com/mangoex/kiwi` (Rama principal: `main`)
  - **Suite Administrativa / Tablero Ejecutivo (Conectado a Vercel):** `https://github.com/mangoex/kiwi-dashboard` (Rama principal: `main`)
- **Carpeta Oficial en Google Drive (`Kiwi/`):**
  - **Folder ID:** `1VvOyaRqaFAI3jgtjmIsw0E8vWH81ATpX`
  - **URL:** `https://drive.google.com/drive/folders/1VvOyaRqaFAI3jgtjmIsw0E8vWH81ATpX`

---

## 2. Catálogo de las 7 Sucursales en Producción (Culiacán, Sinaloa)

| Código | Nombre de Sucursal | `branch_id` (UUID en PostgreSQL) | Dirección | Estado Actual en Base de Datos |
| :--- | :--- | :--- | :--- | :--- |
| **`SUC01`** | **Centro** | `a64252bf-9297-42a9-b2e2-ec30a2771ca1` | Álvaro Obregón Norte 698 | 1 turno de prueba (`CAJA-01`, $500) y 1 pedido de prueba (`SUC01-000001`, $260). Inventario en 0. |
| **`SUC02`** | **Guadalupe / Aeropuerto** | `5aeea33c-d247-4962-99af-ae4c9d9ca42e` | Culiacán, Sinaloa | Limpia para inicio de pruebas (0 ventas, 0 inventario). |
| **`SUC03`** | **Insurgentes** | `3a4bb054-7905-43f0-ba4d-bb647773f360` | Blvd. De los Insurgentes Sur 1205 | Limpia para inicio de pruebas (0 ventas, 0 inventario). |
| **`SUC04`** | **Chapultepec** | `b63c117d-85cf-4c83-8eba-c6321ff37a15` | Josefa Ortiz de Domínguez 598 | **Inventario Físico Inicial Aprobado** (`7988e017`): 102 insumos con existencia física real, 54 en saldo cero, 14 umbrales activos (9 críticos). 1 pedido de prueba (`SUC04-000001`, $170). |
| **`SUC05`** | **Cinepolis** | `8679ba6a-65a8-43e3-bcb7-6ce186b5ce98` | Blvd. Pedro Infante 1546 Int. 5 | Limpia para inicio de pruebas (0 ventas, 0 inventario). |
| **`SUC06`** | **La Primavera** | `6bf77697-8270-4cbc-b5a5-b389ba26e3af` | Calle Industrial 6 #37 | Limpia para inicio de pruebas (0 ventas, 0 inventario). |
| **`SUC07`** | **Constitución** | `dd271572-a918-4608-a19c-a2c284a4b8dc` | Álvaro Obregón Sur 576 B | Limpia para inicio de pruebas (0 ventas, 0 inventario). |

---

## 3. Estado del Inventario Físico y Almacén — Sucursal Chapultepec (`SUC04`)

- **Warehouse ID (Almacén Chapultepec):** `5bcb8d27-4cad-4b7a-870b-6e816d65f85a`
- **Sesión de Conteo Físico Inicial:** `7988e017-a331-4f4f-ada9-0bf8c0acee42`
  - **Estado:** `approved` (Aprobada en Kardex el `2026-11-07T07:59:17Z`).
  - **Total Catálogo de Insumos:** `156` SKUs registrados en PostgreSQL.
  - **Insumos Contados con Stock Positivo:** `102` insumos (provenientes de las 3 hojas físicas del 06/11/2026).
  - **Insumos en Saldo Cero (`0.000`):** `54` insumos (artículos de limpieza, bolsas/empaques secundarios y aderezos no preparados).
- **Los 14 Insumos con Umbral Configurado en Chapultepec:**
  - **🟢 En rango óptimo (4):** Aguacate (`4.336 kg`, mín 2 / máx 8), Agua Jamaica (`5 pza`, mín 5 / máx 15), Yogurth (`1.0 L`, mín 1 / máx 4).
  - **🔵 Sobre máximo (1):** Tortillas Integral (`18 pza`, mín 5 / máx 15).
  - **🔴 Bajo mínimo / Agotados (9 — Requieren compra o preparación):**
    1. `ACEITUNA NEGRA`: Físico `0.900 kg` (Mín `1.0` / Máx `3.0` -> Faltan `2.100 kg`).
    2. `AGUA MIRENAL`: Físico `8 pza` (Mín `10` / Máx `24` -> Faltan `16 pza`).
    3. `AGUA SIN SED`: Físico `4 pza` (Mín `10` / Máx `24` -> Faltan `20 pza`).
    4. `ADEREZO ARANDANO`: Físico `0.000 L` (Mín `1.0` / Máx `3.0` -> Preparar `3.0 L`).
    5. `ADEREZO BALSAMICO`: Físico `0.000 L` (Mín `1.0` / Máx `1.0` -> Preparar `1.0 L`).
    6. `ADEREZO CHIPOTLE`: Físico `0.000 L` (Mín `1.0` / Máx `3.0` -> Preparar `3.0 L`).
    7. `ADEREZO CILANTRO`: Físico `0.000 L` (Mín `1.0` / Máx `3.0` -> Preparar `3.0 L`).
    8. `ADEREZO KYOTO`: Físico `0.000 L` (Mín `1.0` / Máx `3.0` -> Preparar `3.0 L`).
    9. `ADEREZO RANCH` / `VINAGRETA`: Físico `0.000 L` (Mín `1.0` / Máx `3.0` -> Preparar `3.0 L`).

---

## 4. Catálogo de Productos POS

- **Total Productos Activos en Menú (`/api/v1/catalog/products`):** `132` productos (aguas, baguettes, ensaladas, paninis, desayunos, cafés, postres).

---

## 5. Índice de Documentos en Google Drive (`1VvOyaRqaFAI3jgtjmIsw0E8vWH81ATpX`)

1. `01_Configuracion_de_la_Aplicacion_Kiwi.md` (`1wgK-M7BmD4He-87J4kkov3pH9uNyVqZM`)
2. `02_Especificaciones_del_Sistema_Kiwi.md` (`1J8ir17H8rshVa9hsAJLz3Btb37Ay0rNJ`)
3. `03_Criterios_de_Aceptacion_y_Verificacion_Kiwi.md` (`1wz9QJkq9DBbgbWv6SkDWkhQ8DzSUrCHF`)
4. `04_Marco_de_Referencia_y_Gobernanza_Kiwi.md` (`1Rdp8JC2v1YgBivRiMzf4iDDQYgWjXEXH`)
5. `05_Arquitectura_y_Manual_Agentes_Kiwi.md` (`1lJ81ksTMIwyVhfGWKA9XQCFV2UiaChhE`)
6. `conteo_fisico_chapultepec_20261106.csv` (`1rwBPryLuiIx2MlrBP9t2IltT-ovx3ei2`)
7. `AGENTS.md` y `MEMORY.md` (Sincronizados con el repositorio principal).
