FROM python:3.10-slim

WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y gcc

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy action server code
COPY actions /app/actions

# Run Rasa SDK action server
CMD ["python", "-m", "rasa_sdk", "--actions", "actions"]
