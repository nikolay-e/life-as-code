# Build stage
FROM node:22-alpine AS builder

# Build arguments for versioning (passed to Vite)
ARG VITE_APP_VERSION=dev
ARG VITE_BUILD_DATE
ARG VITE_COMMIT_SHA

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source files
COPY . .

# Build the application with version info
ENV VITE_APP_VERSION=${VITE_APP_VERSION} \
    VITE_BUILD_DATE=${VITE_BUILD_DATE} \
    VITE_COMMIT_SHA=${VITE_COMMIT_SHA}

RUN npm run build

# Production stage
FROM nginx:alpine

# Build arguments for metadata
ARG VITE_APP_VERSION=dev
ARG VITE_BUILD_DATE
ARG VITE_COMMIT_SHA

# Labels for container metadata
LABEL org.opencontainers.image.created="${VITE_BUILD_DATE}" \
      org.opencontainers.image.authors="Nikolay Eremeev" \
      org.opencontainers.image.url="https://github.com/nikolay-e/life-as-code" \
      org.opencontainers.image.source="https://github.com/nikolay-e/life-as-code" \
      org.opencontainers.image.version="${VITE_APP_VERSION}" \
      org.opencontainers.image.revision="${VITE_COMMIT_SHA}" \
      org.opencontainers.image.title="Life-as-Code Frontend" \
      org.opencontainers.image.description="Health analytics web interface"

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
