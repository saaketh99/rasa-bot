# Use Rasa SDK base image
FROM rasa/rasa-sdk:3.6.1

# Switch to root for installation
USER root

# Set working directory
WORKDIR /app

# Copy your action code and requirements
COPY actions /app/actions
COPY actions/requirements-actions.txt /app

# Install required Python packages
RUN pip install --no-cache-dir -r requirements-actions.txt

# Switch back to safe user
USER 1000

# Start Rasa action server
# Switch to root for installation
USER root

# Set working directory
WORKDIR /app

# Copy your action code and requirements
COPY actions /app/actions
COPY actions/requirements-actions.txt /app

# Install required Python packages
RUN pip install --no-cache-dir -r requirements-actions.txt

# Switch back to safe user
USER 1000

# Start Rasa action server
CMD ["start"]


