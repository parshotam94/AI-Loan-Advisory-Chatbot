import pickle
from utils import get_db_connection, SimpleVectorizer
import re

class LoanAgent:
    def check_faq_match(self, query):
        """Looks for dynamic FAQ semantic matches using high-performance simple vector calculations."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer FROM faq")
        rows = cursor.fetchall()
        conn.close()

        best_match = None
        highest_score = 0.0

        for row in rows:
            similarity = SimpleVectorizer.get_cosine_similarity(query, row["question"])
            if similarity > highest_score:
                highest_score = similarity
                best_match = row

        # Set confidence threshold to 0.40
        if highest_score >= 0.40 and best_match:
            return True, {
                "answer": best_match["answer"],
                "confidence": round(highest_score, 2),
                "tool": "FAQ Search Tool",
                "sources": "Local FAQ Database"
            }
        return False, None

    def calculate_emi(self, query):
        """
        Parses numerical input from user query: Principal (P), Rate (R), and Tenor (N).
        Example user string: "EMI for 1000000 at 8.5% for 15 years"
        """
        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", query)
        # Defaults
        P, R, N = 500000, 10.5, 5 # default 5 Lakhs, 10.5% interest, 5 years
        
        if len(numbers) >= 3:
            P = float(numbers[0])
            R = float(numbers[1])
            N = float(numbers[2])
            
        # Convert years to months if user inputs a small integer tenor
        if N < 40:  
            N_months = N * 12
        else:
            N_months = N

        r_monthly = (R / 12) / 100
        
        # EMI calculation formula
        try:
            emi = (P * r_monthly * ((1 + r_monthly) ** N_months)) / (((1 + r_monthly) ** N_months) - 1)
            emi = round(emi, 2)
            total_payable = round(emi * N_months, 2)
            total_interest = round(total_payable - P, 2)
            
            ans = f"For a Principal amount of **${P:,.2f}** at **{R}%** interest rate for **{N} years**:\n\n" \
                  f"* **Monthly EMI:** ${emi:,.2f}\n" \
                  f"* **Total Interest Payable:** ${total_interest:,.2f}\n" \
                  f"* **Total Amount Payable:** ${total_payable:,.2f}"
            return {
                "answer": ans,
                "confidence": 1.0,
                "tool": "EMI Calc Tool",
                "sources": "Mathematical Rule Engine"
            }
        except ZeroDivisionError:
            return {
                "answer": "Failed to calculate EMI. Please ensure the interest rate and tenure are greater than 0.",
                "confidence": 0.0,
                "tool": "EMI Calc Tool",
                "sources": "None"
            }

    def check_eligibility(self, query):
        """
        Parses Credit Scoring attributes: Age, Income, and Credit Score.
        Example query: "Eligible for loan? age 30, income 85000, credit 750"
        """
        numbers = re.findall(r"\d+", query)
        age, income, credit = 25, 30000, 650 # Defaults
        
        if len(numbers) >= 3:
            age = int(numbers[0])
            income = float(numbers[1])
            credit = int(numbers[2])

        reasons = []
        eligible = True

        if age < 18 or age > 65:
            eligible = False
            reasons.append("Age must be between 18 and 65 years.")
        if income < 25000:
            eligible = False
            reasons.append("Minimum monthly income threshold is $25,000.")
        if credit < 600:
            eligible = False
            reasons.append("Credit score must be at least 600.")

        if eligible:
            ans = f"✅ **Eligible!** Your financial metrics qualify for the credit guidelines.\n\n" \
                  f"Attributes entered: Age: **{age}**, Monthly Income: **${income:,.2f}**, Credit Score: **{credit}**."
        else:
            reasons_str = "\n".join([f"- {r}" for r in reasons])
            ans = f"❌ **Currently Ineligible** due to the following requirements:\n{reasons_str}\n\n" \
                  f"Attributes entered: Age: **{age}**, Monthly Income: **${income:,.2f}**, Credit Score: **{credit}**."

        return {
            "answer": ans,
            "confidence": 1.0,
            "tool": "Eligibility Checker Engine",
            "sources": "Credit Evaluation Rules"
        }