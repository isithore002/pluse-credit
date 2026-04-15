"""
pdf_parser.py - Parse bank statements (PDF/CSV) using pdfplumber
Supports HDFC, SBI, ICICI, Kotak formats
"""

import pandas as pd
import pdfplumber
import re
import uuid
from typing import List, Dict, Tuple, Optional

try:
    from pdfminer.pdfdocument import PDFPasswordIncorrect
except Exception:
    PDFPasswordIncorrect = Exception


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

    COLUMN_ALIASES = {
        "date": [
            "date",
            "txn date",
            "transaction date",
            "value date",
        ],
        "amount": [
            "amount",
            "amount (inr)",
            "transaction amount",
            "txn amount",
        ],
        "type": [
            "type",
            "dr/cr",
            "cr/dr",
            "debit/credit",
            "transaction type",
        ],
        "narration": [
            "narration",
            "description",
            "remarks",
            "transaction remarks",
            "note",
            "details",
        ],
        "debit": [
            "debit",
            "withdrawal",
            "dr amount",
            "debit amount",
            "amount debited",
        ],
        "credit": [
            "credit",
            "deposit",
            "cr amount",
            "credit amount",
            "amount credited",
        ],
    }

    def detect_bank_format(self, df: pd.DataFrame) -> str:
        """Auto-detect bank format from CSV column names"""
        columns_lower = [str(col).strip().lower() for col in df.columns]

        for bank, pattern in self.BANK_PATTERNS.items():
            if pattern["date_col"].lower() in columns_lower:
                return bank

        return "GENERIC"

    def _resolve_column(self, df: pd.DataFrame, candidates: List[str]) -> str:
        """Resolve a column name from candidate aliases (case-insensitive)."""
        normalized = {
            str(col).replace("\ufeff", "").strip().lower(): col
            for col in df.columns
        }
        for candidate in candidates:
            key = candidate.strip().lower()
            if key in normalized:
                return normalized[key]
        return ""

    def _parse_date(self, value, explicit_format: str = "") -> pd.Timestamp:
        """Parse dates with explicit format first, then fall back to flexible parsing."""
        if explicit_format:
            try:
                return pd.to_datetime(value, format=explicit_format)
            except Exception:
                pass
        return pd.to_datetime(value, dayfirst=True)

    def _parse_amount(self, value) -> float:
        """Parse amount values that may include currency symbols and separators."""
        amount_str = str(value)
        amount_str = amount_str.replace(",", "").replace("₹", "").strip()
        amount_str = re.sub(r"[^0-9.+-]", "", amount_str)
        if not amount_str:
            raise ValueError("empty amount")
        return float(amount_str)

    def _normalize_direction(self, raw_type: str, amount: float) -> str:
        """Normalize transaction direction to DR/CR."""
        value = str(raw_type).upper()
        if "DR" in value or "DEBIT" in value:
            return "DR"
        if "CR" in value or "CREDIT" in value:
            return "CR"
        return "DR" if amount < 0 else "CR"

    def _find_date_token(self, text: str) -> Optional[str]:
        """Extract a date token from free-form text."""
        patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}\b",
            r"\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def _parse_unstructured_table(self, table: List[List]) -> List[Dict]:
        """Parse rows from headerless/irregular PDF tables."""
        parsed = []

        # Skip first row as header candidate when table has more than one row.
        rows = table[1:] if len(table) > 1 else table
        for row in rows:
            cells = [str(cell).strip() for cell in row if str(cell or "").strip()]
            if not cells:
                continue

            row_text = " ".join(cells)
            date_token = self._find_date_token(row_text)
            if not date_token:
                continue

            has_txn_signal = bool(
                re.search(self.VPA_REGEX, row_text, re.IGNORECASE)
                or re.search(r"\bUPI\b", row_text, re.IGNORECASE)
                or re.search(r"\b(DR|CR|DEBIT|CREDIT)\b", row_text, re.IGNORECASE)
            )
            if not has_txn_signal:
                continue

            row_wo_date = row_text.replace(date_token, " ")
            numeric_tokens = re.findall(
                r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?(?!\d)",
                row_wo_date,
            )
            if not numeric_tokens:
                continue

            # In most statements with a balance column, amount is second-last numeric token.
            amount_token = numeric_tokens[-2] if len(numeric_tokens) >= 2 else numeric_tokens[-1]

            try:
                txn_date = self._parse_date(date_token)
                amount = self._parse_amount(amount_token)
            except Exception:
                continue

            direction_match = re.search(r"\b(DR|CR|DEBIT|CREDIT)\b", row_text, re.IGNORECASE)
            direction = self._normalize_direction(direction_match.group(1), amount) if direction_match else "DR"

            vpa_match = re.search(self.VPA_REGEX, row_text)
            vpa = vpa_match.group(0) if vpa_match else "unknown@upi"
            merchant_name = self._detect_merchant(vpa, row_text)
            category = self.MERCHANT_CATEGORIES.get(merchant_name, "other")

            parsed.append(
                {
                    "txn_date": txn_date.date(),
                    "amount": round(amount, 2),
                    "direction": direction,
                    "vpa": vpa,
                    "merchant_name": merchant_name,
                    "category": category,
                    "remarks": row_text[:100],
                    "utr": f"UTR{str(uuid.uuid4())[:12].upper()}",
                }
            )

        return parsed

    def _dedupe_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """Deduplicate transactions generated by multiple table extraction passes."""
        seen = set()
        deduped = []
        for txn in transactions:
            key = (
                str(txn.get("txn_date")),
                float(txn.get("amount", 0.0)),
                txn.get("direction", ""),
                txn.get("vpa", ""),
                txn.get("remarks", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(txn)
        return deduped

    def parse_pdf(self, pdf_path: str, bank_format: str = None, pdf_password: str = "") -> Tuple[str, List[Dict]]:
        """
        Parse PDF statement and extract transactions
        Returns: (profile_id, transactions_list)
        """
        try:
            with pdfplumber.open(pdf_path, password=(pdf_password or None)) as pdf:
                # Extract all tables
                tables = []
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)

            if not tables:
                raise ValueError(
                    "No tabular transaction data found in PDF. "
                    "Please upload a CSV export or a text-based statement PDF."
                )

            parse_errors = []

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Attempt 1: first row as header
                try:
                    header = [
                        (str(col).replace("\ufeff", "").strip() if col is not None else f"col_{i}")
                        for i, col in enumerate(table[0])
                    ]
                    df = pd.DataFrame(table[1:], columns=header).dropna(how="all")
                    if not df.empty:
                        return self.parse_csv_df(df, bank_format)
                except Exception as first_error:
                    parse_errors.append(f"first-row-header parse failed: {first_error}")

                # Attempt 2: find a likely header row in first few rows
                try:
                    candidate_idx = -1
                    for idx, row in enumerate(table[:5]):
                        if not row:
                            continue
                        row_text = " ".join(str(cell or "").lower() for cell in row)
                        if any(token in row_text for token in ["date", "amount", "narration", "description", "remarks"]):
                            candidate_idx = idx
                            break

                    if candidate_idx >= 0 and len(table) > candidate_idx + 1:
                        header_row = table[candidate_idx]
                        header = [
                            (str(col).replace("\ufeff", "").strip() if col is not None else f"col_{i}")
                            for i, col in enumerate(header_row)
                        ]
                        df = pd.DataFrame(table[candidate_idx + 1 :], columns=header).dropna(how="all")
                        if not df.empty:
                            return self.parse_csv_df(df, bank_format)
                except Exception as header_scan_error:
                    parse_errors.append(f"header-scan parse failed: {header_scan_error}")

            # Fallback: parse irregular tables with missing/blank headers.
            fallback_transactions = []
            for table in tables:
                if not table:
                    continue
                fallback_transactions.extend(self._parse_unstructured_table(table))

            fallback_transactions = self._dedupe_transactions(fallback_transactions)
            if fallback_transactions:
                profile_id = str(uuid.uuid4())
                print(f"[OK] Parsed {len(fallback_transactions)} transactions using unstructured PDF fallback")
                return profile_id, fallback_transactions

            error_summary = "; ".join(parse_errors[-3:]) if parse_errors else "no parseable table layout"
            raise ValueError(f"Could not parse PDF transaction tables ({error_summary})")

        except PDFPasswordIncorrect:
            raise ValueError("Incorrect PDF password. Please enter the correct password and try again.")
        except Exception as e:
            detail = str(e) or repr(e)
            if "PDFPasswordIncorrect" in detail:
                if pdf_password:
                    raise ValueError("Incorrect PDF password. Please enter the correct password and try again.")
                raise ValueError("This PDF is password-protected. Enter the PDF password and try again.")
            print(f"PDF parsing error: {detail}")
            raise

    def parse_csv(self, csv_path: str, bank_format: str = None) -> Tuple[str, List[Dict]]:
        """
        Parse CSV statement and extract transactions
        Returns: (profile_id, transactions_list)
        """
        try:
            # sep=None lets pandas auto-detect comma/semicolon/tab delimiters.
            df = pd.read_csv(csv_path, sep=None, engine="python")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, sep=None, engine="python", encoding="latin-1")
        return self.parse_csv_df(df, bank_format)

    def parse_csv_df(self, df: pd.DataFrame, bank_format: str = None) -> Tuple[str, List[Dict]]:
        """
        Parse DataFrame and extract transactions
        """
        if bank_format is None or str(bank_format).upper() in {"", "AUTO", "GENERIC"}:
            bank_format = self.detect_bank_format(df)

        print(f"Detected bank format: {bank_format}")

        if bank_format not in self.BANK_PATTERNS:
            bank_format = self.detect_bank_format(df)
            if bank_format not in self.BANK_PATTERNS:
                raise ValueError(f"Unsupported bank format: {bank_format}")

        pattern = self.BANK_PATTERNS[bank_format]

        date_col = self._resolve_column(df, [pattern["date_col"]] + self.COLUMN_ALIASES["date"])
        amount_col = self._resolve_column(df, [pattern["amount_col"]] + self.COLUMN_ALIASES["amount"])
        type_col = self._resolve_column(df, [pattern["type_col"]] + self.COLUMN_ALIASES["type"])
        narration_col = self._resolve_column(df, [pattern["narration_col"]] + self.COLUMN_ALIASES["narration"])
        debit_col = self._resolve_column(df, self.COLUMN_ALIASES["debit"])
        credit_col = self._resolve_column(df, self.COLUMN_ALIASES["credit"])

        # If requested bank format doesn't match the file columns, retry with auto-detection.
        if not date_col or not amount_col or not narration_col:
            detected = self.detect_bank_format(df)
            if detected in self.BANK_PATTERNS and detected != bank_format:
                bank_format = detected
                pattern = self.BANK_PATTERNS[bank_format]
                date_col = self._resolve_column(df, [pattern["date_col"]] + self.COLUMN_ALIASES["date"])
                amount_col = self._resolve_column(df, [pattern["amount_col"]] + self.COLUMN_ALIASES["amount"])
                type_col = self._resolve_column(df, [pattern["type_col"]] + self.COLUMN_ALIASES["type"])
                narration_col = self._resolve_column(df, [pattern["narration_col"]] + self.COLUMN_ALIASES["narration"])
                debit_col = self._resolve_column(df, self.COLUMN_ALIASES["debit"])
                credit_col = self._resolve_column(df, self.COLUMN_ALIASES["credit"])

        has_amount_path = bool(amount_col or (debit_col and credit_col) or debit_col or credit_col)
        if not date_col or not narration_col or not has_amount_path:
            raise ValueError(
                "Could not map required CSV columns. "
                f"Found columns: {list(df.columns)}"
            )

        transactions = []

        try:
            for _, row in df.iterrows():
                try:
                    # Parse date
                    txn_date = self._parse_date(row[date_col], explicit_format=pattern.get("date_format", ""))

                    # Parse amount and direction
                    if amount_col:
                        amount = self._parse_amount(row[amount_col])
                        direction_source = row[type_col] if type_col else ""
                        direction = self._normalize_direction(direction_source, amount)
                    else:
                        debit_value = row[debit_col] if debit_col else ""
                        credit_value = row[credit_col] if credit_col else ""

                        has_debit = str(debit_value).strip() not in {"", "nan", "None", "0", "0.0"}
                        has_credit = str(credit_value).strip() not in {"", "nan", "None", "0", "0.0"}

                        if has_debit and not has_credit:
                            amount = self._parse_amount(debit_value)
                            direction = "DR"
                        elif has_credit and not has_debit:
                            amount = self._parse_amount(credit_value)
                            direction = "CR"
                        elif has_debit and has_credit:
                            debit_amt = self._parse_amount(debit_value)
                            credit_amt = self._parse_amount(credit_value)
                            if credit_amt >= debit_amt:
                                amount = credit_amt
                                direction = "CR"
                            else:
                                amount = debit_amt
                                direction = "DR"
                        else:
                            raise ValueError("no amount value in row")

                    # Extract narration
                    narration = str(row[narration_col])

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
