# Domain Strategy

- decision: D-Step4-2
- user selected: C. no public exposure in Phase 1
- status: local-only

NoeticBraid remains local-first during Phase 1. The Console binds to `127.0.0.1` and uses a startup token. No DNS, TLS, reverse proxy, Tailscale Funnel, Cloudflare Tunnel, or public Console endpoint is required in Phase 1.

The existing domain `jungerpf.top` may be used later in one of three ways:

1. `noeticbraid.jungerpf.top` as project subdomain;
2. `jungerpf.top/noeticbraid` as documentation path;
3. no public project site.

Stage 0 does not deploy any of these.
