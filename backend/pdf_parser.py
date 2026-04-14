"""
pdf_parser.py - Parse bank statements (PDF/CSV) using pdfplumber
Supports HDFC, SBI, ICICI, Kotak formats
"""

import pandas as pd
import pdfplumber
import re
import uuid
from typing import List, Dict, Tuple


class StatementParser:
    """Parse UPI transaction statements from bank PDFs/CSVs"""

    BANK_PATTERNS = {
        "HDFC": {
            "date_col": "Date",
            "amount_col": "Amount",
            "type_col": "Type",
            "narration_col": "Narration",
            "date_format": "%d/%m/%y",
        },
        "SBI": {
            "date_col": "Txn Date",
            "amount_col": "Amount",
            "type_col": "Dr/Cr",
            "narration_col": "Description",
            "date_format": "%d %b %Y",
        },
        "ICICI": {
            "date_col": "Transaction Date",
            "amount_col": "Amount (INR)",
            "type_col": "CR/DR",
            "narration_col": "Transaction Remarks",
            "date_format": "%d/%m/%Y",
        },
        "KOTAK": {
            "date_col": "Date",
            "amount_col": "Amount (INR)",
            "type_col": "Cr/Dr",
            "narration_col": "Description",
            "date_format": "%d-%m-%Y",
        },
    }

    VPA_REGEX = r"[a-zA-Z0-9._-]+@[a-zA-Z0-9]+"

    KNOWN_MERCHANTS = {
        "zomato@": "Zomato",
        "swiggy@": "Swiggy",
        "uber@": "Uber",
        "ola@": "Ola",
        "amazon@": "Amazon",
        "flipkart@": "Flipkart",
        "paytm@": "Paytm",
        "phonepe@": "PhonePe",
        "blinkit@": "Blinkit",
        "dunzo@": "Dunzo",
    }

    MERCHANT_CATEGORIES = {
        "Zomato": "food",
        "Swiggy": "food",
        "Blinkit": "food",
        "Uber": "transport",
        "Ola": "transport",
        "Rapido": "transport",
        "Amazon": "shopping",
        "Flipkart": "shopping",
        "Myntra": "shopping",
        "Airtel": "utilities",
        "Jio": "utilities",
    }

    def detect_bank_format(self, df: pd.DataFrame) -> str:
        """Auto-detect bank format from CSV column names"""
        columns_lower = [col.lower() for col in df.columns]

        for bank, pattern in self.BANK_PATTERNS.items():
            if pattern["date_col"].lower() in columns_lower:
                return bank

        return "GENERIC"

    def parse_pdf(self, pdf_path: str, bank_format: str = None) -> Tuple[str, List[Dict]]:
        """
        Parse PDF statement and extract transactions
        Returns: (profile_id, transactions_list)
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract all tables
                tables = []
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)

            if not tables:
                raise ValueError("No tables found in PDF")

            # Convert first table to DataFrame
            df = pd.DataFrame(tables[0][1:], columns=tables[0][0])

            # Parse as if CSV
            return self.parse_csv_df(df, bank_format)

        except Exception as e:
            print(f"PDF parsing error: {e}")
            raise

    def parse_csv(self, csv_path: str, bank_format: str = None) -> Tuple[str, List[Dict]]:
        """
        Parse CSV statement and extract transactions
        Returns: (profile_id, transactions_list)
        """
        df = pd.read_csv(csv_path)
        return self.parse_csv_df(df, bank_format)

    def parse_csv_df(self, df: pd.DataFrame, bank_format: str = None) -> Tuple[str, List[Dict]]:
        """
        Parse DataFrame and extract transactions
        """
        if bank_format is None:
            bank_format = self.detect_bank_format(df)

        print(f"Detected bank format: {bank_format}")

        if bank_format not in self.BANK_PATTERNS:
            raise ValueError(f"Unsupported bank format: {bank_format}")

        pattern = self.BANK_PATTERNS[bank_format]
        transactions = []

        try:
            for _, row in df.iterrows():
                try:
                    # Parse date
                    txn_date = pd.to_datetime(row[pattern["date_col"]], format=pattern["date_format"])

                    # Parse amount and direction
                    amount_str = str(row[pattern["amount_col"]])
                    amount = float(amount_str.replace(",", "").replace("₹", "").strip())

                    direction_str = str(row[pattern["type_col"]]).upper()
                    if "DR" in direction_str or "DEBIT" in direction_str:
                        direction = "DR"
                    else:
                        direction = "CR"

                    # Extract narration
                    narration = str(row[pattern["narration_col"]])

                    # Extract VPA
                    vpa_match = re.search(self.VPA_REGEX, narration)
                    vpa = vpa_match.group() if vpa_match else "unknown@upi"

                    # Detect merchant
                    merchant_name = self._detect_merchant(vpa, narration)

                    # Categorize
                    category = self.MERCHANT_CATEGORIES.get(merchant_name, "other")

                    transaction = {
                        "txn_date": txn_date.date(),
                        "amount": round(amount, 2),
                        "direction": direction,
                        "vpa": vpa,
                        "merchant_name": merchant_name,
                        "category": category,
                        "remarks": narration[:100],  # Truncate
                        "utr": f"UTR{str(uuid.uuid4())[:12].upper()}",
                    }

                    transactions.append(transaction)

                except Exception as row_error:
                    print(f"Skipping row: {row_error}")
                    continue

            if not transactions:
                raise ValueError("No valid transactions parsed")

            # Create profile ID
            profile_id = str(uuid.uuid4())

            print(f"[OK] Parsed {len(transactions)} transactions from {txn_date}")

            return profile_id, transactions

        except Exception as e:
            print(f"CSV parsing error: {e}")
            raise

    def _detect_merchant(self, vpa: str, narration: str) -> str:
        """Detect merchant name from VPA or narration"""
        vpa_lower = vpa.lower()

        for vpa_prefix, merchant in self.KNOWN_MERCHANTS.items():
            if vpa_prefix in vpa_lower:
                return merchant

        # Check narration for keywords
        narration_lower = narration.lower()
        for merchant, category in self.MERCHANT_CATEGORIES.items():
            if merchant.lower() in narration_lower:
                return merchant

        # Check for rent indicators
        if any(kw in narration_lower for kw in ["rent", "room", "pg", "hostel", "landlord"]):
            return "Rent"

        # Generic fallback
        return "Unknown"


# Quick test
if __name__ == "__main__":
    # Create a test CSV
    test_data = {
        "Date": ["01/01/24", "02/01/24", "03/01/24"],
        "Amount": [100, 200, 50],
        "Type": ["DR", "CR", "DR"],
        "Narration": [
            "UPI/zomato@upi/Food order",
            "UPI/parent@upi/Stipend transfer",
            "UPI/amazon@upi/Book purchase",
        ],
    }
    test_df = pd.DataFrame(test_data)

    parser = StatementParser()
    profile_id, transactions = parser.parse_csv_df(test_df, bank_format="HDFC")

    print(f"Profile ID: {profile_id}")
    print(f"Transactions:")
    for txn in transactions:
        print(f"  {txn['txn_date']} | {txn['direction']} ₹{txn['amount']} | {txn['merchant_name']}")
