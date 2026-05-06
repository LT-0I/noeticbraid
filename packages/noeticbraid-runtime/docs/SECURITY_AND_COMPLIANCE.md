# Security and compliance

## Allowed behavior

- Launch a user-provided Chrome profile directory when explicitly requested.
- Attach to a local Chrome DevTools Protocol endpoint.
- Run allowlisted CLI commands inside allowed cwd roots.
- Load local selector configuration.
- Build proxy arguments from explicit proxy settings and trusted TUN environment values.

## Forbidden behavior

- No account pool management; SP-C1 owns account/quota data.
- No cookie decryption, browser credential export, or profile content scraping.
- No DPAPI implementation and no `pywin32`.
- No `mcp-server-sqlite` or sqlite runtime store.
- No business automation workflows in C2.
- No vault writes.
- No task scheduling.
- No frozen contract modifications.

## CLI sandbox rules

`CLISandbox` is deny-by-default:

1. command executable must match the allowlist;
2. cwd must resolve inside one allowed root;
3. env overlay is isolated and only `env_allowlist` keys are passed;
4. commands run with `shell=False`;
5. timeout raises `CLISandboxTimeout` after child kill/wait.
