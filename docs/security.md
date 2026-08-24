# Security

Status: **partial**. Phase 1 isolates tenants at the infrastructure boundary (separate config, no shared in-memory stores). Auth, RBAC, and ACL retrieval filters arrive in later phases.

## Control-plane security (Phase 13)

- JWT or session authentication
- RBAC: `OWNER`, `ADMIN`, `EDITOR`, `MEMBER`, `VIEWER`
- Tenant isolation on every query (`organization_id` is not optional)
- Connector credentials from the environment; encrypt at rest where practical
- Upload validation: MIME allow-list, max size (`MAX_UPLOAD_SIZE_BYTES`)
- Rate limiting on auth, search, and chat

## RAG security

Retrieved text is **untrusted**. Prompts must keep three channels distinct:

1. System instructions (non-overridable)
2. User instructions
3. Retrieved data (quoted, never treated as instructions)

Prompt injection inside documents, runbooks, or crawled HTML must not change tool policy, exfiltrate secrets, or disable ACL filters.

## Secrets

| Secret | Source |
| --- | --- |
| `SECRET_KEY` | Environment |
| Postgres password | Environment / Compose |
| MinIO / S3 keys | Environment |
| Qdrant API key | Environment (optional locally) |
| Connector tokens | Environment, stored encrypted in PostgreSQL later |

`.env` is gitignored. Use `.env.example` as the template.

## Phase 1 local defaults

Compose uses `dev-only-change-me` and `minioadmin` so `docker compose up` works without extra files. These values are not acceptable outside local development.
