FROM rasa/rasa-sdk:3.6.1

USER root                    # <-- Add this line

WORKDIR /app
COPY actions /app/actions
COPY actions/requirements-actions.txt /app

RUN pip install --no-cache-dir -r requirements-actions.txt

USER 1000                   # <-- Reset to non-root user (recommended by Rasa)

CMD ["run", "--port", "5055"]

