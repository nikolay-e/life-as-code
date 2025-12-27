# Build stage
FROM node:20-alpine AS builder

ARG VITE_APP_VERSION=dev
ARG VITE_BUILD_DATE
ARG VITE_COMMIT_SHA

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ENV VITE_APP_VERSION=${VITE_APP_VERSION}
ENV VITE_BUILD_DATE=${VITE_BUILD_DATE}
ENV VITE_COMMIT_SHA=${VITE_COMMIT_SHA}

RUN npm run build && \
    # Replace version placeholder with actual version in all built files
    find /app/dist -type f \( -name '*.js' -o -name '*.json' -o -name '*.html' \) -exec \
        sed -i "s/0\.0\.0-placeholder/${VITE_APP_VERSION}/g" {} + 2>/dev/null || true

# Production stage
FROM nginx:alpine

LABEL org.opencontainers.image.title="Life-as-Code Frontend" \
      org.opencontainers.image.description="React frontend for health analytics platform"

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
