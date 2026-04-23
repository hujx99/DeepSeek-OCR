FROM node:22-slim AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --include=optional --no-audit --no-fund \
    && case "$(uname -m)" in \
         x86_64) SWC_PKG=@next/swc-linux-x64-gnu ;; \
         aarch64|arm64) SWC_PKG=@next/swc-linux-arm64-gnu ;; \
         *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;; \
       esac \
    && (npm ls "$SWC_PKG" >/dev/null 2>&1 \
    || npm install --no-save --no-package-lock --no-audit --no-fund "${SWC_PKG}@14.2.16")

FROM node:22-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=deps /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "run", "start"]
