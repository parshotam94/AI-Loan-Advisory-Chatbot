import os
import sqlite3
import re
import numpy as np
from pypdf import PdfReader
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LoanAdvisoryLogger")

DB_PATH = os.getenv("SQLITE_DB_PATH", "data/loans.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Analytics Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT,
        tool_used TEXT,
        confidence REAL,
        latency REAL,
        sources TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Documents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE,
        chunk_count INTEGER,
        file_size INTEGER,
        upload_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Dynamic FAQ Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT UNIQUE,
        answer TEXT,
        embedding BLOB
    )
    """)
    conn.commit()
    conn.close()

def extract_pdf_chunks(pdf_path, chunk_size=500, overlap=100):
    """Parses PDF and splits content into overlapping chunks."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
            
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    
    chunks = []
    filename = os.path.basename(pdf_path)
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk_text = " ".join(chunk_words)
        if chunk_text:
            chunk_id = f"{filename}_chunk_{len(chunks)}"
            chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "metadata": {"source": filename}
            })
    return chunks

# --- Lightweight Mathematical Cosine Similarity Vectorizer ---
class SimpleVectorizer:
    """A lightweight bag-of-words vectorizer that requires zero deep-learning libraries."""
    @staticmethod
    def tokenize(text):
        return re.findall(r'\w+', text.lower())

    @classmethod
    def get_cosine_similarity(cls, text1, text2):
        tokens1 = cls.tokenize(text1)
        tokens2 = cls.tokenize(text2)
        vocab = list(set(tokens1 + tokens2))
        if not vocab:
            return 0.0
        
        v1 = [tokens1.count(word) for word in vocab]
        v2 = [tokens2.count(word) for word in vocab]
        
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = sum(a * a for a in v1) ** 0.5
        norm_b = sum(b * b for b in v2) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))