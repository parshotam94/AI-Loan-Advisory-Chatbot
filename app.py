import os
import time
import sqlite3
import pickle
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from utils import (
    get_db_connection, 
    init_db, 
    extract_pdf_chunks, 
    ChromaDBManager, 
    VectorModel, 
    logger
)
from agent import LoanAgent

# Initialize Flask App
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "data/uploads"
app.config["PDF_FOLDER"] = "data/pdfs"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

# Instantiate core business systems
agent = LoanAgent()
chroma_manager = ChromaDBManager()

# Ensure directories exist
for folder in [app.config["UPLOAD_FOLDER"], app.config["PDF_FOLDER"]]:
    os.makedirs(folder, exist_ok=True)

# ----------------------------------------------------------------------
# 1. CORE AI CHAT CONVERSATION ENDPOINT
# ----------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Accepts user query, triggers the custom orchestrator LoanAgent,
    logs structural analytics metadata, and returns source-backed responses.
    """
    start_time = time.time()
    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Empty search query string provided."}), 400

    try:
        # Route query through agent logic
        response = agent.handle_query(query)
        latency = round(time.time() - start_time, 3)
        
        # Override response latency to ensure precise API measurement
        response["latency"] = latency

        # Store conversation metrics in SQLite database for live plotting
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO analytics (question, answer, tool_used, confidence, latency, sources)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                response["answer"],
                response["tool"],
                response["confidence"],
                response["latency"],
                response["sources"]
            )
        )
        conn.commit()
        conn.close()

        logger.info(f"API chat response generated via [{response['tool']}] in {latency}s")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error handling user chat endpoint request: {str(e)}")
        return jsonify({
            "answer": "A backend framework error occurred while processing your query.",
            "confidence": 0.0,
            "tool": "Error Handler",
            "sources": "None",
            "latency": round(time.time() - start_time, 3)
        }), 500


# ----------------------------------------------------------------------
# 2. DOCUMENT MANAGEMENT ENDPOINTS (ADMIN TOOLS)
# ----------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def upload_document():
    """Handles parsing, chunking, embedding generation, and DB storage for uploaded files."""
    if "file" not in request.files:
        return jsonify({"error": "No file field found in upload request."}), 400
        
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename selected."}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Unsupported format. Only PDF files allowed."}), 400

    filename = secure_filename(file.filename)
    dest_path = os.path.join(app.config["PDF_FOLDER"], filename)

    # Save to permanent storage
    file.save(dest_path)
    file_size = os.path.getsize(dest_path)

    try:
        # Parse PDF structure into overlapping chunks
        chunks = extract_pdf_chunks(dest_path)
        chunk_count = len(chunks)

        if chunk_count > 0:
            # Generate and format embeddings
            model = VectorModel.get_model()
            texts = [c["text"] for c in chunks]
            ids = [c["id"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]
            
            # SentenceTransformer produces list of numpy arrays -> convert to nested list
            embeddings = model.encode(texts, convert_to_numpy=True).tolist()

            # Store inside persistent ChromaDB instances
            chroma_manager.add_chunks(
                ids=ids,
                texts=texts,
                metadatas=metadatas,
                embeddings=embeddings
            )

        # Record metadata inside SQLite database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO documents (filename, chunk_count, file_size)
            VALUES (?, ?, ?)
            """,
            (filename, chunk_count, file_size)
        )
        conn.commit()
        conn.close()

        logger.info(f"Successfully uploaded and indexed policy document: {filename} ({chunk_count} chunks)")
        return jsonify({
            "message": f"Successfully parsed and indexed {filename}!",
            "filename": filename,
            "chunks": chunk_count,
            "size_bytes": file_size
        }), 200

    except Exception as e:
        logger.error(f"Error during file index ingest: {str(e)}")
        # Clean up corrupted physical file
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return jsonify({"error": f"Failed parsing document indexing: {str(e)}"}), 500


@app.route("/api/documents", methods=["GET"])
def get_documents():
    """Returns database overview of currently indexed documents."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, upload_time, chunk_count, file_size FROM documents ORDER BY upload_time DESC")
        rows = cursor.fetchall()
        conn.close()

        docs = [dict(row) for row in rows]
        return jsonify(docs), 200
    except Exception as e:
        logger.error(f"Database query failed for policy catalog list: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/document/<string:filename>", methods=["DELETE"])
def delete_document(filename):
    """Deletes document physical storage, SQLite registry, and ChromaDB vector entries."""
    try:
        # 1. Delete vector entries
        chroma_manager.delete_by_filename(filename)

        # 2. Delete file from storage
        filepath = os.path.join(app.config["PDF_FOLDER"], filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        # 3. Delete from SQLite document register
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE filename = ?", (filename,))
        conn.commit()
        conn.close()

        logger.info(f"Admin manually deleted document and cleared index for: {filename}")
        return jsonify({"message": f"Successfully cleared indexes and deleted: {filename}"}), 200
    except Exception as e:
        logger.error(f"Failed deleting policy: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# 3. FAQ CONFIGURATION & TRAIN ENDPOINTS
# ----------------------------------------------------------------------
@app.route("/api/faq", methods=["POST"])
def add_faq():
    """Adds a new FAQ and computes its embedding."""
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()

    if not question or not answer:
        return jsonify({"error": "Question and Answer values are required."}), 400

    try:
        model = VectorModel.get_model()
        embedding_vector = model.encode(question, convert_to_numpy=True)
        embedding_blob = pickle.dumps(embedding_vector)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO faq (question, answer, embedding)
            VALUES (?, ?, ?)
            """,
            (question, answer, embedding_blob)
        )
        conn.commit()
        conn.close()

        logger.info(f"FAQ successfully registered: '{question}'")
        return jsonify({"message": "FAQ added and vectorized successfully."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "An FAQ with that exact question already exists."}), 400
    except Exception as e:
        logger.error(f"Error adding FAQ entry: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/faqs", methods=["GET"])
