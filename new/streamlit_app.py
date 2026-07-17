import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os

# App Config
st.set_page_config(page_title="AI Loan Advisory Agent & Dashboard", layout="wide")
st.image("workflow_graph.png", caption="System Workflow Diagram")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000/api")

def call_api(endpoint, method="GET", json_data=None, files=None):
    try:
        url = f"{BACKEND_URL}/{endpoint}"
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            if files:
                r = requests.post(url, files=files, timeout=30)
            else:
                r = requests.post(url, json=json_data, timeout=15)
        elif method == "DELETE":
            r = requests.delete(url, timeout=10)
        
        if r.status_code in [200, 201]:
            return r.json()
        else:
            return {"error": r.json().get("error", "An unknown backend error occurred.")}
    except Exception as e:
        return {"error": f"Failed to connect to backend: {str(e)}"}

# Initialize Conversational Chat History in Session State
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = [
        {"role": "assistant", "content": "Hello! I am your AI Loan Expert. Ask me about eligibility, loan terms, calculations, or policies."}
    ]

# Top Title
st.title("💼 AI Loan Advisory Agent & Portal")
st.write("---")

tab1, tab2 = st.tabs(["🗣️ User Chat Assistant", "📊 Admin Portal & Operations"])

# --- TAB 1: USER CHAT ASSISTANT (CONVERSATIONAL INTERFACE) ---
with tab1:
    st.subheader("Interactive AI Loan Expert")
    st.markdown("Select a quick prompt or type your custom query below:")
    
    # 1. Quick suggestion chips
    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        if st.button("📊 Sample EMI Math", use_container_width=True):
            st.session_state["pending_prompt"] = "EMI for 500000 at 8.5% for 10 years"
    with col_e2:
        if st.button("📋 Test Credit eligibility", use_container_width=True):
            st.session_state["pending_prompt"] = "Am I eligible? age 28, income 45000, credit 710"
    with col_e3:
        if st.button("❓ General Document Policy", use_container_width=True):
            st.session_state["pending_prompt"] = "What are the rules regarding collateral or loan guarantees?"

    # 2. Render Existing Chat Thread
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state["chat_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                # Show routing telemetry if present inside the message dictionary
                if "telemetry" in msg:
                    st.caption(msg["telemetry"])

    # 3. Capture User Input (either via chat_input box or clicked suggestion chips)
    user_query = st.chat_input("Enter your finance query here...")
    
    if "pending_prompt" in st.session_state:
        user_query = st.session_state.pop("pending_prompt")

    # 4. Handle Input Submission
    if user_query:
        # Display the user's message immediately
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_query)
        st.session_state["chat_messages"].append({"role": "user", "content": user_query})

        # Process Response with backend API
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Analyzing intent and routing via LangGraph..."):
                    response = call_api("chat", method="POST", json_data={"query": user_query})
                    
                    if "error" in response:
                        err_msg = f"⚠️ {response['error']}"
                        st.error(err_msg)
                        st.session_state["chat_messages"].append({"role": "assistant", "content": err_msg})
                    else:
                        ans_text = response["answer"]
                        st.markdown(ans_text)
                        
                        # Format dynamic telemetry metadata
                        telemetry_text = (
                            f"**Routed Subsystem:** {response.get('tool', 'N/A')} | "
                            f"**Confidence Metric:** {response.get('confidence', 'N/A')} | "
                            f"**Execution Latency:** {response.get('latency', 'N/A')}s | "
                            f"**Attributed Source:** {response.get('sources', 'N/A')}"
                        )
                        st.caption(telemetry_text)
                        
                        # Add to persistent history state with its metadata
                        st.session_state["chat_messages"].append({
                            "role": "assistant", 
                            "content": ans_text,
                            "telemetry": telemetry_text
                        })
        st.rerun()

