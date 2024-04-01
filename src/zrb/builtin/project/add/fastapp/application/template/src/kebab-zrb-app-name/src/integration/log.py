import logging

from config import app_enable_otel, app_logging_level, app_otel_exporter_otlp_endpoint
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

##############################################################################
# Create logger
##############################################################################
logger = logging.getLogger("src")
logger.setLevel(app_logging_level)

##############################################################################
# Formatter log handler
##############################################################################

stream_handler = logging.StreamHandler()
stream_handler.setLevel(app_logging_level)
# create formatter
formatter = logging.Formatter("%(levelname)s:\t%(message)s")
# set stream handler's formatter
stream_handler.setFormatter(formatter)
# add ch to logger
logger.addHandler(stream_handler)

##############################################################################
# Open telemetry log handler
##############################################################################

if app_enable_otel:
    # create logger providers
    otlp_logger_provider = LoggerProvider()
    # set the providers
    set_logger_provider(otlp_logger_provider)
    otlp_log_exporter = OTLPLogExporter(endpoint=app_otel_exporter_otlp_endpoint)
    # add the batch processors to the trace provider
    otlp_logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(otlp_log_exporter)
    )
    otlp_log_handler = LoggingHandler(
        level=app_logging_level, logger_provider=otlp_logger_provider
    )
    logger.addHandler(otlp_log_handler)
