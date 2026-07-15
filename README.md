```markdown
# 💼 AI Loan Advisory Agent & Dashboard

A production-grade, dual-portal web application designed for automated financial customer service and credit operations. The system serves two primary stakeholder personas: general users seeking loan intelligence through an intelligent chat agent, and administrators managing the underlying knowledge base, document corpus, and operational performance metrics.

The project acts as an intelligent frontend orchestration layer built with **Streamlit** that communicates with a decoupled **Flask REST API backend** using **Semantic Routing**, **Dense FAQ Retrieval**, **Rule-Based Automation**, and **Retrieval-Augmented Generation (RAG)**.


* **Pre-Trained FAQ Base (`train_faq.py`):** 
  The system includes a training script that processes a structured collection of baseline frequently asked questions. It generates dense vector representations (embeddings) of these questions and saves them to the vector database (`data/chroma_db`), allowing the agent to perform ultra-fast semantic similarity searches when users ask common questions.
  
* **Dynamic Admin Registry Management:** 
  Administrators don't need to touch code or run scripts to update the system. Through the **Manage System FAQs** tab in the Admin Dashboard, authorized users can dynamically type in new question-and-answer pairs. The system instantly generates vector embeddings for the new patterns on the fly and inserts them directly into the active database, making them immediately available to the user chat agent without requiring a server reboot.

---

## 🛠️ System Architecture & How It Works


```

```
                 +---------------------------------------+
                 |  Streamlit Frontend (UI Portal)       |
                 +-------------------+-------------------+
                                     |
                                     | REST API (Port 5000)
                                     v
                 +-------------------+-------------------+
                 |  Flask REST API Backend (Server)      |
                 +-------------------+-------------------+
                                     |
     +-------------------+-----------+---------------+-------------------+
     |                   |                           |                   |

```

+--------v----------+ +------v-----------+ +-------------v---+ +-------------v----+
| FAQ Search Tool   | | EMI Calc Tool   | | Eligibility     | | RAG Document     |
| (Dense Vectors)   | | (Rule Engine)   | | Checker Engine  | | Retrieval Engine |
+-------------------+ +-----------------+ +-----------------+ +------------------+

```

### 🔄 The Operational Pipeline
1. **Query Ingestion:** The Streamlit app captures user input and sends a JSON payload to the Flask backend's `/api/chat` endpoint.
2. **Intent Classification (Semantic Routing):** The backend dynamically routes the query to the correct module (FAQ Search, EMI Calculator, Eligibility Checker, or RAG Policy Search).
3. **Retrieval-Augmented Generation (RAG):** If routed to policy search, the backend retrieves relevant text chunks from parsed PDF policies in the vector database and formats them with an LLM prompt.
4. **Telemetry Logging:** Every interaction registers backend performance data (latency, confidence scores, sources utilized, and tools executed), which is written to an database.
5. **Real-time Analytics:** The Admin Dashboard pulls these transaction records to dynamically update Plotly dashboards and system health metrics.

---

## ✨ Implemented Features

### 🗣️ 1. User Chat Assistant Portal
* **Automated Semantic Routing:** Instantly detects the user's intent to route queries to specialized sub-modules.
* **Pro-Tips Guidance:** Integrated helper interface highlighting example queries for EMI math, criteria evaluations, and document comparison.
* **Auditable Metadata Telemetry:** Every response prints real-time metrics showing:
  * 🔧 **Routed Tool**
  * 🎯 **Confidence Score**
  * ⚡ **Response Latency** (in seconds)
  * 📄 **Document Sources** (if evaluated using RAG)

### 📊 2. Admin Dashboard & Analytics (Gated)
* **Secure Dialog-Based Authentication:** Protected by an automatic Streamlit pop-up dialog utilizing session-state verification (`st.session_state.admin_authenticated`).
* **KPI Metrics Board:** High-level cards tracking indexed documents, total parsed text vectors, total queries, and average response times.
* **Visual Performance Studio:** High-fidelity Plotly charts including:
  * **Tool Distribution:** Pie charts tracking usage frequency of individual modules.
  * **Daily Query Volume:** Time-series line chart monitoring transactional spikes.
  * **System Latency & Confidence Analysis:** Interactive box plots evaluating speed and score reliability across system components.
* **Document Corpus Manager:** Direct file uploader to index raw loan policy PDFs, run deep vector-space rebuilds, or delete documents and purge active vectors dynamically.
* **Dense FAQ Registry:** Interactive forms to add, embed, or delete hardcoded system Q&A match pairings.

---

## ⚙️ Tech Stack

* **Frontend:** Streamlit, Pandas, Plotly Express
* **Backend Integration:** Requests (REST API client)
* **API Specifications:** JSON payloads, file streams (`multipart/form-data`) for PDF indexing.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.9+
* Active backend running on port `5000` (e.g., matching the Flask `app.py` implementation).

### Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone <your-repository-url>
   cd <repository-directory>

```

2. **Install Dependencies:**
```bash
pip install streamlit requests pandas plotly

```


