import os
import time
import sqlite3
import pickle
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from utils import get_db_connection, init_db, extract_pdf_chunks, logger
from workflow import execute_agent_pipeline

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "data/uploads"
app.config["PDF_FOLDER"] = "data/pdfs"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

for folder in [app.config["UPLOAD_FOLDER"], app.config["PDF_FOLDER"]]:
    os.makedirs(folder, exist_ok=True)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "Flask running"}), 200

@app.route("/api/chat", methods=["POST"])
def chat():
    start_time = time.time()
    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Empty search query string provided."}), 400

    try:
        response = execute_agent_pipeline(query)
        latency = round(time.time() - start_time, 3)
        response["latency"] = latency

        # Store metrics to SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO analytics (question, answer, tool_used, confidence, latency, sources)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (query, response["answer"], response["tool"], response["confidence"], response["latency"], response["sources"])
        )
        conn.commit()
        conn.close()

        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error handling chat: {str(e)}")
        return jsonify({
            "answer": "A backend framework error occurred while processing your query.",
            "confidence": 0.0,
            "tool": "Error Handler",
            "sources": "None",
            "latency": round(time.time() - start_time, 3)
        }), 500

@app.route("/api/upload", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file field found"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    dest_path = os.path.join(app.config["PDF_FOLDER"], filename)
    file.save(dest_path)
    file_size = os.path.getsize(dest_path)

    try:
        chunks = extract_pdf_chunks(dest_path)
        chunk_count = len(chunks)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO documents (filename, chunk_count, file_size) VALUES (?, ?, ?)",
            (filename, chunk_count, file_size)
        )
        conn.commit()
        conn.close()

        return jsonify({
            "message": f"Successfully parsed and indexed {filename}!",
            "filename": filename,
            "chunks": chunk_count,
            "size_bytes": file_size
        }), 200
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents", methods=["GET"])
def get_documents():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, upload_time, chunk_count, file_size FROM documents ORDER BY upload_time DESC")
        docs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(docs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/document/<string:filename>", methods=["DELETE"])
def delete_document(filename):
    try:
        filepath = os.path.join(app.config["PDF_FOLDER"], filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE filename = ?", (filename,))
        conn.commit()
        conn.close()
        return jsonify({"message": f"Successfully deleted: {filename}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/faq", methods=["POST"])
def add_faq():
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()

    if not question or not answer:
        return jsonify({"error": "Question and Answer values are required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO faq (question, answer) VALUES (?, ?)", (question, answer))
        conn.commit()
        conn.close()
        return jsonify({"message": "FAQ added successfully."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "An FAQ with that exact question already exists."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/faqs", methods=["GET"])
def get_faqs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, question, answer FROM faq ORDER BY id DESC")
        faqs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(faqs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/faq/<int:faq_id>", methods=["DELETE"])
def delete_faq(faq_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM faq WHERE id = ?", (faq_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Successfully deleted FAQ"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as pdfs, COALESCE(SUM(chunk_count),0) as chunks FROM documents")
        doc_stats = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as queries, COALESCE(AVG(latency),0.0) as avg_lat FROM analytics")
        query_stats = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) as hits FROM analytics WHERE tool_used LIKE '%FAQ%'")
        faq_hits = cursor.fetchone()["hits"] or 0

        cursor.execute("SELECT COUNT(*) as hits FROM analytics WHERE tool_used LIKE '%RAG%'")
        rag_hits = cursor.fetchone()["hits"] or 0

        cursor.execute("SELECT id, question, tool_used, confidence, latency, sources, timestamp FROM analytics ORDER BY id DESC")
        logs = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return jsonify({
            "total_pdfs": doc_stats["pdfs"] or 0,
            "total_chunks": doc_stats["chunks"] or 0,
            "total_queries": query_stats["queries"] or 0,
            "avg_latency": round(query_stats["avg_lat"], 3),
            "faq_hits": faq_hits,
            "rag_hits": rag_hits,
            "chat_logs": logs
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)