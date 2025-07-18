FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

COPY actions /app/actions
COPY actions/requirements-actions.txt /app

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements-actions.txt --break-system-packages

CMD ["run", "--port", "5055"]

