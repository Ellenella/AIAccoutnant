import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import json
import os
from utils.income_manager import IncomeManager
from utils.snowflake_helpers import TransactionManager

# --- ASI Integration ---
class ASIFinancialAdvisor:
    """Handles all ASI API interactions for financial advice"""
    
    @staticmethod
    def get_advice(prompt: str, temperature: float = 0.3) -> str:
        """Get AI-generated financial advice from ASI"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {st.secrets["ASI_API_KEY"]}'
        }
        
        payload = json.dumps({
            "model": "asi1-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 1000
        })
        
        try:
            response = requests.post(
                "https://api.asi1.ai/v1/chat/completions",
                headers=headers,
                data=payload
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            st.error(f"Failed to get financial advice: {str(e)}")
            return ""

# --- Savings Calculator ---
class SavingsPlanner:
    """Handles savings projections with real financial data"""
    
    @staticmethod
    def get_financial_snapshot():
        """Get current financial position from database"""
        income = IncomeManager.get_monthly_income_average()
        expenses = TransactionManager.get_monthly_expense_average()
        savings_capacity = income - expenses
        return {
            "monthly_income": income,
            "monthly_expenses": expenses,
            "savings_capacity": savings_capacity
        }
    
    @staticmethod
    def generate_projection(goal_amount, current_savings, monthly_contribution, years, risk_profile):
        """Generate detailed savings projection"""
        growth_rates = {"Conservative": 0.03, "Moderate": 0.06, "Aggressive": 0.09}
        rate = growth_rates.get(risk_profile, 0.05)
        monthly_rate = rate / 12
        months = years * 12
        
        dates = [datetime.now() + timedelta(days=30*i) for i in range(months+1)]
        balances = [current_savings]
        
        for _ in range(months):
            interest = balances[-1] * monthly_rate
            new_balance = balances[-1] + monthly_contribution + interest
            balances.append(new_balance)
        
        return pd.DataFrame({
            "Date": dates,
            "Balance": balances,
            "Growth_Rate": risk_profile
        })

# --- Investment Recommender ---
class InvestmentAdvisor:
    """Provides AI-enhanced investment recommendations"""
    
    @staticmethod
    def get_personalized_advice(financial_snapshot: dict, risk_profile: str, goal: str):
        """Get AI-generated investment advice based on user's financial situation"""
        prompt = f"""Act as a certified financial planner. Analyze this financial situation:
        
        Monthly Income: ${financial_snapshot['monthly_income']:,.2f}
        Monthly Expenses: ${financial_snapshot['monthly_expenses']:,.2f}
        Available for Investing: ${financial_snapshot['savings_capacity']:,.2f}
        Risk Tolerance: {risk_profile}
        Primary Goal: {goal}
        
        Provide:
        1. Specific portfolio allocation (percentages)
        2. 3 recommended investment products
        3. Key considerations
        4. Common mistakes to avoid
        
        Format as markdown with clear sections."""
        
        return ASIFinancialAdvisor.get_advice(prompt)

