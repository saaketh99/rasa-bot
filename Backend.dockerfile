# Use official Rasa image
FROM rasa/rasa:3.6.10

# Set working directory
WORKDIR /app

# Copy project files (domain.yml, data/, config.yml, etc.)
COPY . /app

# Optional: You can train the model inside the image if needed
# RUN rasa train

# Expose the Rasa server port
EXPOSE 5005

# Start the Rasa server with API and CORS enabled
CMD ["rasa", "run", "--enable-api", "--cors", "*", "--port", "5005"]
