# Build Stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY . .

# Use legacy-peer-deps to avoid dependency conflicts
RUN npm install --legacy-peer-deps
RUN npm run build

# Serve Stage
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
