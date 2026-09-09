# AERION — Deployment & Low-Cost AWS Production Architecture

**Target Deployment Profile**: Single-Node GPU / Cost-Optimized AWS Cloud  
**Hardware Baseline**: NVIDIA RTX 3050 (6 GB VRAM) locally / AWS g4dn.xlarge (T4 16 GB) in cloud  

---

## 1. Minimal Low-Cost Architecture

AERION is explicitly architected to minimize operational infrastructure expenditure for defense/disaster deployments:

1. **No External Message Broker Required**: No Celery, Redis, RabbitMQ, or Kafka dependencies in the primary backend. In-memory `JobManager` handles asynchronous task execution safely.
2. **PostgreSQL 16 with PostGIS**: Provides unified relational, spatial, and JSONB document persistence in a single database service (e.g. AWS RDS db.t4g.medium or self-hosted EC2 instance).
3. **Lazy Model Allocation**: Heavy models (YOLOv8s, YOLOv8n-OBB, Siamese ResNet18) are not held continuously in GPU memory. They are loaded lazily on demand.
4. **GPU Mutex Serialization**: Protects the 6 GB RTX 3050 GPU from Out-Of-Memory (OOM) crashes by queuing concurrent inference requests through `InferenceLock`.
5. **Decoupled Advisory AI**: Uses hosted Mistral API (`open-mistral-nemo`) for operational synthesis without requiring expensive multi-GPU LLM inference clusters.

---

## 2. Environment Variables & Production Hardening

- All secrets (`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `MISTRAL_API_KEY`, `MAPBOX_ACCESS_TOKEN`, `OPENROUTESERVICE_API_KEY`) must be supplied via OS environment variables.
- Set `ENVIRONMENT=production` to activate:
  - Strict CORS origin enforcement (wildcards `*` rejected).
  - Prohibition of `DEBUG=true`.
  - JSON structured logging with request ID correlation.
  - Automatic stack trace and credential redaction on errors.
