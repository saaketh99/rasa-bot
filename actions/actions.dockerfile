FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

# Copy action files and requirements
COPY actions /app/actions
COPY requirements-actions.txt /app

# Install Python dependencies for custom actions
RUN pip install -r requirements-actions.txt

# Start the Rasa SDK action server
CMD ["rasa", "run", "actions", "--port", "5055"]

