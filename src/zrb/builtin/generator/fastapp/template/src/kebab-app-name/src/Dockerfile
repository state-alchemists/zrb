# First stage: build the frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend .
RUN npm install && npm run build

# Second stage: build the API and copy the frontend build
FROM python:3.10-slim
WORKDIR /home
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
COPY --from=frontend-builder /frontend/build /home/frontend/build
CMD python main.py