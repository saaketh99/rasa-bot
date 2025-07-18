FROM rasa/rasa:3.6.10

WORKDIR /app
COPY . /app

CMD ["rasa", "run", "--enable-api", "--cors", "*", "--port", "5005"]
