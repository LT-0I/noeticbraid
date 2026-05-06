# SP-C2 BrowserSession Contract

SP-H expects the current NoeticBraid runtime shape:

```python
class BrowserSession(Protocol):
    tab_id: str
    cdp_url: str
    def navigate(self, url: str, timeout_s: int = 30) -> None: ...
    def eval(self, expression: str, await_promise: bool = True, timeout_s: int = 30) -> Any: ...
    def click(self, x: float, y: float, timeout_s: int = 30) -> None: ...
    def type_text(self, text: str, timeout_s: int = 30) -> None: ...
```

SP-H resolves selectors to coordinates internally with JavaScript evaluated through `eval`. It does not require SP-C2 to support `click(selector)`, `type_text(selector, text)`, `wait_for`, or `evaluate` aliases.

Optional event sinks may be provided as `emit_event(event)`, `record_event(event)`, or `log_event(event)`.
