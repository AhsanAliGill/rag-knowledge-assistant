# ═══════════════════════════════════════════════════════════════════════════════
# Stage 1 — deps: install node_modules (cached unless package-lock changes)
# ═══════════════════════════════════════════════════════════════════════════════
FROM node:20-alpine AS deps

WORKDIR /app

# Copy manifests only → this layer is cached until lockfile changes
COPY package.json package-lock.json ./

RUN npm ci --ignore-scripts


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 2 — builder: compile TypeScript + bundle with Vite + Nitro (node-server)
# ═══════════════════════════════════════════════════════════════════════════════
FROM node:20-alpine AS builder

WORKDIR /app

# Bring in installed node_modules from deps stage
COPY --from=deps /app/node_modules node_modules

# Copy full source
COPY . .

# VITE_API_URL is baked into the JS bundle at build time (Vite limitation).
# Pass your production backend URL as a build arg:
#   docker build --build-arg VITE_API_URL=https://api.yourdomain.com .
# Defaults to localhost for local/dev builds.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Override Nitro target from Cloudflare → Node.js server so the output
# is a standard .output/server/index.mjs runnable in any Node.js container.
ENV NITRO_PRESET=node-server

RUN npm run build


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 3 — runtime: lean Node.js image, only the compiled output
# ═══════════════════════════════════════════════════════════════════════════════
FROM node:20-alpine AS runtime

LABEL org.opencontainers.image.title="Knowledge Assistant Frontend"
LABEL org.opencontainers.image.description="TanStack Start SSR frontend — production"

# Non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Nitro node-server output is self-contained — no node_modules needed at runtime
COPY --from=builder --chown=appuser:appgroup /app/.output .output

USER appuser

# Nitro respects PORT and HOST env vars out of the box
ENV PORT=3000
ENV HOST=0.0.0.0
ENV NODE_ENV=production

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000/ > /dev/null || exit 1

CMD ["node", ".output/server/index.mjs"]
