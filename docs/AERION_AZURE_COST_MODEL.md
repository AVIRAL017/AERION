# AERION v1 — Azure Staging Cost Model & Budget Projection

## 1. Executive Summary & Context
This document models the infrastructure expenditure for the **AERION v1** staging environment deployed under the active **Azure for Students** subscription ($100 initial credit, $0.00 current spend).

The deployment adheres strictly to the project rule: **Minimize always-on billable resources**. The staging infrastructure utilizes a single consolidated virtual machine hosting application, database, and reverse proxy layers, complemented by low-cost Azure Blob Storage.

---

## 2. Resource Pricing Breakdown (Public Retail / List Rates)

*Region: India South Central (`indiasouthcentral`)*  
*Currency: USD ($)*

| Resource Component | Specific SKU / Tier | Meter / Rate (Retail List) | Monthly Continuous (730 hrs) | Active Testing (4 hrs/day = 120 hrs/mo) |
| :--- | :--- | :--- | :--- | :--- |
| **Virtual Machine Compute** | `Standard_DS2_v2` (2 vCPU, 7 GiB RAM) | $0.1690 / hour | $123.37 | **$20.28** |
| **Managed OS Disk** | 30 GB Standard SSD (`E4` LRS) | ~$2.40 / month | $2.40 | $2.40 |
| **Static Public IP** | Standard IPv4 (`pip-aerion-staging`) | $0.0050 / hour | $3.65 | $3.65 |
| **Azure Blob Storage** | Hot LRS Storage (`staerionstaging01`) | $0.0184 / GB-month | ~$0.09 (for 5 GB) | ~$0.09 |
| **Data Egress / Transfer** | First 100 GB / month free (Azure Student) | $0.00 | $0.00 | $0.00 |
| **Total Estimated Spend** | — | — | **$129.51 / month** | **$26.42 / month** |

*Note: Prices reflect standard Microsoft Azure public retail rates for `indiasouthcentral` as of Q3 2024. Azure for Students applies $100 credit against billable services until exhausted.*

---

## 3. Comparison with Rejected Architectural Options

To prevent unnecessary credit depletion, expensive managed options were evaluated and explicitly rejected:

| Architecture Considered | Estimated Monthly Cost | Decision | Architectural Rationale |
| :--- | :--- | :--- | :--- |
| **Azure Database for PostgreSQL (Flexible Server)** | ~$58.00 / month (Burstable B1ms) to $140.00 (General Purpose) | **REJECTED** | Running PostgreSQL 16 + PostGIS locally on the VM costs $0 additional compute and yields 60.25 ms query latency. |
| **Azure Kubernetes Service (AKS)** | ~$150.00–$250.00 / month (node pools + control plane) | **REJECTED** | Massively over-engineered for staging single-tenant validation. |
| **Application Gateway / Load Balancer** | ~$35.00 / month | **REJECTED** | Nginx running locally handles reverse proxying, headers, and SSL termination at zero additional cost. |
| **GPU Compute (`Standard_NC4as_T4_v3`)** | ~$380.00+ / month | **REJECTED** | Violates student credit budget and unnecessary for staging validation. |

---

## 4. Cost Optimization Strategy: Deallocation Scheduling

Because compute represents **95% of the total monthly cost**, deallocating the staging virtual machine during idle hours protects the $100 student credit pool:

1. **Continuous Run (Unmanaged)**:
   - 24/7 runtime = $129.51/month → Would exhaust $100 student credit within **23 days**.
2. **Scheduled Test Runs (4 hours/day)**:
   - 120 hours/month = $26.42/month → Enables **3.8 months** of active development on the single $100 credit.
3. **Deallocation Command**:
   ```bash
   az vm deallocate --resource-group rg-aerion-staging --name vm-aerion-staging
   ```
   *When deallocated, compute charges drop to $0.00/hour. Only the $2.40/month disk allocation remains billable.*

---

## 5. Credit Monitoring Protocol
Operators must verify credit consumption periodically using the Azure Portal or CLI:
```bash
az consumption usage list --start-date 2026-09-01
```
If billing alerts are triggered or credits fall below $15.00, staging tests should be paused or restricted to essential gate validations.
