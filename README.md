# AILP: Adaptive AI Learning Partner

An enterprise-grade, personalized AI tutoring system built with **LangGraph**, **Azure AI Foundry**, **Azure OpenAI**, **Azure Cosmos DB**, **Azure AI Search**, and **OpenTelemetry**.

AILP dynamically adapts to a student's age, grade, preferred language, and learning style. It features stateful conversation memory, parallel long-term preference extraction, native multimodal vision, curriculum-grounded RAG, sandboxed code execution, and enterprise observability.

---

## Architecture Overview

```
                                      +------------------------------------+
                                      |            Student Input           |
                                      +-----------------+------------------+
                                                        |
                                                        v
                                      +-----------------+------------------+
                                      |              images                |
                                      | (Blob Upload + SAS URL Generation) |
                                      +-----------------+------------------+
                                                        |
                                                        v
                                      +-----------------+------------------+
                                      |          pii_redaction             |
                                      |  (Masks Phone/Email in Cosmos DB)  |
                                      +-----------------+------------------+
                                                        |
                                                        v
                                      +-----------------+------------------+
                                      |          retrieve_ltm              |
                                      |   (Cosmos DB BaseStore LTM Read)   |
                                      +--------+------------------+--------+
                                               |                  |
                         +---------------------+                  +---------------------+
                         | (Parallel Branch)                                            | (Main Branch)
                         v                                                              v
      +------------------+------------------+                    +----------------------+--------------------+
      |           call_ltm_agent            |                    |                    call_agent             |
      | (Phi-4: Memory Extraction on Turn N)|                    |         (gpt-5-mini: Main Agent)          |
      +------------------+------------------+                    +----------------------+--------------------+
                         |                                                              |
                         v                                                              v
      +------------------+------------------+                    +----------------------+--------------------+
      |                Cosmos               |                    |                   tools_router            |
      |            BaseStore Put            |                    +----------+--------------------+-----------+
      +------------------+------------------+                               |                    |
                         |                                       (Has Tool Calls)       (Direct Text)
                         v                                                  |                    |
                       [END]                                                v                    v
                                                         +------------------+---+              [END]
                                                         |      tools_node      |
                                                         |  - query_curriculum  |
                                                         |  - stem_sandbox_tool |
                                                         |  - read_pages        |
                                                         |  - respond           |
                                                         +----------+-----------+
                                                                    |
                                                                    v
                                                         +----------+-----------+
                                                         |  route_after_tools   |
                                                         +----------+-----------+
                                                                    |
                                                      +-------------+-------------+
                                                      |                           |
                                               ("respond" called)          (More tools needed)
                                                      |                           |
                                                      v                           v
                                                    [END]                   -> call_agent
```

---

## Key Capabilities

### 1. Multi-Tier Memory System
* **Short-Term Memory (STM):** Conversation threads and checkpoints are persisted in Azure Cosmos DB (`CosmosDBSaverSync`) using `/partition_key` partitioning.
* **Long-Term Memory (LTM):** User personal facts and study habits are isolated in a Cosmos DB BaseStore (`CosmosDBStore`) using namespace partitioning (`/prefix`).
* **Parallel LTM Extraction:** A lightweight model (`Phi-4`) runs asynchronously in parallel with the main agent every 5 turns, extracting persistent student habits without delaying chat responses.

### 2. High-Performance Multimodal Vision
* Ingests local image paths or raw uploads.
* Converts images to lightweight 7-day Azure Blob SAS URLs in an asynchronous background thread pool.
* Completely resolves the Cosmos DB 2MB document limit (SAS URLs $\approx$ 380 bytes vs raw base64 $\approx$ 2–5MB).
* Passes SAS URLs directly to `gpt-5-mini` native vision, achieving 1–3s latency compared to 70s+ vision-to-text pipelines.

### 3. Privacy & Zero-Latency Guardrails
* **PII Redaction:** Regex-based sanitization node scrubs Egyptian and international phone numbers and email addresses into masked placeholders (`**********`) before state persistence in Cosmos DB.
* **Zero-Latency Content Safety:** Enforces Azure OpenAI built-in gateway content filters (`Microsoft.DefaultPolicy`) directly on the model endpoint with 0ms added network latency.

