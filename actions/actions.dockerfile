FROM rasa/rasa-sdk:3.6.1

WORKDIR /app

COPY . /app/actions         # This copies files from the `actions` directory into `/app/actions`
COPY ../requirements.txt /app/   # This goes one directory up to get the root-level requirements.txt

RUN pip install -r /app/requirements.txt

CMD ["python", "-m", "rasa_sdk.endpoint", "--port", "5055"]
