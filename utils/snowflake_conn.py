import os
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from typing import List, Dict, Optional, Tuple, Any
import uuid
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import streamlit as st

# Load environment variables
load_dotenv()

def get_conn():
    """Get authenticated Snowflake connection"""
    required_vars = ["SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", 
                   "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_WAREHOUSE",
                   "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA"]

    missing = [var for var in required_vars if not st.secrets[var]]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    try:
        return snowflake.connector.connect(
            user=st.secrets["SNOWFLAKE_USER"],
            password=st.secrets["SNOWFLAKE_PASSWORD"],
            account=st.secrets["SNOWFLAKE_ACCOUNT"],
            warehouse=st.secrets["SNOWFLAKE_WAREHOUSE"],
            database=st.secrets["SNOWFLAKE_DATABASE"],
            schema=st.secrets["SNOWFLAKE_SCHEMA"]
        )
    except Exception as e:
        raise ConnectionError(f"Snowflake connection failed: {str(e)}")

def init_db():
    """Initialize database with proper tables and views"""
    try:
        with get_conn() as conn:
            # Create main transactions table
            conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id STRING PRIMARY KEY,
                date TIMESTAMP_NTZ,
                merchant STRING,
                merchant_confidence FLOAT,
                description STRING,
                amount FLOAT,
                amount_confidence FLOAT,
                category STRING,
                category_confidence FLOAT,
                date_confidence FLOAT,
                is_reconciled BOOLEAN DEFAULT FALSE
            )
            """)
            
            # Create view for easier querying
            conn.cursor().execute("""
            CREATE OR REPLACE VIEW enriched_transactions AS
            SELECT 
                id, 
                date, 
                merchant, 
                merchant_confidence,
                description, 
                amount, 
                amount_confidence,
                category, 
                category_confidence,
                date_confidence,
                is_reconciled
            FROM transactions
            ORDER BY date DESC
            """)
            conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS income (
                id STRING PRIMARY KEY,
                date TIMESTAMP_NTZ,
                source STRING,
                amount FLOAT,
                category STRING,
                payment_method STRING,
                description STRING,
                is_taxable BOOLEAN DEFAULT TRUE,
                recurrence STRING,  -- 'one-time', 'weekly', 'monthly', 'annual',
                tags ARRAY
            )
            """)
            
            # Create view for easier querying
            conn.cursor().execute("""
            CREATE OR REPLACE VIEW income_summary AS
                SELECT 
                    id,
                    date,
                    source,
                    amount,
                    category,
                    payment_method,
                    description,
                    is_taxable,
                    recurrence,
                    tags
                            
                FROM income
                ORDER BY date DESC
            """)
            print("Database initialized successfully")
            
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

