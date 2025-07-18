FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

# Copy your action files
COPY actions.py /app/actions.py

# Copy the existing requirements.txt
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install -r requirements.txt

# Run the Rasa SDK action server
CMD ["rasa-sdk", "run", "--port", "5055"]
