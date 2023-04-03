# First stage: build the frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend .
RUN npm install && npm run build

# Second stage: build the API and copy the frontend build
FROM python:3.10-slim
ENV APP_HOST 0.0.0.0
ENV APP_PORT 8080
WORKDIR /home
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
COPY --from=frontend-builder /frontend/build /home/frontend/build
CMD uvicorn main:app --host "$APP_HOST" --port "$APP_PORT"