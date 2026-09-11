# AERION v1 — Azure Staging Infrastructure & Deployment Guide

## 1. Executive Summary
This document provides the authoritative record of the **AERION v1** staging environment deployed on **Microsoft Azure** under the active *Azure for Students* subscription for **Batch 4 — Step 31**.

The staging environment establishes a minimal, cost-conscious, single-node architecture hosting the complete AERION backend, PostgreSQL 16 with PostGIS 3.4.2 spatial extensions, Nginx reverse proxy, systemd process supervision, and Azure Blob Storage integration for immutable evidence artifacts.

---

## 2. Infrastructure Architecture & Specification

### 2.1 Target Staging Architecture Topology
```
                     INTERNET
                        |
                        v
              Azure Public IP (`pip-aerion-staging`)
                [172.198.75.129]
                        |
                        v
        Network Security Group (`nsg-aerion-staging`)
        - Inbound: Port 22 (SSH), Port 80 (HTTP), Port 443 (HTTPS)
        - Deny All direct inbound to 5432 / 8000
                        |
                        v
               Nginx Reverse Proxy (Port 80)
            - Reverse proxy to internal Uvicorn
            - Enforces client request size limits
            - Upstream timeouts configured for async 202 jobs
                        |
                        v
        +-----------------------------------------------+
        | Azure Virtual Machine (`vm-aerion-staging`)   |
        | SKU: Standard_DS2_v2                          |
        | 2 vCPUs (Intel Xeon Platinum 8370C @ 2.80GHz) |
        | 7.0 GiB RAM + 4.0 GiB Swap File               |
        | 30 GB Managed OS Disk (Standard SSD LRS)      |
        | OS: Ubuntu 24.04 LTS x86_64                   |
        |                                               |
        | Processes:                                    |
        |  * systemd (`aerion.service`)                 |
        |  * FastAPI / Uvicorn (127.0.0.1:8000)         |
        |  * Local PostgreSQL 16 + PostGIS 3.4.2        |
        |  * PyTorch 2.14.0+cpu ML Inference Runtimes   |
        +-----------------------+-----------------------+
                                |
                                v
               Azure Blob Storage (`staerionstaging01`)
             - Container: `aerion-evidence`
             - Secure HTTPS connection (TLS 1.2 minimum)
             - Evidence SHA-256 metadata verification
```

### 2.2 Provisioned Resource Inventory
All resources reside in a single resource group tagged for governance and cost tracking:
- **Subscription**: `Azure for Students` (`81b4cad7-e593-4eaf-9029-90138718f352`)
- **Resource Group**: `rg-aerion-staging`
- **Location**: `indiasouthcentral`
- **Tags**: `project=AERION`, `environment=staging`, `managed-by=antigravity`

| Resource Name | Type | SKU / Configuration | Purpose |
| :--- | :--- | :--- | :--- |
| `vm-aerion-staging` | Virtual Machine | `Standard_DS2_v2` (2 vCPU, 7.0 GiB RAM) | Backend compute & inference node |
| `osdisk_aerion_staging` | Managed Disk | 30 GB Standard SSD LRS | OS, application binaries, and PostgreSQL data |
| `pip-aerion-staging` | Public IP Address | Standard Static IPv4 (`172.198.75.129`) | Gateway entry point |
| `nic-aerion-staging` | Network Interface | Standard NIC | Attached to VNet & NSG |
| `vnet-aerion-staging` | Virtual Network | `10.0.0.0/16` (`snet-aerion-staging`: `10.0.1.0/24`) | Isolated private networking |
| `nsg-aerion-staging` | Network Security Group | Security Rules: Ports 22, 80, 443 open | Perimeter firewall |
| `staerionstaging01` | Storage Account | Standard_LRS, StorageV2, TLS 1.2 | Evidence artifact preservation |

---

## 3. SKU Selection & Quota Policy Justification

### 3.1 Primary Candidate Evaluation (`Standard_D2as_v5`)
The original plan specified `Standard_D2as_v5` (AMD EPYC). Upon querying the Azure Compute Resource SKU API with the subscription credentials:
- Subscription policy `sys.regionrestriction` strictly limited resource creation to a designated regional subset: `indiasouthcentral`, `koreacentral`, `malaysiawest`, `uaenorth`, `eastasia`.
- An explicit regional quota check revealed that **`standardDASv5Family` possessed a limit of 0 cores** for this *Azure for Students* subscription in `indiasouthcentral`, `koreacentral`, and `eastasia`. Attempting to allocate `Standard_D2as_v5` yielded quota failure `OperationNotAllowed`.

### 3.2 Chosen SKU: `Standard_DS2_v2`
- **CPU Family**: `standardDSv2Family` (Approved quota limit: 4 vCPUs; 2 vCPUs utilized).
- **Compute Architecture**: Intel Xeon Platinum 8370C @ 2.80GHz, 2 hardware threads, x86_64.
- **Memory**: 7.0 GiB physical RAM.
- **Burstable vs Non-Burstable**: Non-burstable compute (unlike B-series burstable VMs which throttle on sustained CPU inference), ensuring consistent inference latencies for OpenCV video frame decoding and ConvNet Siamese models.
- **Pricing**: ~$0.169/hour retail Linux consumption.

