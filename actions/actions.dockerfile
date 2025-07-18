FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

COPY actions /app/actions
COPY requirements.txt /app/

RUN pip install -r requirements.txt

CMD ["run", "--port", "5055"]

