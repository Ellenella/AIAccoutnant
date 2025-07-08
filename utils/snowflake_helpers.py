import json
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from utils.income_manager import IncomeManager
from utils.snowflake_conn import (
    bulk_log_transactions,
    bulk_update_categories,
    get_transactions,
    get_transactions_as_dataframe,
    log_transaction,
    update_transaction_category,
    bulk_upload_transactions
)

def get_recent_transactions(limit: int = 100) -> pd.DataFrame:
    """Get recent transactions with quality scoring"""
    df = get_transactions_as_dataframe(limit)
    
    if not df.empty:
        # Calculate quality score
        df['quality_score'] = (
            df['amount_confidence'] * 0.4 +
            df['category_confidence'] * 0.3 +
            df['merchant_confidence'] * 0.2 +
            df['date_confidence'] * 0.1
        )
    
    return df


def log_receipt_transaction(receipt_data: Dict) -> str:
    """Log a transaction from receipt analysis"""
    try:
        # Ensure all confidence scores are floats
        transaction = {
            "merchant": receipt_data.get("merchant", {}).get("value", ""),
            "merchant_confidence": float(receipt_data.get("merchant", {}).get("confidence", 1.0)),
            "description": receipt_data.get("description", ""),
            "amount": float(receipt_data.get("amount", {}).get("value", 0.0)),
            "amount_confidence": float(receipt_data.get("amount", {}).get("confidence", 1.0)),
            "category": receipt_data.get("category", {}).get("value", "Other"),
            "category_confidence": float(receipt_data.get("category", {}).get("confidence", 1.0)),
            "date": receipt_data.get("date", {}).get("value", datetime.utcnow()),
            "date_confidence": float(receipt_data.get("date", {}).get("confidence", 1.0))
        }
        return log_transaction(transaction)
    except Exception as e:
        print(f"Failed to prepare transaction: {e}")
        raise

def update_category_interactive(transaction_id: str, 
                             new_category: str,
                             confidence: float = 1.0) -> bool:
    """Update category with validation"""
    valid_categories = ["Meals", "Travel", "Office", "Software", "Rent", "Utilities", "Other"]
    if new_category not in valid_categories:
        raise ValueError(f"Invalid category. Must be one of: {valid_categories}")
    
    return update_transaction_category(transaction_id, new_category, confidence)

def get_categorical_summary(min_confidence: float = 0.7) -> Dict[str, float]:
    """Get summary of spending by category"""
    df = get_recent_transactions()
    if df.empty:
        return {}
    
    # Filter by confidence
    df = df[df['amount_confidence'] >= min_confidence]
    
    return df.groupby('category')['amount'].sum().to_dict()

def get_questionable_transactions(threshold: float = 0.5) -> pd.DataFrame:
    """Get transactions with low confidence scores"""
    df = get_recent_transactions()
    if df.empty:
        return pd.DataFrame()
    
    return df[
        (df['amount_confidence'] < threshold) |
        (df['category_confidence'] < threshold) |
        (df['merchant_confidence'] < threshold)
    ].sort_values('amount_confidence')
def log_bulk_receipt_transactions(receipts_data: List[Dict]) -> List[str]:
    """Log multiple transactions from receipt analysis"""
    transactions = []
    for receipt in receipts_data:
        try:
            transactions.append({
                "merchant": receipt.get("merchant", {}).get("value", ""),
                "merchant_confidence": float(receipt.get("merchant", {}).get("confidence", 1.0)),
                "description": receipt.get("description", ""),
                "amount": float(receipt.get("amount", {}).get("value", 0.0)),
                "amount_confidence": float(receipt.get("amount", {}).get("confidence", 1.0)),
                "category": receipt.get("category", {}).get("value", "Other"),
                "category_confidence": float(receipt.get("category", {}).get("confidence", 1.0)),
                "date": receipt.get("date", {}).get("value", datetime.utcnow()),
                "date_confidence": float(receipt.get("date", {}).get("confidence", 1.0))
            })
        except Exception as e:
            print(f"Failed to prepare transaction: {e}")
            continue
    return bulk_log_transactions(transactions)

