import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple
import fitz  # PyMuPDF
import sentence_transformers
import chromadb
from chromadb.config import Settings

# Ensure system directories exist
for folder in ["data/pdfs", "data/chroma_db", "data/uploads", "logs"]:
    os.makedirs(folder, exist_ok=True)

# Set up global logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LoanAdvisoryAgent")

# Configuration Constants
DB_PATH = "data/loans.db"
CHROMA_DIR = "data/chroma_db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# ----------------------------------------------------------------------
# DATABASE SETUP & UTILITIES
# ----------------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database with dict-like row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes standard metadata tables inside SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Documents Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            chunk_count INTEGER,
            file_size INTEGER
        )
    """)
    
    # 2. FAQ Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT UNIQUE,
            answer TEXT,
            embedding BLOB
        )
    """)
    
    # 3. Analytics / Chat Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT,
            tool_used TEXT,
            confidence REAL,
            latency REAL,
            sources TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("SQLite database tables initialized successfully.")

# Run database setup immediately on load
init_db()

# ----------------------------------------------------------------------
# EMBEDDING & VECTOR DATABASE MANAGER
# ----------------------------------------------------------------------

class VectorModel:
    """Loads and caches SentenceTransformer model for fast, local embedding generation."""
    _model = None

    @classmethod
    def get_model(cls) -> sentence_transformers.SentenceTransformer:
        if cls._model is None:
            logger.info(f"Loading local SentenceTransformer model: {EMBEDDING_MODEL_NAME}...")
            cls._model = sentence_transformers.SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.info("SentenceTransformer model loaded successfully.")
        return cls._model

class ChromaDBManager:
    """Interface to communicate with the local vector database."""
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DIR)
        self.collection_name = "loan_policies"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, ids: List[str], texts: List[str], metadatas: List[Dict[str, Any]], embeddings: List[List[float]]):
        """Inserts generated chunks, metadata, and embeddings into ChromaDB."""
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings
        )
        logger.info(f"Successfully added {len(ids)} document vectors to ChromaDB.")

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs a vector search returning list of matching documents with scores."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        parsed_results = []
        if not results or not results["documents"] or len(results["documents"][0]) == 0:
            return parsed_results

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]
        ids = results["ids"][0]

        for i in range(len(docs)):
            # Convert cosine distance to a similarity score (approximate)
            similarity_score = round(1 - distances[i], 4)
            parsed_results.append({
                "id": ids[i],
                "text": docs[i],
                "metadata": metas[i],
                "score": similarity_score
            })
        return parsed_results

    def delete_by_filename(self, filename: str):
        """Deletes all vector items associated with a given filename."""
        self.collection.delete(where={"source": filename})
        logger.info(f"Deleted vector chunks associated with source: {filename}")

    def reset_collection(self):
        """Completely drops and recreates the policy collection."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("ChromaDB policy collection has been reset.")

# ----------------------------------------------------------------------
# TEXT EXTRACTION & CHUNKING UTILITIES
# ----------------------------------------------------------------------

class RecursiveTextSplitter:
    """Custom character splitter mimicking LangChain's chunk structure."""
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            # Try to break at a space, punctuation, or newline rather than cutting words in half
            if end < text_len:
                last_space = text.rfind(" ", start, end)
                last_newline = text.rfind("\n", start, end)
                boundary = max(last_space, last_newline)
                if boundary > start:
                    end = boundary + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            if start >= text_len or end == text_len:
                break
        return chunks

def extract_pdf_chunks(file_path: str) -> List[Dict[str, Any]]:
    """Reads a PDF using PyMuPDF and returns structured chunks with metadata."""
    logger.info(f"Parsing PDF document: {file_path}")
    doc = fitz.open(file_path)
    filename = os.path.basename(file_path)
    splitter = RecursiveTextSplitter(chunk_size=1000, chunk_overlap=200)
    
    all_chunks = []
    chunk_index = 0
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        if not page_text.strip():
            continue
            
        page_chunks = splitter.split_text(page_text)
        for chunk in page_chunks:
            all_chunks.append({
                "id": f"{filename}_chunk_{chunk_index}",
                "text": chunk,
                "metadata": {
                    "source": filename,
                    "page": page_num + 1,
                    "timestamp": datetime.now().isoformat()
                }
            })
            chunk_index += 1
            
    doc.close()
    logger.info(f"Extracted {len(all_chunks)} total chunks from {filename}.")
    return all_chunks