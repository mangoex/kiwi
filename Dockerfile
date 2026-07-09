# Stage 1: Build React Frontends
FROM node:22-slim AS frontend-builder
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN npm install -g pnpm@10.0.0

WORKDIR /app
COPY . .
RUN pnpm install
RUN pnpm --filter "@restaurantos/pos-web" build
RUN pnpm --filter "@restaurantos/admin-web" build
RUN pnpm --filter "@restaurantos/kds-web" build

# Stage 2: Build Python Backend
FROM python:3.12-slim

WORKDIR /app

# Copy built frontends to static directory
COPY --from=frontend-builder /app/apps/pos-web/dist /app/static/pos-web
COPY --from=frontend-builder /app/apps/admin-web/dist /app/static/admin-web
COPY --from=frontend-builder /app/apps/kds-web/dist /app/static/kds-web

COPY apps/api /app/apps/api

WORKDIR /app/apps/api
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn restaurant_os.main:app --host 0.0.0.0 --port 8000"]

