# TDD - Gate frontend de integración continua

## TDD-TS-048 Gate frontend en CI

Casos:

- el workflow de CI define Node.js 22,
- usa pnpm 10 de manera reproducible, con la versión provista por `packageManager` en `package.json` y sin una versión paralela en el workflow,
- instala con `--frozen-lockfile`,
- ejecuta `pnpm typecheck`,
- construye Admin para producción,
- construye POS para producción,
- construye KDS para producción,
- se ejecuta una sola vez por pull request y permite ejecución manual mediante `workflow_dispatch`,
  sin duplicar la suite completa mediante un trigger `push`.

## TDD-TC-041 El gate frontend contiene los pasos requeridos

Given el archivo `.github/workflows/ci.yml`
When la prueba de arquitectura lee su contenido
Then comprueba que existen Node.js 22, `pnpm/action-setup@v4` sin versión paralela (la versión
proviene de `packageManager: pnpm@10.0.0` en `package.json`), instalación congelada, typecheck,
builds de Admin, POS y KDS, el disparador de pull request y `workflow_dispatch`, sin un trigger
superior `push` que duplique la suite completa.
