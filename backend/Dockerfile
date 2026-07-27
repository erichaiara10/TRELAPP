FROM python:3.11-slim

WORKDIR /app

# Copy requirement files and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Set Python path so it can find backend module
ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
