FROM zrbGeneratorBaseImage
ENV APP_MESSAGE "Hello, world!"
ENV APP_PORT zrbAppHttpPort
ENV POETRY_VIRTUAL_ENVS_CREATE=false
WORKDIR /home
COPY ./pyproject.toml ./pyproject.toml
RUN pip install "poetry==1.7.1"
RUN poetry install --only main --no-root
COPY . .
CMD poetry run uvicorn main:app --host "0.0.0.0" --port "$APP_PORT"