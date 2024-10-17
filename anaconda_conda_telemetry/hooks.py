from conda import __version__ as CONDA_VERSION
from conda.base.context import context
from conda.common.url import mask_anaconda_token
from conda.models.channel import all_channel_urls
from conda.plugins import hookimpl, CondaPostCommand
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    # ConsoleSpanExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

try:
    from conda_build import __version__ as CONDA_BUILD_VERSION
except ImportError:
    CONDA_BUILD_VERSION = "n/a"

# Tracer
provider = TracerProvider()
exporter = OTLPSpanExporter(
    endpoint="http://localhost:4317/",
    insecure=True,
)
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)

# Enable when debugging output is desired
# processor_console = BatchSpanProcessor(ConsoleSpanExporter())
# provider.add_span_processor(processor_console)

# Sets the global default tracer provider
trace.set_tracer_provider(provider)

# Creates a tracer from the global tracer provider
tracer = trace.get_tracer("anaconda-conda-telemetry")


def get_virtual_packages() -> tuple[str, ...]:
    """
    Uses the ``conda.base.context.context`` object to retrieve registered virtual packages
    """
    return tuple(
        f"{package.name}.{package.version}.{package.build}"
        for package in context.plugin_manager.get_virtual_packages()
    )


def get_channel_urls() -> tuple[str, ...]:
    """
    Returns a list of currently configured channel URLs with tokens masked
    """
    channels = list(all_channel_urls(context.channels))
    return tuple(mask_anaconda_token(c) for c in channels)


def submit_telemetry_data(command: str):
    """
    Submits telemetry data to the configured data collector
    """
    with tracer.start_as_current_span("post_command_hook") as current_span:
        current_span.set_attribute(
            "python_implementation", context.python_implementation_name_version[0]
        )
        current_span.set_attribute(
            "python_version", context.python_implementation_name_version[1]
        )
        current_span.set_attribute("conda_version", CONDA_VERSION)
        current_span.set_attribute("solver_version", context.solver_user_agent())
        current_span.set_attribute("conda_build_version", CONDA_BUILD_VERSION)
        current_span.set_attribute("virtual_packages", get_virtual_packages())
        current_span.set_attribute(
            "platform_system", context.platform_system_release[0]
        )
        current_span.set_attribute(
            "platform_release", context.platform_system_release[1]
        )
        current_span.set_attribute("channel_urls", get_channel_urls())
        current_span.set_attribute("conda_command", command)


@hookimpl
def conda_post_commands():
    yield CondaPostCommand(
        name="post-command-submit-telemetry-data",
        action=submit_telemetry_data,
        run_for=["install", "remove", "update", "create"],
    )
