FROM node:22-slim AS build

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install

COPY . .

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

ARG PUBLIC_CLERK_PUBLISHABLE_KEY
ENV PUBLIC_CLERK_PUBLISHABLE_KEY=${PUBLIC_CLERK_PUBLISHABLE_KEY}

RUN pnpm build

FROM node:22-slim

RUN useradd --create-home appuser
WORKDIR /app

COPY --from=build /app/build build/
COPY --from=build /app/package.json .
COPY --from=build /app/node_modules node_modules/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 3000

CMD ["node", "build/index.js"]