# --- Main Tab Implementation ---
def savings_and_investing_tab():
    """Complete Savings & Investing dashboard tab"""
    st.header("💰 AI-Powered Savings & Investing")
    
    # Get financial snapshot
    snapshot = SavingsPlanner.get_financial_snapshot()
    
    # Tab layout
    tab1, tab2, tab3 = st.tabs(["Savings Planner", "Investment Advisor", "Financial Health"])
    
    with tab1:
        st.subheader("Personalized Savings Plan")
        
        # Financial overview
        col1, col2, col3 = st.columns(3)
        col1.metric("Monthly Income", f"${snapshot['monthly_income']:,.2f}")
        col2.metric("Monthly Expenses", f"${snapshot['monthly_expenses']:,.2f}")
        col3.metric("Available for Savings", 
                   f"${snapshot['savings_capacity']:,.2f}",
                   delta=f"{(snapshot['savings_capacity']/snapshot['monthly_income']*100 if snapshot['monthly_income'] > 0 else 0):.1f}%")
        
        # Savings goal form
        with st.form("savings_goal"):
            goal_name = st.text_input("Goal Name (e.g. 'House Downpayment')")
            goal_amount = st.number_input("Target Amount ($)", min_value=100, value=10000)
            years = st.slider("Timeframe (years)", 1, 30, 5)
            risk_profile = st.selectbox("Risk Tolerance", 
                                      ["Conservative", "Moderate", "Aggressive"])
            
            if st.form_submit_button("Generate Plan"):
                with st.spinner("Creating optimized savings plan..."):
                    # Calculate suggested monthly contribution
                    suggested = min(
                        goal_amount / (years * 12),  # Naive calculation
                        snapshot['savings_capacity'] * 0.8  # 80% of available savings
                    )
                    
                    # Generate projection
                    projection = SavingsPlanner.generate_projection(
                        goal_amount=goal_amount,
                        current_savings=0,
                        monthly_contribution=suggested,
                        years=years,
                        risk_profile=risk_profile
                    )
                    
                    # Display results
                    st.success(f"**Suggested Monthly Contribution:** ${suggested:,.2f}")
                    
                    # Interactive chart
                    fig = px.line(projection, x="Date", y="Balance", 
                                 title=f"'{goal_name}' Projection")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Get AI advice
                    advice = ASIFinancialAdvisor.get_advice(
                        f"Suggest 3 ways to achieve a {goal_name} goal of ${goal_amount} "
                        f"in {years} years with ${suggested:,.2f} monthly contributions "
                        f"and {risk_profile} risk tolerance."
                    )
                    with st.expander("AI Optimization Tips"):
                        st.markdown(advice)
    
    with tab2:
        st.subheader("AI Investment Advisor")
        
        with st.form("investment_profile"):
            col1, col2 = st.columns(2)
            with col1:
                risk_profile = st.selectbox("Your Risk Tolerance", 
                                          ["Conservative", "Moderate", "Aggressive"],
                                          index=1)
                investment_goal = st.selectbox("Primary Goal",
                                             ["Retirement", "Wealth Building", "Education", "Other"])
            with col2:
                initial_amount = st.number_input("Initial Investment ($)", 
                                              min_value=100, value=5000)
                recurring_amount = st.number_input("Monthly Additional Investment ($)",
                                                min_value=0, value=500)
            
            if st.form_submit_button("Get Personalized Advice"):
                with st.spinner("Generating AI-powered recommendations..."):
                    # Get AI recommendations
                    advice = InvestmentAdvisor.get_personalized_advice(
                        financial_snapshot=snapshot,
                        risk_profile=risk_profile,
                        goal=investment_goal
                    )
                    
                    # Display results
                    st.markdown("### 📈 Your Custom Investment Plan")
                    st.markdown(advice)
                    
                    # Generate sample portfolio
                    st.plotly_chart(
                        px.pie(values=[40, 30, 20, 10], 
                              names=["ETFs", "Stocks", "Bonds", "Alternatives"],
                              title="Sample Portfolio Allocation"),
                        use_container_width=True
                    )
    
    with tab3:
        st.subheader("Financial Health Dashboard")
        
        # Calculate key metrics
        emergency_fund_months = st.slider("Recommended Emergency Fund (months)", 3, 12, 6)
        emergency_fund_needed = snapshot['monthly_expenses'] * emergency_fund_months
        
        # Metrics grid
        col1, col2 = st.columns(2)
        col1.metric("Savings Rate", 
                   f"{(snapshot['savings_capacity']/snapshot['monthly_income']*100):.1f}%",
                   "Goal: >20%")
        col2.metric("Emergency Fund Coverage", 
                   f"${emergency_fund_needed:,.2f}",
                   f"{emergency_fund_months} months")
        
        # AI Financial Health Assessment
        if st.button("Get Financial Health Checkup"):
            with st.spinner("Analyzing your financial situation..."):
                analysis = ASIFinancialAdvisor.get_advice(
                    f"Analyze this financial profile and provide specific recommendations:\n"
                    f"Income: ${snapshot['monthly_income']:,.2f}/month\n"
                    f"Expenses: ${snapshot['monthly_expenses']:,.2f}/month\n"
                    f"Savings Capacity: ${snapshot['savings_capacity']:,.2f}/month\n\n"
                    "Provide:\n"
                    "1. 3 strengths\n"
                    "2. 3 areas for improvement\n"
                    "3. Specific action items\n"
                    "Format as markdown with headings."
                )
                with st.expander("🔍 AI Financial Health Report"):
                    st.markdown(analysis)
