# ============================
# FRONTEND BUILD STAGE
# ============================
FROM node:20 AS frontend
WORKDIR /app

# Copy only the frontend folder
COPY backend/frontend/ ./frontend/


# Build frontend
WORKDIR /app/frontend
RUN npm install --legacy-peer-deps
RUN npm run build

# ============================
# BACKEND BUILD STAGE
# ============================
FROM python:3.11-slim AS backend
WORKDIR /app

# Copy backend source
COPY . .

# Copy built frontend into backend static folder
COPY --from=frontend /app/frontend/dist ./static

# Install backend dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]

