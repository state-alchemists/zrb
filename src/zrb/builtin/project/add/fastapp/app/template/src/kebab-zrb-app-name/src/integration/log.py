import logging

from config import APP_ENABLE_OTEL, APP_LOGGING_LEVEL, APP_OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

##############################################################################
# Create logger
##############################################################################
logger = logging.getLogger("src")
logger.setLevel(APP_LOGGING_LEVEL)

##############################################################################
# Formatter log handler
##############################################################################

stream_handler = logging.StreamHandler()
stream_handler.setLevel(APP_LOGGING_LEVEL)
# create formatter
formatter = logging.Formatter("%(levelname)s:\t%(message)s")
# set stream handler's formatter
stream_handler.setFormatter(formatter)
# add ch to logger
logger.addHandler(stream_handler)

##############################################################################
# Open telemetry log handler
##############################################################################

if APP_ENABLE_OTEL:
    # create logger providers
    otlp_logger_provider = LoggerProvider()
    # set the providers
    set_logger_provider(otlp_logger_provider)
    otlp_log_exporter = OTLPLogExporter(endpoint=APP_OTEL_EXPORTER_OTLP_ENDPOINT)
    # add the batch processors to the trace provider
    otlp_logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(otlp_log_exporter)
    )
    otlp_log_handler = LoggingHandler(
        level=APP_LOGGING_LEVEL, logger_provider=otlp_logger_provider
    )
    logger.addHandler(otlp_log_handler)