def get_faqs():
    """Returns all FAQ questions and answers registered in the system."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, question, answer FROM faq ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        faqs = [dict(row) for row in rows]
        return jsonify(faqs), 200
    except Exception as e:
        logger.error(f"Database query failed for FAQ list: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/faq/<int:faq_id>", methods=["DELETE"])
def delete_faq(faq_id):
    """Deletes an FAQ entry from the database by ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM faq WHERE id = ?", (faq_id,))
        conn.commit()
        conn.close()

        logger.info(f"Deleted FAQ entry ID: {faq_id}")
        return jsonify({"message": f"Successfully deleted FAQ ID {faq_id}"}), 200
    except Exception as e:
        logger.error(f"Failed deleting FAQ entry: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# 4. ADMIN DIAGNOSTIC & BULK SYSTEM REBUILD
# ----------------------------------------------------------------------
@app.route("/api/rebuild", methods=["POST"])
def rebuild_database():
    """Performs manual deep index rebuild from saved policy PDFs."""
    try:
        # Clear Chroma collection
        chroma_manager.reset_collection()
        
        # Load indexing model
        model = VectorModel.get_model()

        # Re-parse every PDF file in permanent storage
        pdf_folder = app.config["PDF_FOLDER"]
        pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Reset current SQLite register stats (will recount chunks during rebuild)
        cursor.execute("DELETE FROM documents")
        conn.commit()

        total_chunks = 0
        for pdf_name in pdf_files:
            file_path = os.path.join(pdf_folder, pdf_name)
            file_size = os.path.getsize(file_path)
            
            chunks = extract_pdf_chunks(file_path)
            chunk_count = len(chunks)
            total_chunks += chunk_count

            if chunk_count > 0:
                texts = [c["text"] for c in chunks]
                ids = [c["id"] for c in chunks]
                metadatas = [c["metadata"] for c in chunks]
                embeddings = model.encode(texts, convert_to_numpy=True).tolist()

                chroma_manager.add_chunks(
                    ids=ids,
                    texts=texts,
                    metadatas=metadatas,
                    embeddings=embeddings
                )

            cursor.execute(
                """
                INSERT OR REPLACE INTO documents (filename, chunk_count, file_size)
                VALUES (?, ?, ?)
                """,
                (pdf_name, chunk_count, file_size)
            )

        conn.commit()
        conn.close()

        logger.info(f"System Rebuild complete! Rebuilt {len(pdf_files)} PDFs ({total_chunks} chunks)")
        return jsonify({
            "message": "Global vector index completely rebuilt successfully.",
            "processed_documents": len(pdf_files),
            "total_chunks": total_chunks
        }), 200

    except Exception as e:
        logger.error(f"System DB rebuild crash: {str(e)}")
        return jsonify({"error": f"Failed rebuild: {str(e)}"}), 500


# ----------------------------------------------------------------------
# 5. DATA SCIENCE & ANALYTICS REPORTING
# ----------------------------------------------------------------------
@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    """Calculates operational and performance reporting metrics for the dashboard."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Document summary counts
        cursor.execute("SELECT COUNT(*) as pdfs, SUM(chunk_count) as chunks FROM documents")
        doc_stats = cursor.fetchone()
        total_pdfs = doc_stats["pdfs"] or 0
        total_chunks = doc_stats["chunks"] or 0

        # 2. Total questions asked
        cursor.execute("SELECT COUNT(*) as queries, AVG(latency) as avg_lat FROM analytics")
        query_stats = cursor.fetchone()
        total_queries = query_stats["queries"] or 0
        avg_latency = round(query_stats["avg_lat"] or 0.0, 3)

        # 3. Hits categorized by internal subsystem tools
        cursor.execute("SELECT COUNT(*) as hits FROM analytics WHERE tool_used LIKE '%FAQ%'")
        faq_hits = cursor.fetchone()["hits"] or 0

        cursor.execute("SELECT COUNT(*) as hits FROM analytics WHERE tool_used LIKE '%RAG%'")
        rag_hits = cursor.fetchone()["hits"] or 0

        # 4. Fetch all logs for detailed pandas visualization construction on client
        cursor.execute("SELECT id, question, tool_used, confidence, latency, sources, timestamp FROM analytics ORDER BY id DESC")
        logs = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return jsonify({
            "total_pdfs": total_pdfs,
            "total_chunks": total_chunks,
            "total_queries": total_queries,
            "avg_latency": avg_latency,
            "faq_hits": faq_hits,
            "rag_hits": rag_hits,
            "chat_logs": logs
        }), 200

    except Exception as e:
        logger.error(f"Failed loading analytics data: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# SERVER EXECUTION ENTRYPOINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    # Run server locally on port 5000
    app.run(host="0.0.0.0", port=5000, debug=False)