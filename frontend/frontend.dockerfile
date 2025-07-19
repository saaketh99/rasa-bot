# Build Stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY . .

# Use legacy-peer-deps to avoid dependency conflicts
RUN npm install --legacy-peer-deps
RUN npm run build

# Production Stage
FROM node:18-alpine AS runner
WORKDIR /app
COPY --from=builder /app .
EXPOSE 3000
CMD ["npm", "run", "start"]
