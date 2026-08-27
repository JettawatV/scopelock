# Legacy scaffold — do not develop here

The active ADK-native application now lives at the repository root:

```text
app/          # `root_agent`, sub-agents, and read-only ADK tools
scopelock/    # deterministic domain and services
tests/        # unit, integration, and native ADK eval assets
```

This directory is retained temporarily to avoid deleting uncommitted source
files during the refactor. Do not run `adk web` or add new code here. Remove it
only after reviewing the migration and committing the new root-level structure.
