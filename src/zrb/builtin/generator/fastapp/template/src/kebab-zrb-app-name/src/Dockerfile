# First stage: build the frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend .
RUN npm install --save-dev && npm run build

# Second stage: build the API and copy the frontend build
FROM python:3.10-slim
ENV APP_HOST 0.0.0.0
ENV APP_PORT 8080
ENV POETRY_VIRTUAL_ENVS_CREATE=false
WORKDIR /home
RUN apt update && apt install curl psmisc -y
RUN pip install -U pip
RUN pip install "poetry==1.7.1"
COPY ./pyproject.toml ./pyproject.toml
RUN poetry install --only main --no-root
COPY . .
COPY --from=frontend-builder /frontend/build /home/frontend/build
CMD ./start.sh