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

if [ $(_to_boolean "$APP_ENABLE_OTEL") = "true" ]
then
    echo "Start uvicorn with instrumentation, service name: ${APP_NAME}"
    OTEL_RESOURCE_ATTRIBUTES="service.name=${APP_NAME}" \
        OTEL_EXPORTER_OTLP_ENDPOINT="$APP_OTEL_EXPORTER_OTLP_ENDPOINT" \
        opentelemetry-instrument uvicorn main:app --host "$APP_HOST" --port "$APP_PORT"
else
    # reload should only performed if otel is disabled
    _RELOAD=""
    if [ $(_to_boolean "$APP_RELOAD") = "true" ]
    then
        _RELOAD="--reload"
    fi
    # Run uvicorn
    echo "Start uvicorn"
    uvicorn main:app --host "$APP_HOST" --port "$APP_PORT" $_RELOAD
fi