# Reference only: pin Node base image by digest and scan it in production.
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src/ ./src/
USER node
EXPOSE 3000
CMD ["node", "src/server.js"]
