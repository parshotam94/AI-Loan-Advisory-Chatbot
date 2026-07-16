import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Page Configuration
st.set_page_config(
    page_title="AI Loan Advisory Agent & Dashboard",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend REST API configuration
# Render sets the PORT environment variable automatically for the web service
import os

if "RENDER" in os.environ:
    API_URL = "http://127.0.0.1:5000/api"
else:
    API_URL = "http://localhost:5000/api"


# Initialize session state for admin access
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# Decorator to turn this function into a pop-up modal
@st.dialog("🔒 Admin Authentication Required")
def login_dialog():
    st.write("Please enter your credentials to access the Admin Dashboard & Analysis.")
    
    # Username and Password input fields
    username = st.text_input("Username", placeholder="e.g., admin")
    password = st.text_input("Password", type="password", placeholder="••••••••")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Submit", type="primary"):
            if username == "admin" and password == "123":
                st.session_state.admin_authenticated = True
                st.success("Access Granted!")
                st.rerun()  # Rerun to close the dialog and render the admin page
            else:
                st.error("Invalid credentials.")


# Helper function to communicate with Flask server safely
def call_api(method: str, endpoint: str, json_data: dict = None, files: dict = None):
    url = f"{API_URL}/{endpoint}"
    try:
        if method.upper() == "POST":
            if files:
                # Use longer timeout for PDF uploads & indexing
                response = requests.post(url, files=files, timeout=60)
            else:
                response = requests.post(url, json=json_data, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            response = requests.get(url, timeout=30)
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            try:
                error_msg = response.json().get("error", "Unknown server error.")
            except Exception:
                error_msg = response.text
            st.error(f"Server Error: {error_msg}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the Flask API backend. Please ensure `python app.py` is running on port 5000.")
        return None
    except Exception as e:
        st.error(f"An unexpected exception occurred: {str(e)}")
        return None

# Initialize local application session state variables
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ----------------------------------------------------------------------
# SIDEBAR NAVIGATION
# ----------------------------------------------------------------------
st.sidebar.title("💼 AI Loan Advisor")
st.sidebar.markdown("---")
view_mode = st.sidebar.radio(
    "Navigation Portal",
    ["User Chat Assistant", "Admin Dashboard & Analytics"]
)
st.sidebar.markdown("---")
st.sidebar.info(
    "This production-grade system uses semantic routing, "
    "dense FAQ search, rule engines, and RAG document context "
    "retrieval."
)

# ----------------------------------------------------------------------
# PORTAL 1: USER CHAT ASSISTANT
# ----------------------------------------------------------------------
if view_mode == "User Chat Assistant":
    st.title("🗣️ AI Loan Advisor Agent")
    st.markdown(
        "Ask questions about our policies, calculate loan payments (EMI), "
        "evaluate your application eligibility, or compare multi-document conditions."
    )

    # Prompt guidance options
    with st.expander("💡 Pro-Tips for Querying the Agent", expanded=False):
        st.markdown("""
        Our advisor routes your messages to specialized tools automatically:
        1. **FAQ Retrieval:** Ask general questions, like *"What are your document requirements?"* or *"How long is approval?"*
        2. **EMI Calculator:** Type parameters like *"Calculate EMI for a loan of $500,000 at 5.5% for 30 years"*
        3. **Eligibility Checker:** Enter details like *"Am I eligible if my credit score is 720, income is 8000, and age is 34?"*
        4. **Comparative Analysis:** Type *"Compare interest rates and prepayment charges across our policies"*
        """)

    st.markdown("---")

    # Display conversational thread
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat["role"] == "assistant":
                # Meta-information panel
                cols = st.columns(4)
                with cols[0]:
                    st.caption(f"🔧 Tool: {chat.get('tool', 'N/A')}")
                with cols[1]:
                    st.caption(f"🎯 Confidence: {chat.get('confidence', 'N/A')}")
                with cols[2]:
                    st.caption(f"⚡ Latency: {chat.get('latency', 'N/A')}s")
                with cols[3]:
                    st.caption(f"📄 Sources: {chat.get('sources', 'N/A')}")

    # Standard Chat Input Box
    user_query = st.chat_input("Enter your loan query here...")

    if user_query:
        # Append and render user statement
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Contact REST backend for evaluation
        with st.spinner("Analyzing request and formulating response..."):
            res = call_api("POST", "chat", json_data={"query": user_query})

        if res:
            answer = res.get("answer", "No response received.")
            tool = res.get("tool", "Unknown")
            confidence = res.get("confidence", 0.0)
            latency = res.get("latency", 0.0)
            sources = res.get("sources", "None")

            # Append and render agent statement
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer,
                "tool": tool,
                "confidence": confidence,
                "latency": latency,
                "sources": sources
            })
            
            with st.chat_message("assistant"):
                st.markdown(answer)
                cols = st.columns(4)
                with cols[0]:
                    st.caption(f"🔧 Tool: {tool}")
                with cols[1]:
                    st.caption(f"🎯 Confidence: {confidence}")
                with cols[2]:
                    st.caption(f"⚡ Latency: {latency}s")
                with cols[3]:
                    st.caption(f"📄 Sources: {sources}")

