# TDD - Gate frontend de integración continua

## TDD-TS-048 Gate frontend en CI

Casos:

- el workflow de CI define Node.js 22,
- usa pnpm 10 de manera reproducible,
- instala con `--frozen-lockfile`,
- ejecuta `pnpm typecheck`,
- construye Admin para producción,
- construye POS para producción,
- construye KDS para producción,
- se ejecuta en pull requests y pushes a `main`.

## TDD-TC-041 El gate frontend contiene los pasos requeridos

Given el archivo `.github/workflows/ci.yml`
When la prueba de arquitectura lee su contenido
Then comprueba que existen Node.js 22, pnpm 10, instalación congelada, typecheck, builds de Admin, POS y KDS, y los disparadores de pull request y push a `main`.
