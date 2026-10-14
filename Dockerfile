FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-alpine
WORKDIR /app
COPY backend/ ./backend/
COPY clinic.json ./clinic.json
COPY conversations/ ./conversations/
COPY --from=frontend /app/frontend/dist ./frontend/dist
ENV PORT=8000
CMD ["sh", "-c", "python3 -m backend.server --host 0.0.0.0 --port ${PORT}"]
