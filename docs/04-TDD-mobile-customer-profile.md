# TDD — Acceso y perfil móvil

## TDD-TS-153 CRM-MOBILE-001

## TDD-TC-435 Identidad, aislamiento y calendario

apps/api/tests/test_mobile_customer_profile.py (15 casos): OTP falso por puerto (sin red), código inválido,
consumo único, expiración, agotamiento, cookie, cierre/revocación, alcance organizacional,
campos prohibidos, coincidencia única/ambigua, cumpleaños parcial, 29/02, futuro y año opcional.
Incluye errores privados SQL, body 64 KiB y límite agotado/no disponible que nunca envía SMS.
apps/api/tests/test_phone_verification.py (2 casos): contrato del adaptador HTTP sin red,
SID conservado, timeout, host fijo sin redirects, estados denegados e indisponibilidad.

## TDD-TC-436 Perfil, delivery y consumo

Misma suite: edición de perfil, cambio de teléfono verificado, domicilios ajenos, email obligatorio,
intención idempotente vinculada, aceptación y snapshots inmutables. Regresiones de clientes,
intenciones públicas y seguimiento. tests/frontend/test_mobile_customer_profile.mjs verifica
semántica renderizada y cliente HTTP (5 casos). tests/browser/test_mobile_customer_profile.mjs
verifica registro real contra API local, perfil, reintento sin duplicación, delivery que solicita
completar datos y regresa al carrito, error de envío y reintento exitoso, en 320/390/1280 px;
además edición CRM a 1366 px. Capturas sintéticas en output/playwright/crm-mobile-journey/.

## TDD-TC-437 Migración y concurrencia

apps/api/tests/test_mobile_customer_migration.py: roundtrip SQLite/PostgreSQL aislado, datos
anteriores y pedido/intención aceptados intactos, downgrade protegido con información nueva.
apps/api/tests/test_mobile_customer_postgres.py (3 casos): login simultáneo con identidad única,
materialización de perfil/domicilio una sola vez y cambios de teléfono solapados con rechazo
del obsoleto. PostgreSQL17 local aislado, sin skips en los cinco casos de migración/concurrencia.
Gates: Ruff, mypy focal, typecheck, build móvil, trazabilidad, QA móvil y auditoría R3 independiente.
La ejecución productiva y CI se reportan aparte; ningún skip acredita PostgreSQL.


CRM-MOBILE-002 amplía esta misma suite/casos: test_mobile_customer_password.py cubre registro,
login, hashes, errores privados, colisiones CRM/identidad, throttle persistente, CSRF, cierre,
contraseña/teléfono y revocación. La compatibilidad OTP conserva sus regresiones existentes.
La suite PG prueba altas y rotaciones concurrentes, rechazo de la contraseña anterior y throttle
atómico entre conexiones; migración 0099
SQLite/PG conserva identidades/sesiones y bloquea downgrade con credenciales.
El recorrido de navegador y semántica cambian al alta/login por contraseña sin proveedor;
prueban formulario bloqueado en 503, reintento, error de contraseña y carrito conservado.
