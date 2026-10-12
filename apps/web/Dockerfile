# One Next.js app for the desk, the responder PWA and the reporter PWA (PRD §12.1).
FROM public.ecr.aws/docker/library/node:22-alpine AS base
COPY --from=certs . /tmp/certs/
RUN cat /tmp/certs/*.crt > /etc/extra-ca.pem 2>/dev/null || touch /etc/extra-ca.pem
ENV NODE_EXTRA_CA_CERTS=/etc/extra-ca.pem NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public && npm run build

FROM base AS run
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
