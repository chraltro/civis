# civis — build the Vite dashboard, serve the static dist/ on nginx.
# Build context is the repo root so the vite dataAssets plugin can reach
# ../data/processed/civis.{json,csv} relative to web/.

FROM node:22-alpine AS build
WORKDIR /repo
# install web deps first for layer caching
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci
# bring in the data the dashboard reads, then the web source
COPY data/processed ./data/processed
COPY web ./web
RUN cd web && npm run build

FROM nginx:1.27-alpine
RUN rm /etc/nginx/conf.d/default.conf
COPY web/nginx.conf /etc/nginx/conf.d/site.conf
COPY --from=build /repo/web/dist/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1
