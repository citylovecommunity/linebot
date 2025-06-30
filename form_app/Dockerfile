FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app

# Expose the port uvicorn will run on
EXPOSE 5678

# Command to run the app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5678", "app:app"]