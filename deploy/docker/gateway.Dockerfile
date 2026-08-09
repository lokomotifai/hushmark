# syntax=docker/dockerfile:1.12

ARG NODE_IMAGE=node:22-slim@sha256:d649c27dae7ba0137b3cef5dd75baa422c08dc3d9e3fc0c23dfb172dc3cc6436

FROM ${NODE_IMAGE} AS build
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json turbo.json ./
COPY packages/shared/package.json packages/shared/package.json
COPY packages/gateway/package.json packages/gateway/package.json
COPY packages/gateway-enterprise/package.json packages/gateway-enterprise/package.json
RUN pnpm install --frozen-lockfile
COPY packages/shared packages/shared
COPY packages/gateway packages/gateway
COPY packages/gateway-enterprise packages/gateway-enterprise
COPY deploy/docker/eval deploy/docker/eval
RUN pnpm --filter @hushmark/shared build \
    && pnpm --filter @hushmark/gateway build \
    && pnpm --filter @hushmark/gateway-enterprise build \
    && pnpm --filter @hushmark/gateway-enterprise deploy --prod /deploy

FROM ${NODE_IMAGE} AS runtime
ARG HUSHMARK_UID=10001
ARG HUSHMARK_GID=10001
RUN groupadd --gid "${HUSHMARK_GID}" hushmark \
    && useradd --uid "${HUSHMARK_UID}" --gid hushmark --no-create-home --shell /usr/sbin/nologin hushmark
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/pnpm /usr/local/bin/pnpx
WORKDIR /opt/hushmark
COPY --from=build --chown=hushmark:hushmark /deploy ./
COPY --from=build --chown=hushmark:hushmark /workspace/deploy/docker/eval ./eval
ENV NODE_ENV=production
USER hushmark:hushmark
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=5 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:8080/healthz').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]
ENTRYPOINT ["node", "dist/cli.js"]
