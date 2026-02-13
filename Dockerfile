FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy frontend
COPY frontend/ ./frontend/

# Expose ports
EXPOSE 5000 8000

# Run both backend and frontend
CMD ["sh", "-c", "python backend/app.py & cd frontend && python -m http.server 8000"]

