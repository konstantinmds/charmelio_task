"""Temporal Worker entry point.

This worker polls the extraction-queue for workflow and activity tasks.
Actual workflows and activities will be implemented in T-07 and T-08.
"""
import asyncio
import logging
import signal

from temporalio.client import Client
from temporalio.worker import Worker

from worker.config import WorkerSettings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("worker")


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Install signal handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:  # pragma: no cover - Windows
            signal.signal(sig, lambda *_: stop_event.set())


async def run_worker() -> None:
    """Run the Temporal worker."""
    # Load configuration
    settings = WorkerSettings()

    logger.info(
        f"Starting worker: temporal={settings.TEMPORAL_ADDRESS}, "
        f"namespace={settings.TEMPORAL_NAMESPACE}, queue={settings.WORKER_TASK_QUEUE}"
    )

    # Connect to Temporal
    client = await Client.connect(
        settings.TEMPORAL_ADDRESS,
        namespace=settings.TEMPORAL_NAMESPACE
    )

    # Create worker (no workflows/activities yet - will be added in T-07/T-08)
    # For now, just ensure the worker starts and connects successfully
    worker = Worker(
        client,
        task_queue=settings.WORKER_TASK_QUEUE,
        workflows=[],  # Will add ExtractionWorkflow in T-08
        activities=[]  # Will add activities in T-07
    )

    # Setup graceful shutdown
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    # Run worker
    logger.info("Worker running, polling for tasks...")
    worker_task = asyncio.create_task(worker.run())

    # Wait for shutdown signal
    await stop_event.wait()
    logger.info("Shutdown signal received, stopping worker...")

    # Cancel worker task
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)
    logger.info("Worker stopped")


def main() -> None:
    """Main entry point."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
