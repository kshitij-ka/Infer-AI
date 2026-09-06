# Documentation index

- [architecture.md](architecture.md): system diagram, database  migration mechanics, the RBAC and SSO/OIDC extension path, the response caching design and its LLM output trust caveat, the 500 requests per second scaling plan, and the EC2 to production migration plan.
- [security.md](security.md): every security hardening measure in this application, why it exists, the real vulnerabilities found and fixed during development, and what is explicitly out of scope.
- [admin.md](admin.md): why there is no self service registration, how the first admin is created, how every other user is created, and the fixes applied after a security review of that feature.
- [observability.md](observability.md): structured logging, request tracing, Prometheus metrics, and the health check.
- [testing.md](testing.md): the two test tiers, unit and integration, how to run each, and the pytest path deduplication
  detail that makes the combined test command less obvious than it looks.
- [development.md](development.md): lint, format, type check, and test commands for day to day development.
- [frontend.md](frontend.md): the two frontend pages (API reference and interactive console), their routes, the design system tokens and components, and the reconciliation between the design mockups and the real API contracts.

