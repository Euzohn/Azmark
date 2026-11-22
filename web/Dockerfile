FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# npm 缓存目录持久化，lock 不变时秒级完成。
RUN --mount=type=cache,target=/root/.npm npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG API_INTERNAL_URL=http://localhost:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
ARG MAX_ATTACHMENT_BYTES=20971520
ENV MAX_ATTACHMENT_BYTES=$MAX_ATTACHMENT_BYTES
ENV NEXT_TELEMETRY_DISABLED=1
# 持久化 Next.js 构建缓存，后续构建只重编译变更部分。
RUN --mount=type=cache,target=/app/.next/cache npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# next start re-evaluates next.config.ts at runtime; without the file the
# experimental proxy body limit falls back to the 10MB default even though
# the build embedded a larger one. Keep the runtime env identical to the
# builder's so re-evaluation cannot diverge (rewrites destination included).
ARG API_INTERNAL_URL=http://localhost:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
ARG MAX_ATTACHMENT_BYTES=20971520
ENV MAX_ATTACHMENT_BYTES=$MAX_ATTACHMENT_BYTES
COPY --from=builder /app/next.config.ts ./next.config.ts
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
CMD ["npm", "run", "start"]
