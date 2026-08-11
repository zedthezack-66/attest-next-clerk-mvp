FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
COPY apps/dashboard ./apps/dashboard
COPY packages ./packages
RUN npm install
RUN npm run build -w apps/dashboard
CMD ["npm", "run", "start", "-w", "apps/dashboard"]

