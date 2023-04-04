FROM python:3.10-slim
ENV APP_MESSAGE "Hello, world!"
ENV APP_PORT 8080
WORKDIR /home
COPY . .
RUN pip install -r requirements.txt
CMD uvicorn main:app --host "0.0.0.0" --port "$APP_PORT"
