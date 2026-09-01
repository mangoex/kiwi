# TDD - Suite de Google Reviews y Feedback por Sucursal

## TDD-TS-105 Suite de Google Reviews y Feedback por Sucursal

### TDD-TC-231 Persistencia y CRUD de google_review_url en Sucursales

- Archivo: `apps/api/tests/test_branch_google_reviews.py::test_branch_google_review_url_crud`
- Propósito: Verificar la creación, actualización y consulta pública de `google_review_url` por sucursal física.

### TDD-TC-232 Captura de Feedback Privado de Comensales

- Archivo: `apps/api/tests/test_branch_google_reviews.py::test_public_customer_feedback_endpoint`
- Propósito: Validar el endpoint público `POST /api/v1/public/feedback` con rating (1..5), folio y comentario interno.
