FROM node:22-alpine AS deps
WORKDIR /app/apps/web
COPY apps/web/package.json ./
RUN npm install

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/apps/web/node_modules /app/apps/web/node_modules
COPY apps/web /app/apps/web
WORKDIR /app/apps/web
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app/apps/web
ENV NODE_ENV=production
COPY --from=builder /app/apps/web/.next ./.next
COPY --from=builder /app/apps/web/public ./public
COPY --from=builder /app/apps/web/package.json ./package.json
COPY --from=deps /app/apps/web/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "run", "start"]
