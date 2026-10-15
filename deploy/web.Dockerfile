# Builds the React app and serves it with Caddy, which also proxies the API.
FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2.10-alpine
COPY deploy/Caddyfile deploy/Caddyfile.http /etc/caddy/
COPY --from=build /src/dist /srv/app
