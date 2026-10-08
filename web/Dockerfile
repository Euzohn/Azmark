# syntax=docker/dockerfile:1.6
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
ENV NEXT_TELEMETRY_DISABLED=1
# 持久化 Next.js 构建缓存，后续构建只重编译变更部分。
RUN --mount=type=cache,target=/app/.next/cache npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
CMD ["npm", "run", "start"]
