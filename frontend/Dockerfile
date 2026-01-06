# Build stage
FROM node:20-alpine AS builder

ARG VITE_APP_VERSION=dev
ARG VITE_APP_ENVIRONMENT=development
ARG VITE_BUILD_DATE
ARG VITE_COMMIT_SHA

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN VITE_APP_VERSION=${VITE_APP_VERSION} \
    VITE_APP_ENVIRONMENT=${VITE_APP_ENVIRONMENT} \
    VITE_BUILD_DATE=${VITE_BUILD_DATE} \
    VITE_COMMIT_SHA=${VITE_COMMIT_SHA} \
    npm run build

# Production stage
FROM nginx:alpine

LABEL org.opencontainers.image.title="Life-as-Code Frontend" \
      org.opencontainers.image.description="React frontend for health analytics platform"

# Setup nginx to run as non-root
RUN chown -R nginx:nginx /var/cache/nginx /var/run && \
    chmod -R 755 /var/cache/nginx /var/run

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN chown -R nginx:nginx /usr/share/nginx/html

USER nginx
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
