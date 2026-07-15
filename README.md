Here is the completely clean, consolidated, and properly formatted `README.md` file.

I removed all the broken code fence tags (`````), fixed the formatting errors in your ASCII architecture diagrams, organized the hybrid FAQ engine logic cleanly, and merged your technical analysis report directly into the file as a comprehensive system overview.

```markdown
# 💼 AI Loan Advisory Agent & Dashboard

A production-grade, dual-portal web application designed for automated financial customer service and credit operations. The system serves two primary stakeholder personas: general users seeking loan intelligence through an intelligent chat agent, and administrators managing the underlying knowledge base, document corpus, and operational performance metrics.

The project acts as an intelligent frontend orchestration layer built with **Streamlit** that communicates with a decoupled **Flask REST API backend** using **Semantic Routing**, **Dense FAQ Retrieval**, **Rule-Based Automation**, and **Retrieval-Augmented Generation (RAG)**.

---

## 🛠️ System Architecture & How It Works

```text
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
+-----v-------------+ +---v-------------+ +-----------v-----+ +-----------v------+
|  FAQ Search Tool  | |  EMI Calc Tool  | |  Eligibility  | |   RAG Document   |
|  (Dense Vectors)  | |  (Rule Engine)  | | Checker Engine| | Retrieval Engine |
+-------------------+ +-----------------+ +---------------+ +------------------+

```

### 🔄 The Operational Pipeline

1. **Query Ingestion:** The Streamlit app captures user input and sends a JSON payload to the Flask backend's `/api/chat` endpoint using a centralized connection-resilient wrapper (`call_api`).
2. **Intent Classification (Semantic Routing):** The backend dynamically determines which tool is best equipped to handle the incoming text string and routes it accordingly.
3. **Context Assembly (RAG):** If routed to the policy search track, the system queries the active vector index, fetches the top matching text chunks from the parsed PDF policies, and binds them directly to the LLM prompt context window.
4. **Execution & Telemetry Logging:** The selected module processes the request, computes answers, registers performance statistics (latency, certainty metrics), and flushes the data log into the backend analytics database.
5. **Real-time Analytics:** The Streamlit application consumes the payload response to render the answer along with its individual metadata metrics. Concurrently, the Admin Dashboard pulls these transaction records via a `GET` request to `/api/analytics` to update the data visualization suites instantly.

```text
[ User Input ] ---> [ Streamlit Frontend Portal ] ---> [ Flask REST API Backend ]
                                                            |
        +-------------------+---------------------------+-----------------------+
        |                   |                           |                       |
[ Tool: FAQ Search ]   [ Tool: EMI Calc ]    [ Tool: Eligibility ]    [ Tool: RAG Policy search ]
  (Dense Vectors)        (Rule Engine)          (Credit Logic)         (LangChain/Vector DB)

```

---

## ✨ Implemented Features

### 🗣️ 1. User Chat Assistant Portal

* **Automated Semantic Routing:** Instantly detects the user's intent to route queries to specialized sub-modules:
* *FAQ Retrieval:* For generalized customer queries regarding approval times and documentation requirements.
* *EMI Calculator:* A structured engine that handles financial math inputs (e.g., Principal, Interest Rate, Tenor).
* *Eligibility Checker:* A rule-based scoring engine evaluating age, income, and credit metrics.
* *Comparative Analysis:* A multi-document search pattern comparing policy frameworks.


* **Pro-Tips Guidance:** Integrated helper interface highlighting example queries for EMI math, criteria evaluations, and document comparison.
* **Auditable Metadata Telemetry:** Every response prints real-time metrics showing the **Routed Tool**, **Confidence Score**, **Response Latency** (in seconds), and **Document Sources**.

### 📊 2. Admin Dashboard & Analytics (Authenticated)

* **Session-State Dialog Gate:** Access is strictly guarded by a custom `@st.dialog` authentication modal requiring a matching username (`admin`) and password (`123`). The portal blocks rendering on the server side unless authenticated.
* **KPI Metrics Board:** High-level cards tracking indexed documents, total parsed text vectors, total queries, and average response times.
* **Visual Performance Studio:** High-fidelity Plotly charts including tool distribution pie charts, daily query volume timelines, and interactive box plots tracking subsystem query latency and confidence score spreads.
* **Document Corpus Manager (RAG Control):** Direct file uploader to index raw loan policy PDFs, run deep vector-space rebuilds, or selectively delete active documents to purge their associated vectors from the backend index.

### 🧠 3. Intelligent FAQ Subsystem (Dual-Method)

* **Pre-Trained FAQ Base (`train_faq.py`):** Includes an offline training script that processes a structured collection of baseline FAQs, generates dense vector representations (embeddings), and saves them to the vector database (`data/chroma_db`) for ultra-fast semantic similarity searches.
* **Dynamic Admin Registry Management:** Through the **Manage System FAQs** tab, administrators can dynamically type in new question-and-answer pairs. The system instantly generates vector embeddings for the new patterns on the fly and inserts them directly into the active database without requiring a server reboot.

---

## ⚙️ Tech Stack

* **Frontend UI:** Streamlit, Pandas, Plotly Express
* **Backend Integration:** Requests (REST API client)
* **Data Layer Integration:** JSON payloads, file streams (`multipart/form-data`) for PDF indexing.

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