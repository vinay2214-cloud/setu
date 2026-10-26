FROM node:22-bookworm-slim AS web
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock ./backend/requirements.lock
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r backend/requirements.lock
ENV PATH="/opt/venv/bin:$PATH" NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY backend/ ./backend/
COPY seed/ ./seed/
COPY --from=web /build/frontend/.next/standalone ./frontend/
COPY --from=web /build/frontend/.next/static ./frontend/.next/static
COPY scripts/start.sh ./scripts/start.sh
RUN mkdir -p /app/data && chmod +x /app/scripts/start.sh
EXPOSE 10000
CMD ["/app/scripts/start.sh"]
