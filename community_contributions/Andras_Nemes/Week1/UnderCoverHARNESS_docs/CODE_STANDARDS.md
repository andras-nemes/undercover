# Code standards

1. Keep it simple, do not overcomplicate (KISS).
2. Comments only when necessary.
3. Be concise: a short README and no emojis.
4. IMPORTANT: avoid overly defensive code. Handle exceptions only when necessary.
5. Use uv: ALWAYS `uv run`, NEVER `python3`.
6. TypeScript: strict mode, never `any`.
7. Build only what the current plan's phase asks for; do not add a parameter, a flag or a layer for a future phase (YAGNI).
8. Every external service (an HTTP API, a database, a file store) is called from exactly one module. Nothing else holds its base URL, its client or makes the call directly.
9. Separate the mechanism from the domain: a harness, a client or a framework wrapper does not know about claims, payouts or UnderCover; the domain's tools and rules call into it, not the other way round.
10. A module earns a split (a new file or package) when it has outgrown a screen or two and the split follows a real seam, such as "talks to the backend" vs. "runs the agent" vs. "the claim's own tools". Splitting earlier scatters one idea across files; splitting later tangles several together.
11. Python: type hints on every function signature, a dataclass or a pydantic model for structured data instead of a dict, no mutable default arguments.
