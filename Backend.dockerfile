FROM rasa/rasa:3.6.10

WORKDIR /app
COPY . /app

ENTRYPOINT ["rasa"]
CMD ["run", "--enable-api", "--cors", "*", "--port", "5005"]

