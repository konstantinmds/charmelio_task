"""Temporal Worker entry point.

This worker polls the extraction-queue for workflow and activity tasks.
"""
import asyncio
import logging
import signal
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from worker.activities import llm_extract, parse_pdf, store_results
from worker.config import WorkerSettings
from worker.workflows import ExtractionWorkflow

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

    # Create thread pool for sync activities
    activity_executor = ThreadPoolExecutor(max_workers=4)

    # Create worker with workflows and activities
    worker = Worker(
        client,
        task_queue=settings.WORKER_TASK_QUEUE,
        workflows=[ExtractionWorkflow],
        activities=[parse_pdf, llm_extract, store_results],
        activity_executor=activity_executor,
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

    # Cancel worker task and shutdown executor
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)
    activity_executor.shutdown(wait=True)
    logger.info("Worker stopped")


def main() -> None:
    """Main entry point."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
