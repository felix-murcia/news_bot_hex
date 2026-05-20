# ---- Build stage ----
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# VITE_API_BASE_URL is intentionally left empty here.
# nginx will proxy /api → backend, so the browser never needs the backend host directly.
RUN npm run build

# ---- Serve stage ----
FROM nginx:1.27-alpine AS runner

# Replace default nginx config with our proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
