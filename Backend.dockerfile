FROM rasa/rasa:3.6.10

WORKDIR /app
COPY . /app

# Optional: Uncomment to train model inside image
# RUN rasa train

CMD ["run", "--enable-api", "--cors", "*", "--port", "5005"]