---

## 4. Operating System & Software Stack

### 4.1 System Packages
- **Distribution**: Ubuntu 24.04 LTS (Kernel 6.8.0-1018-azure x86_64)
- **Runtimes**:
  - Python: `3.12.3`
  - PostgreSQL: `16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)`
  - PostGIS: `3.4.2`
  - Nginx: `1.24.0`
  - Swap: 4.0 GiB swapfile configured at `/swapfile` (swappiness=10) to guard against sudden OOM spikes during batch video analysis.

### 4.2 Python Virtual Environment (`/home/aerion/venv-aerion`)
- **PyTorch**: `2.14.0+cpu` (Strictly verified `torch.cuda.is_available() == False`)
- **Torchvision**: `0.29.0+cpu`
- **Ultralytics**: `8.4.148`
- **OpenCV**: `opencv-python-headless 5.0.0.93`
- **Azure SDK**: `azure-storage-blob 12.30.1`
- **FastAPI / Uvicorn**: `0.115.0` / `0.30.6`
- **Database Adapters**: `asyncpg 0.29.0`, `psycopg2-binary 2.9.9`, `GeoAlchemy2 0.15.2`

---

## 5. PostgreSQL & PostGIS Configuration

PostgreSQL runs locally on `127.0.0.1:5432` and is strictly forbidden from listening on the public network interface.

### 5.1 Database Provisioning
- Database: `aerion`
- Role: `aerion_user` (granted `ALL PRIVILEGES`)
- Extensions enabled: `postgis`

### 5.2 Schema Migrations
All migrations were applied sequentially using Alembic:
```bash
alembic upgrade head
```
Head revision: `a1b2c3d4e5f6` (`extend_analysis_jobs_lifecycle`).
Total relations verified: 28 tables, including `analysis_jobs`, `evidence_items`, `projects`, `shelters`, `situations`, and `users`.

---

## 6. Azure Blob Storage Integration

### 6.1 Storage Architecture
Evidence artifacts generated during pipeline execution (such as annotated JPEG images and extracted video frame bundles) are stored with SHA-256 content hashes.
- Storage Account: `staerionstaging01`
- Container: `aerion-evidence`
- Public Access: Disabled (`--public-access off`). Blobs are written securely using the storage account connection string configured via environment variables.

### 6.2 Application Layer Integration
`app/services/storage_service.py` was enhanced to mirror artifacts to Azure Blob Storage while retaining local storage cache:
- When `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_STORAGE_CONTAINER_NAME` are defined, `store_artifact()` persists the file to Azure Blob Storage and associates the blob name and content hash.
- Verification: Upload of `b9a12db1-0427-4d8b-8b94-288c9512eccb.jpg` (835,503 bytes) and `bc437dba-1a7f-4b0e-8b33-aecbf6c4558c.mp4` (4,833,417 bytes) confirmed in `staerionstaging01`.

---

## 7. Service Supervision & Reverse Proxy

### 7.1 Systemd Service (`aerion.service`)
Configured at `/etc/systemd/system/aerion.service`:
```ini
[Unit]
Description=AERION FastAPI Geospatial Backend
After=network.target postgresql.service

[Service]
Type=simple
User=aerion
WorkingDirectory=/home/aerion/aerion-backend
EnvironmentFile=/home/aerion/aerion-backend/.env
ExecStart=/home/aerion/venv-aerion/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
- Status: `active (running)`
- Restart resilience: Automatically restarts within 3 seconds if the worker process terminates.

### 7.2 Nginx Configuration
Configured at `/etc/nginx/sites-available/aerion`:
```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

---

## 8. Security Controls & Posture
1. **Network Boundary**:
   - NSG rules restrict incoming internet traffic to ports 22, 80, and 443.
   - Direct access to PostgreSQL (5432) and FastAPI (8000) from the internet is completely blocked.
2. **Authentication & Access**:
   - VM SSH access uses ED25519 public key cryptography. Password authentication is disabled on the SSH daemon.
   - Private keys are stored on the operator's local machine and never committed.
3. **Application Secrets**:
   - Stored exclusively in server-side `/home/aerion/aerion-backend/.env`.
   - `.env` is git-ignored and never committed or tracked in version control.
4. **Blob Storage**:
   - Public anonymous blob access is disabled.
   - SAS tokens or service-side authenticated clients are required for all read/write operations.

---

## 9. Staging Operational Procedures

### 9.1 Starting and Stopping the Staging Environment
To conserve Azure for Students credits when not testing:
```bash
# Deallocate VM (compute billing stops, only storage incurs minor fee)
az vm deallocate --resource-group rg-aerion-staging --name vm-aerion-staging

# Start VM for testing
az vm start --resource-group rg-aerion-staging --name vm-aerion-staging
```

### 9.2 Inspecting Service Logs
```bash
ssh -i ~/.ssh/id_aerion_azure aerion@172.198.75.129 "journalctl -u aerion -f"
```
