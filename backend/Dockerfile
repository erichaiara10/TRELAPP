# Build the React frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY backend/frontend/package.json ./

RUN corepack enable \
    && yarn install --non-interactive

COPY backend/frontend/ ./

RUN yarn build

# Build the FastAPI backend
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Put the compiled frontend where backend/server.py expects it
COPY --from=frontend-builder /frontend/build /app/frontend

ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
