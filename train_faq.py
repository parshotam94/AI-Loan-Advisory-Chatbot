import sqlite3
import numpy as np
import pickle
from typing import List, Tuple
from utils import get_db_connection, VectorModel, logger

# Pre-populated starter FAQs for our Loan Agent
SEED_FAQS: List[Tuple[str, str]] = [
    (
        "What is the maximum loan amount I can apply for?",
        "Our standard home loans go up to $5,000,000, while personal loans are capped at $100,000. Approval limits always depend on your verified income, credit profile, and existing debt commitments."
    ),
    (
        "How long does the loan approval process take?",
        "Personal loans are typically processed and approved within 24 to 48 hours. Home loans and commercial mortgages usually take between 10 to 15 business days, pending complete asset valuations and documentation."
    ),
    (
        "Can I pay off my loan early without any prepayment penalties?",
        "Yes, all variable-rate loans can be paid off early with zero prepayment penalties. However, fixed-rate loans may incur an early break fee if settled before the maturity date. Please consult your specific credit contract."
    ),
    (
        "What documents do I need to submit for a loan application?",
        "You will need: 1) Government-issued photo ID, 2) Your two most recent paystubs, 3) Past two years of W-2 tax forms or tax returns, and 4) Your last three months of personal bank statements."
    ),
    (
        "What is the difference between a fixed rate and a variable rate?",
        "A fixed-rate loan locks in your interest rate and monthly payment for a set term, protecting you from market hikes. A variable-rate loan fluctuates with market indices, meaning your payments can go up or down over time."
    ),
    (
        "What are your current standard interest rates?",
        "Our current starting rates are: Home Loans at 5.5% p.a. (variable) and 5.9% p.a. (fixed), Personal Loans at 8.9% p.a., and Auto Loans starting at 6.2% p.a. Final interest rates are determined upon individual credit assessment."
    )
]

def train_and_index_faqs():
    """Generates embeddings for seed FAQs and populates the SQLite database."""
    logger.info("Starting FAQ indexing process...")
    
    # Load embedding model
    try:
        model = VectorModel.get_model()
    except Exception as e:
        logger.error(f"Failed to load sentence-transformer model: {str(e)}")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    success_count = 0
    duplicate_count = 0

    for question, answer in SEED_FAQS:
        logger.info(f"Processing FAQ: '{question}'")
        
        # 1. Generate high-quality dense embedding vector
        try:
            embedding_vector = model.encode(question, convert_to_numpy=True)
            # Serialize the NumPy array to binary blob for SQLite storage
            embedding_blob = pickle.dumps(embedding_vector)
        except Exception as e:
            logger.error(f"Failed to generate embedding for FAQ '{question}': {str(e)}")
            continue

        # 2. Insert into SQLite FAQ storage
        try:
            cursor.execute(
                """
                INSERT INTO faq (question, answer, embedding)
                VALUES (?, ?, ?)
                """,
                (question, answer, embedding_blob)
            )
            success_count += 1
        except sqlite3.IntegrityError:
            # Handle duplicates gracefully by updating the answer and embedding
            cursor.execute(
                """
                UPDATE faq 
                SET answer = ?, embedding = ?
                WHERE question = ?
                """,
                (answer, embedding_blob, question)
            )
            duplicate_count += 1

    conn.commit()
    conn.close()

    logger.info("FAQ Indexing complete!")
    logger.info(f"Summary: {success_count} new FAQs added, {duplicate_count} existing FAQs updated.")

if __name__ == "__main__":
    train_and_index_faqs()