class TransactionManager:
    """Wrapper class for transaction operations"""
    @staticmethod
    def get_recent_transactions(limit: int = 100) -> pd.DataFrame:
        return get_recent_transactions(limit)
    
    @staticmethod
    def log_receipt(data: Dict) -> str:
        return log_receipt_transaction(data)
    
    @staticmethod
    def update_category(trans_id: str, category: str, confidence: float) -> bool:
        return update_category_interactive(trans_id, category, confidence)
    @staticmethod
    def log_bulk_receipts(data: List[Dict]) -> List[str]:
        return log_bulk_receipt_transactions(data)

    @staticmethod
    def bulk_update_categories(updates: List[Tuple[str, str, float]]) -> int:
        """Bulk update categories with validation"""
        valid_categories = ["Meals", "Travel", "Office", "Software", "Rent", "Utilities", "Other"]
        validated_updates = []
        
        for trans_id, category, confidence in updates:
            if category not in valid_categories:
                print(f"Skipping invalid category {category} for transaction {trans_id}")
                continue
            validated_updates.append((trans_id, category, confidence))

        return bulk_update_categories(validated_updates)

    @staticmethod
    def get_spending_analytics(timeframe: str = 'month') -> Dict:
        """Get spending analytics by timeframe"""
        df = get_recent_transactions(1000)
        if df.empty:
            return {}
        
        # Filter by timeframe
        now = datetime.utcnow()
        if timeframe == 'week':
            df = df[df['date'] >= (now - pd.Timedelta(weeks=1))]
        elif timeframe == 'month':
            df = df[df['date'] >= (now - pd.Timedelta(days=30))]
        elif timeframe == 'quarter':
            df = df[df['date'] >= (now - pd.Timedelta(days=90))]
        
        # Calculate weighted amounts
        df['weighted_amount'] = df['amount'] * df['amount_confidence']
        
        return {
            'by_category': df.groupby('category')['weighted_amount'].sum().to_dict(),
            'by_merchant': df.groupby('merchant')['weighted_amount']
                            .sum()
                            .sort_values(ascending=False)
                            .head(10)
                            .to_dict(),
            'total': df['weighted_amount'].sum(),
            'timeframe': timeframe
        }
    @staticmethod
    def get_monthly_expense_average(months=12) -> float:
        """Get average monthly expenses over specified period"""
        expenses = get_transactions_as_dataframe()
        if expenses.empty:
            return 0.0
        
        # Filter for last N months
        cutoff = datetime.now() - pd.DateOffset(months=months)
        recent_expenses = expenses[expenses['date'] >= cutoff]
        
        if recent_expenses.empty:
            return 0.0
        
        return recent_expenses.groupby(recent_expenses['date'].dt.to_period('M'))['amount'].sum().mean()
    # In your TransactionManager class (snowflake_helpers.py)
    @staticmethod
    def get_combined_financial_report(time_period: str = 'month', 
                                custom_start: datetime = None,
                                custom_end: datetime = None) -> Dict:
        """
        Generate a report combining income and expenses with enhanced features
        
        Args:
            time_period: One of 'week', 'month', 'quarter', 'year'
            custom_start: Optional start date for custom range
            custom_end: Optional end date for custom range
        
        Returns:
            Dictionary containing comprehensive financial report
        """
        # Get all expenses
        expense_df = get_transactions_as_dataframe(10000)
        
        # Get all income with proper column renaming
        income_df = IncomeManager.get_income_as_dataframe(10000).rename(columns={
            'SOURCE': 'source',
            'PAYMENT_METHOD': 'payment_method',
            'IS_TAXABLE': 'is_taxable',
            'DESCRIPTION': 'description',
            'RECURRENCE': 'recurrence',
            'AMOUNT': 'amount',
            'CATEGORY': 'category',
            'ID': 'id',
            'DATE': 'date'
        })

        # Convert dates to datetime if they're not already
        if not expense_df.empty:
            expense_df['date'] = pd.to_datetime(expense_df['date'])
        if not income_df.empty:
            income_df['date'] = pd.to_datetime(income_df['date'])

        # Determine date range
        now = datetime.utcnow()
        if custom_start and custom_end:
            cutoff = custom_start
            end_date = custom_end
        else:
            end_date = now
            if time_period == 'week':
                cutoff = now - pd.Timedelta(weeks=1)
            elif time_period == 'month':
                cutoff = now - pd.Timedelta(days=30)
            elif time_period == 'quarter':
                cutoff = now - pd.Timedelta(days=90)
            elif time_period == 'year':
                cutoff = now - pd.Timedelta(days=365)
            else:
                cutoff = now - pd.Timedelta(days=30)  # Default to month

        # Filter dataframes with date validation
        if not expense_df.empty:
            expense_df = expense_df[(expense_df['date'] >= cutoff) & 
                                (expense_df['date'] <= end_date)]
            expense_df['amount'] = expense_df['amount'].abs()  # Convert to positive values
        
        if not income_df.empty:
            income_df = income_df[(income_df['date'] >= cutoff) & 
                                (income_df['date'] <= end_date)]

        # Calculate monthly trends with proper date handling
        def calculate_monthly_trend(df, amount_col='amount'):
            if df.empty:
                return {}
            try:
                return df.groupby(pd.Grouper(key='date', freq='M'))[amount_col] \
                    .sum() \
                    .to_dict()
            except Exception as e:
                print(f"Error calculating monthly trend: {e}")
                return {}

        # Generate enhanced report structure
        report = {
            'time_period': time_period if not custom_start else 'custom',
            'date_range': {
                'start': cutoff.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'income': {
                'total': float(income_df['amount'].sum()) if not income_df.empty else 0.0,
                'top_sources': income_df.groupby('source')['amount']
                                    .sum()
                                    .nlargest(5)
                                    .to_dict() if not income_df.empty else {},
                'monthly_trend': calculate_monthly_trend(income_df),
                'average': float(income_df['amount'].mean()) if not income_df.empty else 0.0,
                'count': len(income_df),
                'recurrence_breakdown': income_df['recurrence'].value_counts().to_dict() 
                                    if not income_df.empty else {}
            },
            'expenses': {
                'total': float(expense_df['amount'].sum()) if not expense_df.empty else 0.0,
                'top_merchants': expense_df.groupby('merchant')['amount']
                                        .sum()
                                        .nlargest(10)
                                        .to_dict() if not expense_df.empty else {},
                'category_breakdown': expense_df.groupby('category')['amount']
                                            .sum()
                                            .sort_values(ascending=False)
                                            .to_dict() if not expense_df.empty else {},
                'monthly_trend': calculate_monthly_trend(expense_df),
                'average': float(expense_df['amount'].mean()) if not expense_df.empty else 0.0,
                'count': len(expense_df),
                'confidence_metrics': {
                    'avg_amount_confidence': float(expense_df['amount_confidence'].mean()) 
                                        if not expense_df.empty else 0.0,
                    'low_confidence_count': len(expense_df[expense_df['amount_confidence'] < 0.7])
                }
            },
            'net_flow': {
                'total': (float(income_df['amount'].sum()) - float(expense_df['amount'].sum()))
                        if (not income_df.empty or not expense_df.empty) else 0.0,
                'daily_average': (
                    (float(income_df['amount'].sum()) - float(expense_df['amount'].sum())) 
                    / ((end_date - cutoff).days or 1)
                    if (not income_df.empty or not expense_df.empty) else 0.0
                ),
            },
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'income_records': len(income_df),
                'expense_records': len(expense_df)
            }
        }
        
        return report