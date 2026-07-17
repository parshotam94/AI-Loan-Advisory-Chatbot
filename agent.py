import os
import re
import time
import pickle
import numpy as np
from typing import Dict, Any, List, Optional
from groq import Groq
from dotenv import load_dotenv

from utils import get_db_connection, VectorModel, ChromaDBManager, logger

# Load Environment Variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

class LoanAgent:
    """
    Intelligent Loan Advisory Agent. Decides on appropriate tool routings:
    1. EMI calculation queries -> Programmatic EMI tool
    2. Eligibility assessment -> Programmatic Eligibility evaluation
    3. FAQ match with high similarity -> SQLite FAQ Retrieval
    4. Document comparative query -> Policy Comparison tool
    5. General policy questions -> Dense RAG Search (ChromaDB + Groq)
    """

    def __init__(self):
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY is not defined. LLM steps will fail.")
        self.llm_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        self.chroma_manager = ChromaDBManager()
        self.embedding_model = VectorModel.get_model()

    # ----------------------------------------------------------------------
    # 1. SEMANTIC FAQ TOOL
    # ----------------------------------------------------------------------
    def check_faq_similarity(self, query: str, threshold: float = 0.72) -> Optional[Dict[str, Any]]:
        """Compares search terms semantically against precomputed FAQ database embeddings."""
        try:
            query_vector = self.embedding_model.encode(query, convert_to_numpy=True)
        except Exception as e:
            logger.error(f"FAQ vectorizer step failed: {str(e)}")
            return None

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, question, answer, embedding FROM faq")
        rows = cursor.fetchall()
        conn.close()

        best_score = -1.0
        best_match = None

        for row in rows:
            try:
                faq_vector = pickle.loads(row["embedding"])
                # Compute cosine similarity
                dot_product = np.dot(query_vector, faq_vector)
                norm_q = np.linalg.norm(query_vector)
                norm_f = np.linalg.norm(faq_vector)
                
                if norm_q > 0 and norm_f > 0:
                    similarity = float(dot_product / (norm_q * norm_f))
                    if similarity > best_score:
                        best_score = similarity
                        best_match = {
                            "answer": row["answer"],
                            "question": row["question"]
                        }
            except Exception as e:
                logger.error(f"Error parsing FAQ embedding entry {row['id']}: {str(e)}")
                continue

        if best_match and best_score >= threshold:
            logger.info(f"FAQ match found with score {best_score:.4f} for query: '{query}'")
            return {
                "answer": f"**Matched FAQ:** *\"{best_match['question']}\"*\n\n{best_match['answer']}",
                "confidence": round(best_score, 2),
                "tool": "FAQ Tool",
                "sources": "Database FAQ System"
            }
        
        logger.info(f"No database FAQ match met the threshold. Top score was: {best_score:.4f}")
        return None

    # ----------------------------------------------------------------------
    # 2. EMI CALCULATOR TOOL (PARSING WITHOUT LLM CALLS)
    # ----------------------------------------------------------------------
    def try_parse_emi(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Regex patterns to detect EMI inquiries and parse values directly:
        - Principal (loan amount): $ or numerical string
        - Rate: percentage
        - Term: years or months
        """
        # Look for indicators of calculation interest
        lower_q = query.lower()
        if not any(term in lower_q for term in ["emi", "calculate", "monthly payment", "repayment", "interest rate"]):
            return None

        # Robust extraction regexes
        # Extract amount (e.g. 500k, 500,000, 50k, 50000)
        amount_match = re.search(r'(?:[\$\s]|^)(\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?:\s*(k|kilo|million|m))?\s*(?:dollars|loan|amount)?', lower_q)
        # Extract percentage rate (e.g. 5.5%, 6.5 percent)
        rate_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent)', lower_q)
        # Extract terms (e.g. 30 years, 5 year, 15yr, 360 months)
        term_match = re.search(r'(\d+)\s*(?:year|yr|month|mo|annual)', lower_q)

        if not (amount_match and rate_match and term_match):
            return None

        try:
            # Parse Amount
            amt_str = amount_match.group(1).replace(",", "")
            amount = float(amt_str)
            multiplier = amount_match.group(2)
            if multiplier in ["k", "kilo"]:
                amount *= 1000
            elif multiplier in ["m", "million"]:
                amount *= 1000000

            # Parse Rate
            rate = float(rate_match.group(1))

            # Parse Duration
            term_val = int(term_match.group(1))
            term_str = term_match.group(0)
            is_months = "month" in term_str or "mo" in term_str
            months = term_val if is_months else term_val * 12

            if months <= 0 or rate < 0:
                return None

            # --- EMI Guardrails against math overflow or unrealistic values ---
            if amount > 1_000_000_000 or rate > 100 or months > 600:  # Cap at $1B loan, 100% interest, 50 years
                logger.warning(f"EMI parameters exceed reasonable system thresholds: amt={amount}, rate={rate}, months={months}")
                return None

            # Calculate EMI
            monthly_rate = (rate / 100) / 12
            if monthly_rate == 0:
                emi = amount / months
            else:
                emi = (amount * monthly_rate * ((1 + monthly_rate) ** months)) / (((1 + monthly_rate) ** months) - 1)

            total_payment = emi * months
            total_interest = total_payment - amount

            answer = (
                f"### EMI Calculation Breakdown\n"
                f"Your estimated monthly repayment structure is detailed below:\n\n"
                f"*   **Principal Amount:** ${amount:,.2f}\n"
                f"*   **Annual Interest Rate:** {rate}%\n"
                f"*   **Repayment Duration:** {term_val} {'months' if is_months else 'years'} ({months} installments)\n"
                f"*   **Monthly Installment (EMI):** **${emi:,.2f}** / month\n"
                f"*   **Total Cumulative Interest:** ${total_interest:,.2f}\n"
                f"*   **Total Out-of-pocket Cost:** ${total_payment:,.2f}\n"
            )
            return {
                "answer": answer,
                "confidence": 1.0,
                "tool": "EMI Calculator",
                "sources": "EMI Algorithm"
            }
        except Exception as e:
            logger.error(f"Error occurred during EMI parsing: {str(e)}")
            return None

    # ----------------------------------------------------------------------
    # 3. ELIGIBILITY EVALUATOR TOOL
    # ----------------------------------------------------------------------
    def try_parse_eligibility(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Parses specific criteria for eligibility or checks standard conditions.
        Format expected: Age, Income, Employment, Credit Score, Loan Amount.
        If structured values aren't in query, we output standard evaluation templates.
        """
        lower_q = query.lower()
        if not any(term in lower_q for term in ["eligible", "eligibility", "qualify", "can i get", "credit score"]):
            return None

        # Extract numerical parameters
        credit_match = re.search(r'(?:credit|score|fico)\s*(?:of|is|equals)?\s*(\d{3})', lower_q)
        income_match = re.search(r'(?:income|salary|earning|earn)\s*(?:of|is)?\s*[\$]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?:\s*(k))?', lower_q)
        age_match = re.search(r'(?:age|old|am)\s*(?:is|of)?\s*(\d{2})', lower_q)
        loan_req_match = re.search(r'(?:borrow|loan|amount|request)\s*(?:of|for)?\s*[\$]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?:\s*(k))?', lower_q)

        # Fallback to offering assistance if parameters are entirely missing
        if not (credit_match or income_match or age_match):
            return {
                "answer": (
                    "### Loan Eligibility Checker\n"
                    "To determine if you qualify for our loan options, please provide your structural details:\n"
                    "*   **Age** (e.g., *'I am 32 years old'*\n"
                    "*   **Monthly or Annual Income** (e.g., *'monthly income of $6,500'*\n"
                    "*   **Credit Score** (e.g., *'credit score of 720'*)\n"
                    "*   **Target Loan Amount** (e.g., *'want to borrow $50,000'*)\n\n"
                    "**Alternatively, write them in a sentence like:** *'Am I eligible for a $40k loan if I have a credit score of 680, age of 29, and income of 5000 monthly?'*"
                ),
                "confidence": 0.90,
                "tool": "Eligibility Engine",
                "sources": "Rule Database"
            }

        # Extracted metrics (with standard defaults if missing)
        credit_score = int(credit_match.group(1)) if credit_match else 650
        age = int(age_match.group(1)) if age_match else 25
        
        income = 4000.0
        if income_match:
            val = float(income_match.group(1).replace(",", ""))
            is_k = income_match.group(2) is not None
            income = val * 1000 if is_k else val
            # Assume annual if number looks like a full year salary
            if income > 20000:
                income = income / 12

        loan_req = 30000.0
        if loan_req_match:
            val = float(loan_req_match.group(1).replace(",", ""))
            is_k = loan_req_match.group(2) is not None
            loan_req = val * 1000 if is_k else val

        # --- Eligibility Guardrails against negative/overflow inputs ---
        credit_score = max(300, min(850, credit_score))  # FICO scores fall strictly between 300 and 850
        age = max(0, min(120, age))
        income = max(1.0, min(1_000_000_000.0, income))  # Clamp income bounds to avoid zero-division and overflows
        loan_req = max(0.0, min(1_000_000_000.0, loan_req))

        # Evaluate logic metrics
        reasons = []
        status = "Eligible"

        # Age Check (Standard: 18 - 70)
        if age < 18:
            status = "Not Eligible"
            reasons.append("Applicant must be 18 years or older.")
        elif age > 70:
            status = "Partially Eligible"
            reasons.append("Applicant age is close to pension caps. Requires a joint cosigner.")

        # Credit Score Checks
        if credit_score < 580:
            status = "Not Eligible"
            reasons.append(f"Credit score ({credit_score}) is below our 580 threshold for unsecured products.")
        elif 580 <= credit_score < 660:
            if status != "Not Eligible":
                status = "Partially Eligible"
            reasons.append(f"Credit score ({credit_score}) falls into the subprime tier. Higher rates apply.")
        else:
            reasons.append(f"Credit score ({credit_score}) meets premium criteria standards.")

        # Debt-to-Income (DTI) approximation
        # Standard: Monthly payment shouldn't exceed 40% of income
        est_monthly_payment = (loan_req * 0.08) / 12  # Estimate at 8% p.a.
        dti = est_monthly_payment / income
        if dti > 0.45:
            status = "Not Eligible"
            reasons.append(f"Estimated payment-to-income ratio ({dti*100:.1f}%) exceeds our risk tolerance of 45%.")
        elif 0.35 < dti <= 0.45:
            if status != "Not Eligible":
                status = "Partially Eligible"
            reasons.append(f"Payment-to-income ratio ({dti*100:.1f}%) is elevated. Requires strict guarantor vetting.")
        else:
            reasons.append(f"Debt-to-income metric ({dti*100:.1f}%) is in optimal range.")

        # Build output structure
        color_map = {"Eligible": "🟢 **FULLY ELIGIBLE**", "Partially Eligible": "🟡 **CONDITIONALLY ELIGIBLE**", "Not Eligible": "🔴 **NOT ELIGIBLE**"}
        verdict = color_map.get(status, "Unknown")

        answer = (
            f"### Eligibility Vetting Verdict: {verdict}\n\n"
            f"**Evaluated Parameters:**\n"
            f"*   Age: {age} yrs\n"
            f"*   Reported Monthly Income: ${income:,.2f}/mo\n"
            f"*   Credit Score: {credit_score}\n"
            f"*   Requested Loan: ${loan_req:,.2f}\n\n"
            f"**Risk Analysis Notes:**\n"
            + "\n".join([f"- {r}" for r in reasons])
        )

        return {
            "answer": answer,
            "confidence": 1.0,
            "tool": "Eligibility Engine",
            "sources": "Vetting Rule Engine v4.1"
        }

    # ----------------------------------------------------------------------
    # 4. POLICY COMPARISON AND RAG RECONSTRUCTION
    # ----------------------------------------------------------------------
    def run_comparative_search(self, query: str) -> Optional[Dict[str, Any]]:
        """Handles comparative inquiries by pulling multiple dense vectors and compiling a table."""
        lower_q = query.lower()
        if not any(word in lower_q for word in ["compare", "difference between", "versus", "vs", "differences"]):
            return None

        # Execute a dense search to identify context files
        try:
            query_vector = self.embedding_model.encode(query, convert_to_numpy=True).tolist()
            matches = self.chroma_manager.search(query_vector, top_k=7)
        except Exception as e:
            logger.error(f"Failed RAG extraction for comparison: {str(e)}")
            return None

        if not matches:
            return None

        # Build context prompt
        context_blocks = []
        unique_sources = set()
        for idx, match in enumerate(matches):
            src = match["metadata"].get("source", "Unknown Document")
            unique_sources.add(src)
            context_blocks.append(
                f"[Document Source: {src} - Chunk {idx+1}]\n"
                f"{match['text']}\n"
            )

        context_string = "\n\n".join(context_blocks)
        
        # We need at least two documents to meaningfully compare, otherwise we route to basic RAG
        if len(unique_sources) < 2:
            return None

        system_instruction = (
            "You are an expert financial policy analysis engine. "
            "The user wishes to compare loan rules, policies, processing fees, or interest rates "
            "across multiple documents. Use the provided context to generate a structured markdown "
            "comparison table contrasting the differences. If specific items are missing in some documents, "
            "mark them as 'Not specified in document'."
        )

        prompt = (
            f"Context Documents:\n"
            f"-----------------------\n"
            f"{context_string}\n\n"
            f"User Question: {query}\n\n"
            f"Please output a comparison table followed by a 2-3 sentence summary."
        )

        if not self.llm_client:
            return {
                "answer": "Groq LLM Client is not initialized. Please configure GROQ_API_KEY.",
                "confidence": 0.5,
                "tool": "Comparison Tool",
                "sources": ", ".join(unique_sources)
            }

        try:
            chat_completion = self.llm_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                model=GROQ_MODEL,
                temperature=0.2
            )
            ans = chat_completion.choices[0].message.content
            return {
                "answer": ans,
                "confidence": 0.95,
                "tool": "Comparison Tool",
                "sources": ", ".join(unique_sources)
            }
        except Exception as e:
            logger.error(f"Groq API call during comparison failed: {str(e)}")
            return None

    # ----------------------------------------------------------------------
    # 5. CORE DENSE RAG SEARCH TOOL
    # ----------------------------------------------------------------------
    def run_rag_search(self, query: str) -> Dict[str, Any]:
        """Runs normal RAG pipeline over loaded policies."""
        try:
            query_vector = self.embedding_model.encode(query, convert_to_numpy=True).tolist()
            matches = self.chroma_manager.search(query_vector, top_k=5)
        except Exception as e:
            logger.error(f"Error executing dense query lookup: {str(e)}")
            return {
                "answer": "An error occurred during vector retrieval. Please verify backend index configuration.",
                "confidence": 0.0,
                "tool": "RAG Tool",
                "sources": "System Error"
            }

        if not matches:
            return {
                "answer": (
                    "I searched our loan policies but couldn't find any relevant reference chunks.\n\n"
                    "**Tip:** Make sure you have uploaded policy PDFs in the admin panel and run a database rebuild."
                ),
                "confidence": 0.0,
                "tool": "RAG Tool",
                "sources": "None"
            }

        # Format retrieved blocks
        context_blocks = []
        citations = []
        for idx, match in enumerate(matches):
            src = match["metadata"].get("source", "Unknown")
            pg = match["metadata"].get("page", "?")
            citations.append(f"{src} (Page {pg})")
            context_blocks.append(
                f"[Source Document: {src} - Page {pg}]\n"
                f"{match['text']}"
            )

        context_string = "\n\n".join(context_blocks)
        unique_citations = sorted(list(set(citations)))

        system_instruction = (
            "You are a helpful, expert Loan Advisor. Use the following snippets of loan policy "
            "documents to answer the user's question accurately. "
            "If the document context does not contain enough information to answer, state clearly that "
            "the provided policy documents do not specify, but answer as much as possible with the context."
        )

        prompt = (
            f"Retrieved Policy Context:\n"
            f"-----------------------\n"
            f"{context_string}\n\n"
            f"User Question: {query}\n\n"
            f"Provide a clear, helpful, and concise response."
        )

        if not self.llm_client:
            return {
                "answer": (
                    f"### RAG Mode (No LLM Active)\n"
                    f"Here is the most relevant raw document text retrieved from database files:\n\n"
                    f"\"{matches[0]['text']}\""
                ),
                "confidence": float(matches[0]["score"]),
                "tool": "RAG Tool (Vector only)",
                "sources": ", ".join(unique_citations)
            }

        try:
            chat_completion = self.llm_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                model=GROQ_MODEL,
                temperature=0.2
            )
            ans = chat_completion.choices[0].message.content
            # Compute average score of top matches for reference confidence
            avg_score = float(np.mean([m["score"] for m in matches]))
            
            return {
                "answer": ans,
                "confidence": round(avg_score, 2),
                "tool": "RAG Tool",
                "sources": ", ".join(unique_citations)
            }
        except Exception as e:
            logger.error(f"Groq generation error: {str(e)}")
            return {
                "answer": f"Error communicating with the language model API: {str(e)}",
                "confidence": 0.5,
                "tool": "RAG Tool",
                "sources": ", ".join(unique_citations)
            }

    # ----------------------------------------------------------------------
    # ORCHESTRATOR ROUTER MAIN ENTRYPOINT
    # ----------------------------------------------------------------------
    def handle_query(self, query: str) -> Dict[str, Any]:
        """Runs routing logic sequentially across all engines."""
        logger.info(f"Incoming user transaction query: '{query}'")
        start_time = time.time()

        # --- Orchestrator Input Guardrails ---
        if not query or not isinstance(query, str) or not query.strip():
            logger.warning("Empty or invalid query type rejected by orchestrator guardrails.")
            return {
                "answer": "The query submitted was empty or invalid. Please try asking a specific loan-related question.",
                "confidence": 0.0,
                "tool": "Validation Guardrail",
                "sources": "System Guardrail",
                "latency": 0.0
            }

        # Truncate queries exceeding reasonable length limits (e.g., to prevent prompt-injection bulk or excessive load)
        if len(query) > 1000:
            logger.info(f"Query length of {len(query)} exceeds maximum. Truncating to 1000 characters.")
            query = query[:1000].strip()

        # Step 1. Match programmatically against EMI formula patterns
        emi_match = self.try_parse_emi(query)
        if emi_match:
            emi_match["latency"] = round(time.time() - start_time, 3)
            return emi_match

        # Step 2. Match programmatically against eligibility rules
        eligibility_match = self.try_parse_eligibility(query)
        if eligibility_match:
            eligibility_match["latency"] = round(time.time() - start_time, 3)
            return eligibility_match

        # Step 3. Compare semantically against our local FAQ cache
        faq_match = self.check_faq_similarity(query)
        if faq_match:
            faq_match["latency"] = round(time.time() - start_time, 3)
            return faq_match

        # Step 4. Run contrast comparison check if comparing multiple policies
        comparison_match = self.run_comparative_search(query)
        if comparison_match:
            comparison_match["latency"] = round(time.time() - start_time, 3)
            return comparison_match

        # Step 5. Fallback: Standard high-density RAG Search
        rag_match = self.run_rag_search(query)
        rag_match["latency"] = round(time.time() - start_time, 3)
        return rag_match