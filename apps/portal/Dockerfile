FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
COPY apps/portal ./apps/portal
COPY packages ./packages
RUN npm install
RUN npm run build -w apps/portal
CMD ["npm", "run", "start", "-w", "apps/portal"]