# ----------------------------------------------------------------------
# PORTAL 2: ADMIN DASHBOARD & ANALYTICS (GATED BY DIALOG AUTH)
# ----------------------------------------------------------------------
else:
    # 1. Gate: Verify authentication state
    if not st.session_state.admin_authenticated:
        # Trigger pop-up automatically
        login_dialog()
        
        # Display elegant, secure fallback interface
        st.title("📊 Operational Dashboard & System Admin")
        st.subheader("🔒 Restricted Access Portal")
        st.warning("You must authenticate as an administrator to access system analytics, policy indexing, and FAQ databases.")
        
        # Provide helper manual trigger in case they click away
        if st.button("🔑 Open Login Interface", type="primary"):
            login_dialog()
            
    else:
        # 2. Access Granted: Render the actual Admin Interface
        col_title, col_logout = st.columns([8, 2])
        with col_title:
            st.title("📊 Operational Dashboard & System Admin")
        with col_logout:
            if st.button("🚪 Log Out", type="secondary", use_container_width=True):
                st.session_state.admin_authenticated = False
                st.rerun()

        st.divider()
        
        # Retrieve system-wide stats
        stats = call_api("GET", "analytics")
        
        if stats:
            # Main Stat KPI Metrics Bar
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Documents Indexed", stats.get("total_pdfs", 0))
            col2.metric("Total Chunked Vectors", stats.get("total_chunks", 0))
            col3.metric("Queries Processed", stats.get("total_queries", 0))
            col4.metric("Avg Latency", f"{stats.get('avg_latency', 0.0)}s")

            st.markdown("---")

            # Create Tab layout to separate concerns cleanly
            tab_analytics, tab_docs, tab_faq = st.tabs([
                "📈 System Analytics", 
                "📂 Manage Loan Policies", 
                "❓ Manage System FAQs"
            ])

            # TAB 1: ANALYTICS & MACHINE LEARNING METRICS
            with tab_analytics:
                st.subheader("System Performance & Behavioral Analytics")
                
                logs_list = stats.get("chat_logs", [])
                if not logs_list:
                    st.warning("No conversation logs found in database. Ask questions in the Chat panel to generate analytics.")
                else:
                    df = pd.DataFrame(logs_list)
                    # Parse timestamps
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df["date"] = df["timestamp"].dt.date

                    # Display Dashboard Layout Mockup reference image contextually
                    st.caption("Monitoring real-time API transactions & performance metrics:")
                    st.image("uploads/agent.png", caption="Operational KPI & Analysis Visual Interface", width=550)

                    col_left, col_right = st.columns(2)

                    with col_left:
                        # Chart A: Tool Distribution Split
                        st.write("**Agent Tool Selection Distribution**")
                        tool_counts = df["tool_used"].value_counts().reset_index()
                        tool_counts.columns = ["Tool Used", "Total Requests"]
                        fig_pie = px.pie(
                            tool_counts, 
                            names="Tool Used", 
                            values="Total Requests", 
                            color_discrete_sequence=px.colors.qualitative.Bold,
                            hole=0.4
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)

                    with col_right:
                        # Chart B: Query Volume over Time
                        st.write("**Daily Query Volume**")
                        daily_counts = df.groupby("date").size().reset_index(name="Queries")
                        fig_line = px.line(
                            daily_counts, 
                            x="date", 
                            y="Queries", 
                            markers=True,
                            labels={"date": "Timeline", "Queries": "Volume"}
                        )
                        fig_line.update_layout(xaxis_tickformat="%Y-%m-%d")
                        st.plotly_chart(fig_line, use_container_width=True)

                    # Row 2: Latency & Confidence Analysis
                    col_left_2, col_right_2 = st.columns(2)
                    
                    with col_left_2:
                        st.write("**Subsystem Query Latency (Seconds)**")
                        fig_box_lat = px.box(
                            df, 
                            x="tool_used", 
                            y="latency", 
                            color="tool_used",
                            labels={"tool_used": "Routed Tool", "latency": "Latency (s)"}
                        )
                        st.plotly_chart(fig_box_lat, use_container_width=True)

                    with col_right_2:
                        st.write("**Confidence Score Distribution by Subsystem**")
                        fig_box_conf = px.box(
                            df, 
                            x="tool_used", 
                            y="confidence", 
                            color="tool_used",
                            labels={"tool_used": "Routed Tool", "confidence": "Score (0 - 1)"}
                        )
                        st.plotly_chart(fig_box_conf, use_container_width=True)

                    # Raw Analytics Logs
                    st.write("**Raw System Interaction Logs**")
                    st.dataframe(
                        df[["id", "question", "tool_used", "confidence", "latency", "sources", "timestamp"]],
                        use_container_width=True
                    )

            # TAB 2: DOCUMENT INGESTION & DELETION
            with tab_docs:
                st.subheader("Document Corpus Management")
                
                col_u_l, col_u_r = st.columns([1, 2])
                with col_u_l:
                    st.write("**Upload New Loan Policy PDF**")
                    uploaded_file = st.file_uploader("Select Policy PDF", type=["pdf"])
                    if st.button("Index & Ingest Document", use_container_width=True):
                        if uploaded_file:
                            with st.spinner(f"Ingesting and indexing {uploaded_file.name}..."):
                                # Read raw payload bytes
                                files_payload = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                                result = call_api("POST", "upload", files=files_payload)
                                if result:
                                    st.success(f"Indexed {uploaded_file.name} successfully! Chunks: {result.get('chunks')}")
                                    st.rerun()
                        else:
                            st.warning("Please choose a valid local PDF file first.")
                
                with col_u_r:
                    st.write("**Global Database Rebuild**")
                    st.info("If vector representations or databases appear desynchronized, trigger a complete rebuild of the vector space.")
                    if st.button("Trigger Deep Database Rebuild", type="primary"):
                        with st.spinner("Rebuilding indexes (Parsing files & re-embedding)..."):
                            rebuild_res = call_api("POST", "rebuild")
                            if rebuild_res:
                                st.success(f"Rebuild finished! Processed: {rebuild_res.get('processed_documents')} documents.")
                                st.rerun()

                st.markdown("---")
                st.write("**Currently Indexed Policy Documents**")
                
                docs_list = call_api("GET", "documents")
                if docs_list:
                    df_docs = pd.DataFrame(docs_list)
                    df_docs["size_kb"] = (df_docs["file_size"] / 1024).round(2)
                    
                    # Dynamic rendering with action delete buttons
                    for idx, row in df_docs.iterrows():
                        cols = st.columns([3, 2, 2, 2, 2])
                        cols[0].write(f"📄 **{row['filename']}**")
                        cols[1].write(f"Chunks: {row['chunk_count']}")
                        cols[2].write(f"Size: {row['size_kb']} KB")
                        cols[3].write(f"Uploaded: {row['upload_time']}")
                        
                        if cols[4].button("Delete Document & Clear Index", key=f"del_doc_{row['id']}", use_container_width=True):
                            with st.spinner("Deleting document components..."):
                                del_res = call_api("DELETE", f"document/{row['filename']}")
                                if del_res:
                                    st.success(f"Deleted {row['filename']}.")
                                    st.rerun()
                else:
                    st.info("No policy documents found in system index storage. Upload a document to get started.")

            # TAB 3: FAQ MANAGEMENT
            with tab_faq:
                st.subheader("FAQ Database Registry Management")
                
                col_f_l, col_f_r = st.columns([1, 2])
                
                with col_f_l:
                    st.write("**Add New FAQ Entry**")
                    new_q = st.text_input("Question Pattern")
                    new_a = st.text_area("Authorized Response")
                    if st.button("Save & Generate Embedding", use_container_width=True):
                        if new_q and new_a:
                            with st.spinner("Generating dense FAQ representation..."):
                                faq_res = call_api("POST", "faq", json_data={"question": new_q, "answer": new_a})
                                if faq_res:
                                    st.success("FAQ successfully added.")
                                    st.rerun()
                        else:
                            st.warning("All input fields are required.")

                with col_f_r:
                    st.write("**Registered FAQ Patterns**")
                    faqs_list = call_api("GET", "faqs")
                    if faqs_list:
                        for faq in faqs_list:
                            with st.container():
                                st.markdown(f"❓ **{faq['question']}**")
                                st.markdown(f"💬 *{faq['answer']}*")
                                if st.button("Delete Pattern", key=f"del_faq_{faq['id']}", type="secondary"):
                                    with st.spinner("Removing..."):
                                        del_faq_res = call_api("DELETE", f"faq/{faq['id']}")
                                        if del_faq_res:
                                            st.success("FAQ deleted.")
                                            st.rerun()
                                st.markdown("---")
                    else:
                        st.info("No FAQs stored in system. Populate by executing `python train_faq.py` or use the registry manager.")