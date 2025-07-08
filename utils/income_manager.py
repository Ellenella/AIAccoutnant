import os
import pandas as pd
import snowflake.connector
from typing import List, Dict, Optional
from datetime import datetime
import uuid
from dotenv import load_dotenv
import json

from utils.snowflake_conn import get_conn

load_dotenv()

class IncomeManager:
    @staticmethod
    def log_income(income_data: Dict) -> str:
        """Log a new income entry"""
        required_fields = ['source', 'amount', 'date']
        if not all(field in income_data for field in required_fields):
            raise ValueError(f"Missing required fields: {required_fields}")
        
        income_id = str(uuid.uuid4())
        try:
            tags_json = json.dumps(income_data.get('tags', []))  # Convert list to JSON string


            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO income (
                        id, date, source, amount, category,
                        payment_method, description, is_taxable,
                        recurrence
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        income_id,
                        income_data.get('date', datetime.utcnow()),
                        income_data['source'],
                        income_data['amount'],
                        income_data.get('category', 'Other'),
                        income_data.get('payment_method', 'Unknown'),
                        income_data.get('description', ''),
                        income_data.get('is_taxable', True),
                        income_data.get('recurrence', 'one-time')
                    )
                )
                conn.commit()
            return income_id
        except Exception as e:
            print(f"Error logging income: {e}")
            raise

    @staticmethod
    def get_income(limit: int = 100) -> List[Dict]:
        """Retrieve income records"""
        try:
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT 
                        id, date, source, amount, category,
                        payment_method, description, is_taxable,
                        recurrence,tags
                    FROM income_summary
                    ORDER BY date DESC
                    LIMIT {limit}
                """)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching income: {e}")
            return []

    @staticmethod
    def get_income_as_dataframe(limit: int = 100) -> pd.DataFrame:
        """Get income records as DataFrame"""
        income = IncomeManager.get_income(limit)
        return pd.DataFrame(income) if income else pd.DataFrame()
    @staticmethod
    def get_monthly_income_average(months=12) -> float:
        """Get average monthly income over specified period"""
        income = IncomeManager.get_income_as_dataframe()
        if income.empty:
            return 0.0
        
        # Ensure we have DATE and AMOUNT columns (adjust as needed for your schema)
        if 'DATE' not in income.columns or 'AMOUNT' not in income.columns:
            return 0.0
        
        # Filter for last N months
        cutoff = datetime.now() - pd.DateOffset(months=months)
        recent_income = income[income['DATE'] >= cutoff]
        
        if recent_income.empty:
            return 0.0
        
        return recent_income.groupby(recent_income['DATE'].dt.to_period('M'))['AMOUNT'].sum().mean()

    @staticmethod
    def get_income_report(timeframe: str = 'month') -> Dict:
        """Generate income analytics report with properly structured data"""
        df = IncomeManager.get_income_as_dataframe(1000)
        
        if df.empty:
            return {}
        
        if 'date' not in df.columns:
            print("Warning: 'date' column not found in the income data.")
            return {}
        
        # Convert date column if needed
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])
        
        now = datetime.utcnow()
        if timeframe == 'week':
            df = df[df['date'] >= (now - pd.Timedelta(weeks=1))]
        elif timeframe == 'month':
            df = df[df['date'] >= (now - pd.Timedelta(days=30))]
        elif timeframe == 'quarter':
            df = df[df['date'] >= (now - pd.Timedelta(days=90))]
        elif timeframe == 'year':
            df = df[df['date'] >= (now - pd.Timedelta(days=365))]
        
        by_source = df.groupby('source')['amount'] \
                    .sum() \
                    .reset_index() \
                    .sort_values('amount', ascending=False)
        
        by_category = df.groupby('category')['amount'] \
                    .sum() \
                    .reset_index() \
                    .sort_values('amount', ascending=False)
        
        by_time = df.groupby(pd.Grouper(key='date', freq='M'))['amount'] \
                .sum() \
                .reset_index()
        
        return {
            'total_income': float(df['amount'].sum()),
            'average_income': float(df['amount'].mean()),
            'by_source': by_source,
            'by_category': by_category,
            'by_time': by_time
        }
    # Add to income_manager.py
    # In income_manager.py, update the get_income_for_transactions_view method:
    @staticmethod
    def get_income_for_transactions_view(limit: int = 100) -> pd.DataFrame:
        """Get income records formatted for transactions view"""
        income = IncomeManager.get_income(limit)
        if not income:
            return pd.DataFrame()
        
        df = pd.DataFrame(income)
          # Normalize column names: lowercase and deduplicate
        # Ensure date column exists and is proper datetime
        df['date'] = pd.to_datetime(df['DATE'])
        
        # Standardize column names to match transactions
        df = df.rename(columns={
            'SOURCE': 'merchant',
            'PAYMENT_METHOD': 'description',
            'IS_TAXABLE':'is_taxable',
            'RECURRENCE': 'recurrence',
            'AMOUNT': 'amount',
            'CATEGORY': 'category',
            'ID': 'id',
        })
        
        # Add type identifier and ensure positive amounts
        df['type'] = 'income'
        df['amount_display'] = df['amount'].abs()
        
        expected_columns = [
        'id', 'date', 'merchant', 'amount', 'amount_display',
        'type', 'category', 'description', 'is_taxable', 'recurrence'
      ]

        # Ensure all expected columns exist
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None

    # Step 5: Reindex safely with ensured unique columns
        return df.loc[:, expected_columns]
    @staticmethod
    def get_recent_income(limit: int = 100) -> pd.DataFrame:
        """Get recent income records with quality scoring"""
        df = IncomeManager.get_income_as_dataframe(limit)
        
        if df.empty:
            return df
        
        # Normalize column names to lowercase for consistency
        df.columns = [col.lower() for col in df.columns]
        
        # Ensure 'date' column is datetime type
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        else:
            raise ValueError("Income data must contain a 'date' column")
        
        # Rename columns to align with expense data for combined views
        df = df.rename(columns={
            'source': 'merchant',            # income 'source' to generic 'merchant'
            'payment_method': 'description'  # standardize description field
        })
        
        # Add 'type' column to distinguish income
        df['type'] = 'income'
        
        # Calculate quality score similarly if confidence columns exist
        confidence_cols = ['amount_confidence', 'category_confidence', 'merchant_confidence', 'date_confidence']
        if all(col in df.columns for col in confidence_cols):
            df['quality_score'] = (
                df['amount_confidence'] * 0.4 +
                df['category_confidence'] * 0.3 +
                df['merchant_confidence'] * 0.2 +
                df['date_confidence'] * 0.1
            )
        else:
            # Optionally, fill quality_score with 1 if confidences are missing
            df['quality_score'] = 1.0
        
        # Add amount_display as absolute value for UI display
        df['amount_display'] = df['amount'].abs()
        
        # Select and reorder columns to match expected schema
        columns_to_return = [
            'id',
            'date',
            'merchant',
            'amount',
            'amount_display',
            'type',
            'category',
            'description',
            'is_taxable',
            'recurrence',
            'quality_score'
        ]
        
        # Filter to columns existing in df to avoid key errors
        columns_existing = [col for col in columns_to_return if col in df.columns]
        df = df[columns_existing]
        
        return df.reset_index(drop=True)
