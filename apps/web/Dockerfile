FROM node:22-alpine

WORKDIR /app
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web

EXPOSE 5173
CMD ["pnpm", "--filter", "@b2b/web", "dev"]
