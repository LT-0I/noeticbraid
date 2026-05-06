# Manual browser smoke test

Automated tests do not launch a real browser. To manually verify live browser connectivity:

1. Install optional browser dependencies:

   ```powershell
   pip install -e .[browser]
   playwright install chromium
   ```

2. Pick a disposable Chrome profile directory. Do not point at a private production profile unless explicitly intended.

3. Run a small script:

   ```python
   from noeticbraid_runtime import launch_browser, get_session

   process = launch_browser(".tmp/c2-profile", cdp_port=9222, headless=False)
   session = get_session(cdp_port=9222)
   session.navigate("https://example.com")
   title = session.eval("document.title")
   written = session.screenshot(".tmp/c2-smoke.png")
   print(title, written)
   process.close()
   ```

Expected result: non-empty screenshot bytes and title `Example Domain`.

Do not use this smoke test to bypass login, CAPTCHA, paywall, bot defense, or site policy.
