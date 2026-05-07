# Reference Research

- APScheduler ? https://apscheduler.readthedocs.io/en/master/userguide.html ? schedule/executor/store separation.
- Prefect ? https://docs.prefect.io/v3/get-started ? run-state tracking and explicit orchestration.
- Temporal ? https://temporal.io/ ? workflow/activity separation and durable-event design inspiration.
- Celery ? https://docs.celeryq.dev/en/2.0-archived/internals/worker.html ? scheduler/worker separation; SP-E deliberately avoids broker/worker behavior.

These are design references only. The package remains stdlib-only at runtime.
