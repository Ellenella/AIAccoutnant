import streamlit as st
import requests
import os
import groq
import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
from typing import Dict, Any

# --- Configuration ---
GROQ_MODEL = "llama3-70b-8192"
ASI_API_URL = "https://api.asi1.ai/v1/chat/completions"
ASI_MODEL = "asi1-mini"

# --- API Clients ---
class GroqClient:
    def __init__(self):
        self.client = groq.Client(api_key=st.secrets["GROQ_API_KEY"])

    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=4000
        )
        return response.choices[0].message.content

class ASIClient:
    @staticmethod
    def get_advice(prompt: str, temperature: float = 0.3) -> str:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {st.secrets["ASI_API_KEY"]}'
        }
        
        payload = json.dumps({
            "model": ASI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 1000
        })
        
        try:
            response = requests.post(ASI_API_URL, headers=headers, data=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            st.error(f"ASI API Error: {str(e)}")
            return ""

# --- Financial Services ---
class MarketIntelligence:
    def __init__(self):
        self.groq = GroqClient()
    
    def analyze_security(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """Comprehensive security analysis with Groq"""
        # Main analysis prompt
        analysis_prompt = f"""Perform professional analysis for {symbol} (last {days} days):
        
        1. Technical Analysis:
        - Trend analysis with moving averages
        - Key support/resistance levels
        - RSI and MACD indicators
        
        2. Fundamental Analysis:
        - Valuation metrics (P/E, P/B, EV/EBITDA)
        - Growth projections
        - Dividend analysis if applicable
        
        3. Risk Assessment:
        - Volatility metrics
        - Liquidity analysis
        - Sector-specific risks
        
        4. Recommendation:
        - Buy/Hold/Sell with price targets
        - Optimal entry/exit points
        
        Format as markdown with clear sections."""
        
        analysis = self.groq.generate(analysis_prompt)
        
        # Generate visual data for charts - with improved JSON handling
        risk_prompt = f"""Provide a risk assessment for {symbol} in this EXACT JSON format:
        {{
            "volatility_score": 0-100,
            "liquidity_score": 0-100,
            "sector_risk": "Low/Medium/High",
            "overall_risk_rating": "Low/Medium/High",
            "risk_factors": ["list", "of", "key", "risks"]
        }}
        
        Only return the JSON object, nothing else."""
        
        try:
            risk_response = self.groq.generate(risk_prompt, temperature=0.1)
            # Clean the response to ensure valid JSON
            risk_response = risk_response.strip().strip('`').replace('json\n', '')
            risk_data = json.loads(risk_response)
        except json.JSONDecodeError as e:
            st.error(f"Failed to parse risk assessment: {str(e)}")
            st.warning(f"Raw response: {risk_response}")
            risk_data = {
                "volatility_score": 50,
                "liquidity_score": 50,
                "sector_risk": "Medium",
                "overall_risk_rating": "Medium",
                "risk_factors": ["Data unavailable"],
                "error": True
            }
        except Exception as e:
            st.error(f"Risk assessment failed: {str(e)}")
            risk_data = {
                "volatility_score": 50,
                "liquidity_score": 50,
                "sector_risk": "Medium",
                "overall_risk_rating": "Medium",
                "risk_factors": ["Assessment failed"],
                "error": True
            }
        
        return {
            "analysis": analysis,
            "risk_data": risk_data
        }
# --- Streamlit UI ---
def detail_investmentplan():
    st.header("AI-Powered Market Analysis")
    symbol = st.text_input("Enter ticker symbol", "AAPL").upper()
    analysis_days = st.slider("Analysis period (days)", 7, 365, 30)
        
    if st.button("Analyze Security"):
        with st.spinner("Running comprehensive analysis..."):
            market = MarketIntelligence()
            result = market.analyze_security(symbol, analysis_days)
                
            # Display results
            st.subheader(f"{symbol} Analysis Report")
            st.markdown(result["analysis"])
                
            # Risk visualization
            st.subheader("Risk Assessment")
            risk_df = pd.DataFrame.from_dict(result["risk_data"], orient="index").reset_index()
            risk_df.columns = ["Metric", "Value"]
            fig = px.bar(risk_df, x="Metric", y="Value", 
                         title="Risk Profile", color="Metric")
            st.plotly_chart(fig, use_container_width=True)
    
    