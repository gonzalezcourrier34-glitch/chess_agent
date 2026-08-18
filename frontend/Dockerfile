FROM node:20-alpine

# Application

WORKDIR /app


# Dépendances

COPY package.json package-lock.json ./

RUN npm ci


# Frontend Angular

COPY . .


# Application

EXPOSE 4200

CMD ["npm", "run", "start", "--", "--host", "0.0.0.0", "--port", "4200"]