def log_transaction(transaction_data: dict) -> str:
    """Log a transaction with automatic ID generation"""
    if 'id' not in transaction_data:
        transaction_data['id'] = str(uuid.uuid4())
    
    try:
        
        with get_conn() as conn:
            cursor = conn.cursor()
            
            
            # Use parameterized query
            cursor.execute(
                """
                INSERT INTO transactions (
                    id, date, merchant, merchant_confidence,
                    description, amount, amount_confidence,
                    category, category_confidence, date_confidence,
                    is_reconciled
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    transaction_data.get("id"),
                    transaction_data.get("date", datetime.utcnow()),
                    transaction_data.get("merchant", ""),
                    float(transaction_data.get("merchant_confidence", 1.0)),
                    transaction_data.get("description", ""),
                    float(transaction_data.get("amount", 0.0)),
                    float(transaction_data.get("amount_confidence", 1.0)),
                    transaction_data.get("category", "Other"),
                    float(transaction_data.get("category_confidence", 1.0)),
                    float(transaction_data.get("date_confidence", 1.0)),
                    bool(transaction_data.get("is_reconciled", False))
                )
            )
            conn.commit()
            
        return transaction_data['id']
    except Exception as e:
        print(f"Transaction logging failed: {e}")
        raise
# Add these methods to your Snowflake connector

def bulk_log_transactions(transactions: List[Dict]) -> List[str]:
    """Bulk log transactions with automatic ID generation"""
    if not transactions:
        return []
    
    # Generate IDs for all transactions
    for t in transactions:
        if 'id' not in t:
            t['id'] = str(uuid.uuid4())
    
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Prepare the bulk insert query
            query = """
            INSERT INTO transactions (
                id, date, merchant, merchant_confidence,
                description, amount, amount_confidence,
                category, category_confidence, date_confidence,
                is_reconciled
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Prepare all values
            values = []
            for t in transactions:
                values.append((
                    t.get("id"),
                    t.get("date", datetime.utcnow()),
                    t.get("merchant", ""),
                    float(t.get("merchant_confidence", 1.0)),
                    t.get("description", ""),
                    float(t.get("amount", 0.0)),
                    float(t.get("amount_confidence", 1.0)),
                    t.get("category", "Other"),
                    float(t.get("category_confidence", 1.0)),
                    float(t.get("date_confidence", 1.0)),
                    bool(t.get("is_reconciled", False))
                ))
            
            # Execute the bulk insert
            cursor.executemany(query, values)
            conn.commit()
            
            return [t['id'] for t in transactions]
    except Exception as e:
        print(f"Bulk transaction logging failed: {e}")
        raise

def bulk_update_categories(self, updates: List[Tuple[str, str, float]]) -> int:
    """Bulk update transaction categories"""
    if not updates:
        return 0
    
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Prepare the bulk update query
            query = """
            UPDATE transactions
            SET category = %s,
                category_confidence = %s,
                last_updated = CURRENT_TIMESTAMP()
            WHERE id = %s
            """
            
            # Execute the bulk update
            cursor.executemany(query, updates)
            conn.commit()
            
            return cursor.rowcount
    except Exception as e:
        print(f"Bulk update failed: {e}")
        return 0
def get_transactions(limit: int = 100) -> List[Tuple]:
    """Get recent transactions as tuples"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT 
                    id, date, merchant, merchant_confidence,
                    description, amount, amount_confidence,
                    category, category_confidence, date_confidence,
                    is_reconciled
                FROM enriched_transactions
                ORDER BY date DESC
                LIMIT {limit}
            """)
            return cursor.fetchall()
    except Exception as e:
        print(f"Failed to fetch transactions: {e}")
        return []

def get_transactions_as_dataframe(limit: int = 100) -> pd.DataFrame:
    """Get transactions as DataFrame"""
    columns = [
        'id', 'date', 'merchant', 'merchant_confidence',
        'description', 'amount', 'amount_confidence',
        'category', 'category_confidence', 'date_confidence',
        'is_reconciled'
    ]
    
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT * FROM enriched_transactions
                ORDER BY date DESC
                LIMIT {limit}
            """)
            rows = cursor.fetchall()
            df = pd.DataFrame(rows, columns=columns)
            
            # Convert data types
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                numeric_cols = ['amount', 'amount_confidence', 'merchant_confidence',
                              'category_confidence', 'date_confidence']
                df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
                
            return df
    except Exception as e:
        print(f"Failed to create DataFrame: {e}")
        return pd.DataFrame(columns=columns)

def update_transaction_category(transaction_id: str, 
                             new_category: str,
                             confidence: float = 1.0) -> bool:
    """Update transaction category"""
    try:
        with get_conn() as conn:
            conn.cursor().execute(
                """
                UPDATE transactions
                SET category = %s,
                    category_confidence = %s,
                    last_updated = CURRENT_TIMESTAMP()
                WHERE id = %s
                """,
                (new_category, confidence, transaction_id)
            )
            return True
    except Exception as e:
        print(f"Update failed: {e}")
        return False

def bulk_upload_transactions(df: pd.DataFrame) -> int:
    """Bulk upload transactions from DataFrame"""
    try:
        with get_conn() as conn:
            success, _, nrows, _ = write_pandas(
                conn,
                df,
                table_name="TRANSACTIONS",
                auto_create_table=False
            )
            return nrows if success else 0
    except Exception as e:
        print(f"Bulk upload failed: {e}")
        return 0