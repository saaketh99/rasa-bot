FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

COPY requirements.txt /app/
COPY actions /app/actions

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "rasa_sdk", "--actions", "actions"]
