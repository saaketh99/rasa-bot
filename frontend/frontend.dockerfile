# Build Stage
FROM node:18-alpine AS builder

WORKDIR /app
COPY . .

# Install dependencies (avoiding conflicts)
RUN npm install --legacy-peer-deps

# Build the app (export is automatic with output: 'export' in next.config.js)
RUN npm run build

# Serve Stage
FROM nginx:alpine

# Copy the exported static site from the /out folder
COPY --from=builder /app/out /usr/share/nginx/html

# Expose default nginx port
EXPOSE 80

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
