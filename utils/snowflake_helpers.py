import json
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from utils.snowflake_conn import (
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