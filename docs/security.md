# Security

Status: **implemented baseline**. The API authenticates callers with signed
JWT bearer tokens, gates operations with organization membership roles, and
applies document ACLs during retrieval and document inspection.

## Control-plane security (Phase 13)

- JWT bearer authentication
- RBAC: `OWNER`, `ADMIN`, `EDITOR`, `MEMBER`, `VIEWER`
- Tenant isolation on every query (`organization_id` is not optional)
- Connector credentials encrypted at rest in `source_connections.credentials_encrypted`
- Upload validation: MIME allow-list, max size (`MAX_UPLOAD_SIZE_BYTES`)
- Rate limiting on auth, search, and chat

`/api/v1/auth/login` exchanges an email/password for a bearer token.
Development seeds `admin@example.com` / `password`; production requires
`Authorization: Bearer <token>`.

## RAG security

Retrieved text is **untrusted**. Prompts must keep three channels distinct:

1. System instructions (non-overridable)
2. User instructions
3. Retrieved data (quoted, never treated as instructions)

Prompt injection inside documents, runbooks, or crawled HTML must not change tool policy, exfiltrate secrets, or disable ACL filters.

Search request bodies do not supply `user_id` or groups. The API derives
`ACLContext` from the authenticated user, including the user's UUID, email,
stored groups, role group, and organization group. Dense and sparse retrieval
hydrate candidate documents and call ACL checks before returning hits or context.
Google Drive permissions are propagated from the upstream Drive permissions API
as user emails, group emails, domains, or public access.

## Secrets

| Secret | Source |
| --- | --- |
| `SECRET_KEY` | Environment |
| Postgres password | Environment / Compose |
| MinIO / S3 keys | Environment |
| Qdrant API key | Environment (optional locally) |
| Connector tokens | Encrypted in PostgreSQL using `CREDENTIAL_ENCRYPTION_KEY` or `SECRET_KEY` |

`.env` is gitignored. Use `.env.example` as the template.

## Phase 1 local defaults

Compose uses `dev-only-change-me` and `minioadmin` so `docker compose up` works without extra files. These values are not acceptable outside local development.
