FROM node:24-trixie-slim AS build
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_CLIENT_ID
ARG NEXT_PUBLIC_TENANT_ID
ARG NEXT_PUBLIC_REDIRECT_URI
ARG NEXT_PUBLIC_API_SCOPE
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_CLIENT_ID=$NEXT_PUBLIC_CLIENT_ID \
    NEXT_PUBLIC_TENANT_ID=$NEXT_PUBLIC_TENANT_ID \
    NEXT_PUBLIC_REDIRECT_URI=$NEXT_PUBLIC_REDIRECT_URI \
    NEXT_PUBLIC_API_SCOPE=$NEXT_PUBLIC_API_SCOPE \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_STANDALONE=true \
    NEXT_TELEMETRY_DISABLED=1
RUN test -n "$NEXT_PUBLIC_CLIENT_ID" && test -n "$NEXT_PUBLIC_TENANT_ID" && test -n "$NEXT_PUBLIC_REDIRECT_URI" && test -n "$NEXT_PUBLIC_API_SCOPE" && test -n "$NEXT_PUBLIC_API_BASE_URL" && npm run build

FROM node:24-trixie-slim AS runtime
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]