# --- TAB 2: ADMIN PORTAL (AUTHENTICATED) ---
with tab2:
    st.subheader("System Administration & Analytics Dashboard")
    
    # Simple Authentication Gate
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        
    if not st.session_state["authenticated"]:
        st.warning("Locked section. Please authenticate to view analytical operations.")
        user_auth = st.text_input("Username", key="admin_user")
        pass_auth = st.text_input("Password", type="password", key="admin_pass")
        if st.button("Login", type="primary"):
            if user_auth == "admin" and pass_auth == "123":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid Username or Password.")
    else:
        if st.button("Log out", type="secondary"):
            st.session_state["authenticated"] = False
            st.rerun()

        st.success("Authorized Admin Mode Active.")
        st.write("---")
        
        # Load Operational Analytics Metrics
        analytics = call_api("analytics")
        if "error" in analytics:
            st.error("Could not fetch analytical logs from backend database.")
        else:
            # Metrics Dashboard Row
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Indexed Documents", analytics.get("total_pdfs", 0))
            col2.metric("Total Extracted Chunks", analytics.get("total_chunks", 0))
            col3.metric("Total Queries Processed", analytics.get("total_queries", 0))
            col4.metric("Avg Latency (seconds)", f"{analytics.get('avg_latency', 0.0)}s")

            # Analytical Plots
            st.write("---")
            st.subheader("Performance Metrics Studio")
            
            logs = analytics.get("chat_logs", [])
            if logs:
                df = pd.DataFrame(logs)
                
                # Plot 1: Tool Distribution Pie Chart
                fig1 = px.pie(df, names="tool_used", title="System Core Query Routing Distribution")
                
                # Plot 2: Daily query volume timeline
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                timeline_df = df.groupby(df["timestamp"].dt.date).size().reset_index(name="Queries")
                fig2 = px.line(timeline_df, x="timestamp", y="Queries", title="Operational Demand Trends")

                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.plotly_chart(fig1, use_container_width=True)
                with col_chart2:
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No queries logged yet to compile interactive metrics charts.")

            # Document Management Section
            st.write("---")
            st.subheader("Document Corpus Manager (RAG Index Controls)")
            
            uploaded_file = st.file_uploader("Upload official policy guidelines PDF to extend dynamic knowledge base:", type="pdf")
            if uploaded_file is not None:
                if st.button("Deploy & Index Document", type="primary"):
                    with st.spinner("Parsing guidelines..."):
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                        res = call_api("upload", method="POST", files=files)
                        if "error" in res:
                            st.error(res["error"])
                        else:
                            st.success(res["message"])
                            st.rerun()

            # Active documents table list
            docs_res = call_api("documents")
            if isinstance(docs_res, list) and len(docs_res) > 0:
                st.write("**Currently Indexed Documents:**")
                for d in docs_res:
                    col_file, col_btn = st.columns([4, 1])
                    col_file.write(f"📄 **{d['filename']}** ({d['chunk_count']} chunks) - Size: {round(d['file_size']/1024, 2)} KB")
                    if col_btn.button("Purge Vectors", key=d["filename"]):
                        call_api(f"document/{d['filename']}", method="DELETE")
                        st.success("Purged successfully.")
                        st.rerun()

            # FAQ dynamic registration module
            st.write("---")
            st.subheader("Manage System FAQs")
            
            with st.form("add_faq_form"):
                new_q = st.text_input("FAQ Question Pattern")
                new_a = st.text_area("Authorized Resolution Answer")
                submit_faq = st.form_submit_button("Vectorize FAQ Pair")
                
                if submit_faq:
                    if new_q.strip() and new_a.strip():
                        res = call_api("faq", method="POST", json_data={"question": new_q, "answer": new_a})
                        if "error" in res:
                            st.error(res["error"])
                        else:
                            st.success("FAQ dynamic vectors compiled and registered.")
                            st.rerun()

            # View Current FAQs
            faq_list = call_api("faqs")
            if isinstance(faq_list, list) and len(faq_list) > 0:
                st.write("**Registered Dynamic FAQs:**")
                for f in faq_list:
                    col_faq, col_del = st.columns([5, 1])
                    col_faq.write(f"**Q:** {f['question']} \n *A:* {f['answer']}")
                    if col_del.button("Delete FAQ", key=f"faq_{f['id']}"):
                        call_api(f"faq/{f['id']}", method="DELETE")
                        st.success("FAQ Deleted.")
                        st.rerun()