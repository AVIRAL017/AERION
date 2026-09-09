# AERION — Supported API Endpoints & Contract Catalog

**Document Version**: 1.0.0  
**Base URL**: `/api/v1`  
**Protocol**: RESTful HTTP / JSON  
**Canonical Specification**: [`AERION_API_CONTRACT.md`](../../AERION_API_CONTRACT.md)  

---

## 1. Health & Operational Probes

| Method | Endpoint | Auth | Purpose | Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Liveness probe returning operational state | `{ "status": "healthy", "version": "v1", "timestamp": ... }` |
| `GET` | `/ready` | Public | Readiness probe assessing process, config, and GPU lock | `{ "ready": true, "components": { ... } }` |
| `GET` | `/api/v1/health` | Public | Versioned health probe | `{ "status": "healthy" }` |
| `GET` | `/api/v1/ready` | Public | Versioned readiness probe | `{ "ready": true, ... }` |

---

## 2. Authentication & Authorization

| Method | Endpoint | Auth | Purpose | Request Payload |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Public | Register user & organization | `{ "email": "...", "password": "...", "organization_name": "...", "role": "operator" }` |
| `POST` | `/api/v1/auth/login` | Public | Authenticate credentials and issue JWT | `{ "email": "...", "password": "..." }` |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Fetch current authenticated profile | None |

---

## 3. Operational Situations & Intelligence (Architecture-Defined)

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/situations` | Bearer JWT | List active operational situations |
| `GET` | `/api/v1/situations/{id}` | Bearer JWT | Fetch situation state, threat score, and sector metrics |
| `GET` | `/api/v1/situations/{id}/events` | Bearer JWT | Retrieve immutable chronological event sequence |
| `GET` | `/api/v1/situations/{id}/weather` | Bearer JWT | Query live or reconstructed historical weather |
| `GET` | `/api/v1/situations/{id}/routes` | Bearer JWT | Query evaluated road routes avoiding active hazards |
| `GET` | `/api/v1/situations/{id}/report` | Bearer JWT | Generate deterministic Situation Report with Mistral advisory |

---

## 4. Usage Metering & Subscriptions

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/usage/summary` | Bearer JWT | Retrieve monthly metered resource consumption |
| `POST` | `/api/v1/subscriptions/upgrade` | Bearer JWT | Transition organization between FREE and PRO (₹9/mo) |
