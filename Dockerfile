FROM node:22-alpine
WORKDIR /app
COPY out ./out
COPY scripts/serve-static.mjs ./scripts/serve-static.mjs
ENV PORT=4173
EXPOSE 4173
CMD ["node", "scripts/serve-static.mjs", "4173"]