### 4. Curriculum RAG & Tool Ecosystem
* **Azure AI Search:** Vector + Semantic hybrid search across indexed educational textbooks (`query_curriculum`).
* **Azure Container Apps Dynamic Sessions:** Provides an isolated, ephemeral Python LTS sandbox for math, scientific equations, and logic execution (`stem_sandbox_tool`).
* **Source Attribution:** The custom `respond` tool enforces verified citation linking on every factual response.

### 5. Enterprise Observability & OpenTelemetry
* Built with `azure-monitor-opentelemetry` and Azure Application Insights.
* OpenTelemetry GenAI semantic conventions implemented (`gen_ai.conversation.id`, `gen_ai.tool.*`, `gen_ai.completion`).
* Visual waterfall Gantt charts and span latencies integrated directly into the **Azure AI Foundry Studio Tracing** dashboard.

---

## Project Structure

```
AILP/
├── Agent/
│   ├── agent.py               # Core LangGraph state machine & OpenTelemetry spans
│   └── Tools/
│       ├── tools.py           # Tool definitions (curriculum search, sandbox, respond)
│       └── utils/
│           ├── analyze_images.py  # SAS URL generation & async blob upload pipeline
│           ├── pii.py             # Phone & email redaction engine
│           └── latency_tracker.py # Console performance summary logger
├── RAG/                       # Ingestion utilities & search index helpers
├── setup/
│   ├── deploy.bicep           # Complete Infrastructure-as-Code (IaC) deployment
│   ├── deploy.ps1             # PowerShell automated provisioning script
│   ├── deploy.sh              # Bash automated provisioning script
│   ├── create_blob_containers.py # Blob storage container initialization
│   └── create_index.py        # Azure AI Search index schema & vector store creator
├── UI/
│   ├── server.py              # Async HTTP web server
│   ├── index.html             # Chat UI interface
│   └── style.css              # Glassmorphic responsive styling
├── config.py                  # Global thresholds, system prompts & categories
├── requirements.txt           # Python package dependencies
├── .env.example               # Template for environment variables
└── README.md                  # Project documentation
```

---

## Infrastructure Deployment (Azure Bicep)

All cloud resources are provisioned via Infrastructure-as-Code in `setup/deploy.bicep`:

| Resource | Service | Purpose |
| :--- | :--- | :--- |
| `aiFoundry` | Azure Cognitive Services (`AIServices`) | Model deployments (`gpt-5-mini`, `Phi-4`, `DeepSeek-V4-Flash`, `text-embedding-3-small`) |
| `aiProject` | Azure AI Foundry Project | Foundry Studio workspace and management |
| `searchService` | Azure AI Search (Basic) | Vector and hybrid search knowledge base |
| `cosmosAccount` | Azure Cosmos DB (SQL API) | STM Checkpoints, LTM BaseStore, User Gradings |
| `storageAccount`| Azure Blob Storage | Educational books, extracted pages, and multimodal image uploads |
| `sessionPool` | Azure Container Apps Dynamic Sessions | Sandboxed Python code execution pool |
| `logAnalyticsWorkspace` | Log Analytics | Centralized log workspace |
| `appInsights` | Application Insights | OpenTelemetry trace ingestion and monitoring |
| `appInsightsConnection` | Foundry Project Connection | Connects Application Insights to Foundry Tracing tab |

### Deploy via Azure CLI:
```bash
az login
az group create --name AILP --location australiaeast
az deployment group create --resource-group AILP --template-file setup/deploy.bicep
```

---

## Getting Started

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/RealGobz/AILP.git
cd AILP
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your endpoints from the Bicep deployment outputs:
```bash
cp .env.example .env
```

### 3. Run the Agent

**Interactive Console Mode:**
```bash
python -m Agent.agent
```

**Web UI Mode:**
```bash
python UI/server.py
```
Open your browser to `http://localhost:8080`.

---

## Viewing Traces in Azure AI Foundry

1. Navigate to [ai.azure.com](https://ai.azure.com) and open your project.
2. Select **Tracing** from the left-hand navigation.
3. Filter by Name: `agent_turn` or by your Conversation ID (`thread_id`).
4. Click on any turn to inspect the full waterfall Gantt chart showing the exact latency and inputs/outputs of every node and tool.

---

## License

This project is licensed under the MIT License.
