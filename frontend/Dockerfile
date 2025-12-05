# syntax=docker/dockerfile:1

# ---- Build stage ----
FROM node:20-alpine AS builder
WORKDIR /app

# Install deps
COPY sautai-react-frontend/package*.json ./
RUN npm ci

# Build with API base configured at build time
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}

COPY sautai-react-frontend/ ./
RUN npm run build

# ---- Runtime stage ----
FROM nginx:alpine

COPY sautai-react-frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

# Ensure static files are world-readable (avoid 403 on files with 0600)
RUN find /usr/share/nginx/html -type d -exec chmod 0755 {} \; \
 && find /usr/share/nginx/html -type f -exec chmod 0644 {} \;

EXPOSE 80
HEALTHCHECK CMD wget -qO- http://127.0.0.1/ || exit 1
