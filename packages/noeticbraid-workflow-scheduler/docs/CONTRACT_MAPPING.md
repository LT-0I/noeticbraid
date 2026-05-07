# Frozen Contract Mapping

SP-E does not modify frozen OpenAPI files. Internal scheduler events are mapped to existing frozen `RunRecord.event_type` values only:

| SP-E internal event | Frozen RunRecord.event_type |
|---|---|
| `run_pending` | `routing_advice_recorded` |
| `run_started` | `routing_advice_recorded` |
| `step_started` | `routing_advice_recorded` |
| `step_completed` | `artifact_created` |
| `step_blocked` | `approval_requested` |
| `step_failed` | `task_failed` |
| `outbound_notify` | `approval_requested` |
| `run_finished` | `task_completed` |
| `run_failed` | `task_failed` |
| `security_violation` | `security_violation` |
| `schedule_due` | `routing_advice_recorded` |

Legacy prototype `telegram_notify` is not emitted by this package. The neutral replacement is `outbound_notify`.
