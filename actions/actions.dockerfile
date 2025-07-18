# actions.dockerfile
FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

COPY actions /app/actions
COPY actions/requirements-actions.txt /app

# ✅ Just install requirements without upgrading pip
RUN pip install --no-cache-dir -r requirements-actions.txt --break-system-packages

USER 1000

CMD ["run", "--port", "5055"]

