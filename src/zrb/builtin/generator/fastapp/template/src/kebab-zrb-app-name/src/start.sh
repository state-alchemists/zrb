##############################################################################
# Function declaration
##############################################################################

_to_boolean() {
    if [ "$1" = 1 ] || [ "$1" = "true" ] || [ "$1" = "True" ] || [ "$1" = "TRUE" ] || [ "$1" = "yes" ] || [ "$1" = "Yes" ] || [ "$1" = "YES" ]
    then
        echo "true"
    else
        echo "false"
    fi
}

##############################################################################
# Set default environment values
##############################################################################

if [ -z "$APP_NAME" ]
then
    APP_NAME="kebab-zrb-app-name"
fi

if [ -z "$APP_HOST" ]
then
    APP_HOST="0.0.0.0"
fi

if [ -z "$APP_PORT" ]
then
    APP_PORT="8080"
fi

if [ -z "$APP_OTEL_EXPORTER_OTLP_ENDPOINT" ]
then
    APP_OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
fi

##############################################################################
# Start kebab-zrb-app-name
##############################################################################

# Reload option can only be used when APP_ENABLE_OTEL is false
_RELOAD=""
if [ $(_to_boolean "$APP_ENABLE_OTEL") = "false" ] && [ $(_to_boolean "$APP_RELOAD") = "true" ]
then
    _RELOAD="--reload"
fi

# Constructing otel command
# See: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html#installation
_OTEL_COMMAND=""
if [ $(_to_boolean "$APP_ENABLE_OTEL") = "true" ]
then
    export OTEL_RESOURCE_ATTRIBUTES="service.name=${APP_NAME}"
    export OTEL_EXPORTER_OTLP_ENDPOINT="$APP_OTEL_EXPORTER_OTLP_ENDPOINT"
    export OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST=".*"
    export OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE=".*"
    _OTEL_COMMAND="opentelemetry-instrument"
fi

# Run uvicorn
echo "Start uvicorn"
poetry run $_OTEL_COMMAND uvicorn main:app --host "$APP_HOST" --port "$APP_PORT" $_RELOAD