3. **Verify Backend Status:**
Ensure your backend microservice is running locally:
```bash
# In your backend workspace
python app.py

```


*The frontend assumes the backend API is live at `http://localhost:5000/api`.*
4. **Launch the Streamlit App:**
```bash
streamlit run streamlit_app.py

```



---

## 🔒 Admin Credentials

For development and local evaluation, use the following administrator credentials to unlock the administrative analytics and management tools:

* **Username:** `admin`
* **Password:** `123`

```

```

```
## 📈 System Overview Report: AI Loan Advisory Agent & Dashboard

This project implements a production-grade, dual-portal web application designed for automated financial customer service and credit operations. The system serves two primary stakeholder personas: general users seeking loan intelligence and administrators managing the underlying knowledge base and operational metrics.

Architecturally, the project acts as an intelligent frontend orchestration layer that communicates with a decoupled **Flask REST API backend** (running on `http://localhost:5000`). It utilizes **Semantic Routing**, **Dense FAQ Retrieval**, **Rule-Based Automation**, and **Retrieval-Augmented Generation (RAG)** to provide highly accurate, contextual, and auditable responses.

---

## 🛠️ Implemented Features & Capabilities

The codebase is divided into two operational scopes controlled by a sidebar navigation portal:

### 1. User Chat Assistant Portal

This module functions as a smart conversational agent capable of parsing natural language queries and automatically routing them to specialized backend subsystems:

* **Semantic Routing & Tool Execution:** The system dynamically categorizes queries into four distinct tracks:
* *FAQ Retrieval:* For generalized customer queries regarding approval times and documentation requirements.
* *EMI Calculator:* A structured engine that handles financial math inputs (e.g., Principal, Interest Rate, Tenor).
* *Eligibility Checker:* A rule-based scoring engine evaluating age, income, and credit metrics.
* *Comparative Analysis:* A multi-document search pattern comparing policy frameworks.


* **Auditable Metadata Streams:** Every response returned by the assistant surfaces underlying operational telemetry to the user interface, including the precise tool utilized, model confidence scores, query latency in seconds, and source attribution.

### 2. Admin Dashboard & Analytics Portal (Authenticated)

A restricted workspace for system configurations, vector database maintenance, and machine learning analytics:

* **Session-State Dialog Gate:** Access is strictly guarded by a custom `@st.dialog` authentication modal requiring a matching username (`admin`) and password (`123`). The portal blocks rendering on the server side unless authenticated.
* **KPI Metrics Monitoring:** Displays high-level system indicators such as the total count of indexed policy documents, total chunked vectors, historical queries processed, and average network/inference latency.
* **Data Visualization Studio:** Integrates dynamic Plotly charts detailing the agent's tool distribution split, daily transaction volumes, and box plots analyzing query latency and confidence scores by tool type.
* **Document Corpus Management (RAG Pipeline Control):** Allows administrators to upload raw policy PDFs directly into the system, call deep database vector rebuilds, or selectively delete active documents to purge their associated vectors from the backend index.
* **Dense FAQ Registry Manager:** Allows line-of-business operators to inject or remove hardcoded Question/Answer pairings, triggering immediate vector embedding generation for the backend semantic match registry.

---

## 🔄 Technical Workflow: How It Works

```
[ User Input ] ---> [ Streamlit Frontend Portal ] ---> [ Flask REST API Backend ]
                                                            |
        +-------------------+---------------------------+-----------------------+
        |                   |                           |                       |
[ Tool: FAQ Search ]   [ Tool: EMI Calc ]    [ Tool: Eligibility ]    [ Tool: RAG Policy search ]
  (Dense Vectors)        (Rule Engine)          (Credit Logic)         (LangChain/Vector DB)

```

### Step 1: Query Ingestion and API Communication

When a user submits a prompt, the application appends the message to an active thread stored in `st.session_state.chat_history`. It triggers a `POST` request to the backend `/api/chat` endpoint using a centralized connection-resilient wrapper (`call_api`).

### Step 2: Backend Semantic Processing

The Flask API receives the payload and evaluates it against an orchestration pipeline:

1. **Intent Classification:** The system determines which tool is best equipped to handle the text string.
2. **Context Assembly (RAG):** If the request relies on policy details, the system queries the active vector index (populated via the Admin portal's document management interface), fetches the top matching text chunks, and binds them to the LLM prompt context window.
3. **Execution & Telemetry Logging:** The selected module processes the request, computes answers, registers performance statistics (latency, certainty metrics), and flushes the data log into an analytics database.

### Step 3: Frontend Render and Analytics Re-evaluation

The Streamlit application consumes the JSON payload response, instantly rendering the answer into the chat message bubble along with its individual metadata metrics. Concurrently, if an administrator is logged into the **Admin Dashboard**, refreshing or navigating tabs prompts a `GET` request to `/api/analytics`. The system updates Pandas dataframes instantly, refreshing the data visualization suites and data tables to match real-time system performance.
```
