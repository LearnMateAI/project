# Build the SPA with the deployment's settings baked in, then serve the static files.
# Vite 8 needs Node 20.19+ or 22.12+.
FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# VITE_* are read at build time, not run time: changing one means rebuilding this image.
ARG VITE_API_BASE_URL=
ARG VITE_KEYCLOAK_URL=/auth
ARG VITE_KEYCLOAK_REALM=learnmate
ARG VITE_KEYCLOAK_CLIENT_ID=learnmate-frontend
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL} \
    VITE_KEYCLOAK_REALM=${VITE_KEYCLOAK_REALM} \
    VITE_KEYCLOAK_CLIENT_ID=${VITE_KEYCLOAK_CLIENT_ID}

RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
