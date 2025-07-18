FROM rasa/rasa-sdk:3.6.1

WORKDIR /app
COPY actions /app/actions
COPY requirements-actions.txt /app
RUN pip install -r requirements-actions.txt

CMD ["run", "--port", "5055"]
