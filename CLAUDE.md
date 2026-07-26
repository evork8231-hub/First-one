# Global Implementation Rules

These rules apply to every implementation phase in this repository.

## Before writing code

1. Inspect the entire existing project.
2. Understand the architecture.
3. Never rewrite completed modules unless explicitly instructed.
4. Reuse existing abstractions whenever possible.
5. Keep commits logically separated by phase.
6. If a requested change conflicts with the existing architecture, explain why before changing it.
7. Never fabricate implementations for unavailable APIs or undocumented endpoints.
8. If an official API does not support a requested feature, stop and explain the limitation.
9. Every new module must include tests.
10. Every public function and class must include type hints.
11. Maintain compatibility with previous phases.
12. Run linting, type checking, and tests before considering the phase complete.
13. Report:
    - Files created
    - Files modified
    - Tests added
    - Remaining limitations
14. Wait for the next prompt before implementing additional features.
