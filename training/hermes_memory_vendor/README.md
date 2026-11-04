# Vendored Hermes memory component

Source: https://github.com/NousResearch/hermes-agent

Snapshot retrieved 2026-11-04; original source hashes and links are recorded in PROVENANCE.json. MIT license is included in LICENSE.

- store.py: upstream tools/memory_tool_store.py, with imports redirected to this private package's compat.py and threat_patterns.py. No memory algorithm changes.
- threat_patterns.py: upstream tools/threat_patterns.py, unchanged apart from text newline serialization.
- compat.py: Orvyth-specific atomic-write helper and ContextVar-based memory-directory adapter. Used instead of importing the entire Hermes CLI/utilities and its process-global configuration.

This is a component integration, not a complete Hermes Agent installation. No automatic remote update occurs at runtime.
