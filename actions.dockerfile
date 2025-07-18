FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

COPY requirements.txt /app/
COPY actions /app/actions

RUN pip install --upgrade pip && pip install --no-cache-dir --break-system-packages -r requirements.txt

CMD ["python", "-m", "rasa_sdk", "--actions", "actions"]
