import os
import streamlit as st
import requests
import json
from datetime import datetime
from utils.snowflake_helpers import TransactionManager
from utils.income_manager import IncomeManager
import dotenv

dotenv.load_dotenv()

class TaxComplianceAssistant:
    """Handles all tax compliance queries using ASI API"""
    
    @staticmethod
    def ask_compliance_question(question: str) -> str:
        """Call ASI API for compliance and tax advice"""
        HEADERS = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {st.secrets["ASI_API_KEY"]}'
        }
        
        URL = "https://api.asi1.ai/v1/chat/completions"
        
        # Enhanced prompt for tax/compliance context
        prompt = f"""You are a tax and financial compliance expert specializing in GDPR and fintech regulations. 
    Provide detailed, accurate advice for the following question. Cite relevant regulations when possible.

    Question: {question}

    Answer in clear, actionable terms suitable for a financial application user. 
    If the question is ambiguous, ask clarifying questions."""

        payload = json.dumps({
            "model": "asi1-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,  # Lower for more factual responses
            "max_tokens": 1000
        })
        
        response = requests.post(URL, headers=HEADERS, data=payload)
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]

class TaxOptimizationDashboard:
    """Handles the tax optimization calculations and visualizations"""
    
    @staticmethod
    def display_annual_tax_summary(report: dict):
        """Display key tax metrics"""
        with st.expander("📊 Annual Tax Summary"):
            if report:
                st.metric("Total Income", f"${report['income']['total']:,.2f}")
                st.metric("Total Expenses", f"${report['expenses']['total']:,.2f}")
                st.metric("Taxable Income", f"${report['income']['total'] - report['expenses']['total']:,.2f}")
                
                # Simple tax estimate (example rates)
                taxable_income = report['income']['total'] - report['expenses']['total']
                tax_estimate = taxable_income * 0.25  # Example 25% rate
                st.metric("Estimated Tax Liability", f"${tax_estimate:,.2f}")
                
                # Important notice
                st.warning("""
                **Important Notice**: 
                - These are estimates only
                - Actual tax liability may vary based on jurisdiction
                - Consult a qualified tax professional for official advice
                """)
            else:
                st.warning("No financial data available for tax analysis")
    
    @staticmethod
    def display_tax_deductible_expenses(report: dict):
        """Show expense categories with tax benefits"""
        with st.expander("💡 Tax-Deductible Expenses"):
            if report and report['expenses']['category_breakdown']:
                deductible_categories = {
                    'Office': "100% deductible for home office",
                    'Software': "100% deductible if used for business",
                    'Travel': "50-100% deductible depending on purpose",
                    'Meals': "50% deductible for business meals"
                }
                
                for category, amount in report['expenses']['category_breakdown'].items():
                    if category in deductible_categories:
                        st.write(f"**{category}**: ${amount:,.2f} - {deductible_categories[category]}")
                
                # Important notice
                st.info("""
                **Note**: 
                - Deductibility rules vary by country
                - Some expenses may require special documentation
                - Maintain proper receipts for all deductions
                """)
            else:
                st.info("No tax-deductible expenses identified")

class ComplianceChatInterface:
    """Manages the compliance Q&A interface"""
    
    def __init__(self):
        if 'tax_chat_history' not in st.session_state:
            st.session_state.tax_chat_history = []
    
    def display_common_questions(self):
        """Show pre-defined compliance questions"""
        common_questions = [
            "What are the GDPR requirements for storing financial data?",
            "How should I handle international transactions for tax purposes?",
            "What receipts do I need to keep for tax deductions?",
            "How long should I retain financial records under EU law?"
        ]
        
        selected_question = st.selectbox(
            "Common compliance questions:",
            ["Select a question..."] + common_questions
        )
        return selected_question
    
    def process_user_question(self, question: str):
        """Handle user questions and display responses"""
        if st.button("Ask Compliance Expert") and question:
            with st.spinner("Consulting compliance experts..."):
                try:
                    response = TaxComplianceAssistant.ask_compliance_question(question)
                    
                    # Add to chat history
                    st.session_state.tax_chat_history.append({
                        "question": question,
                        "response": response,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                except Exception as e:
                    st.error(f"Failed to get compliance advice: {str(e)}")
    
    def display_chat_history(self):
        """Show previous Q&A"""
        if st.session_state.tax_chat_history:
            st.subheader("Previous Q&A")
            for i, chat in enumerate(reversed(st.session_state.tax_chat_history)):
                with st.expander(f"Q: {chat['question']} ({chat['timestamp']})"):
                    st.write(chat['response'])
                    
                    # Disclaimer for all responses
                    if i == 0:  # Only show once
                        st.caption("""
                        **Disclaimer**: These responses are AI-generated suggestions only. 
                        For legally binding advice, please consult a qualified professional.
                        """)

def tax_optimization_tab():
    """
    Main entry point for the Tax Optimization & Compliance dashboard tab.
    
    This function:
    - Displays important legal disclaimers
    - Shows tax insights and recommendations
    - Provides a compliance Q&A assistant
    - Manages all layout and component coordination
    
    Layout:
    - Left column: Tax calculations and visualizations
    - Right column: Compliance question answering interface
    
    Returns:
        None (renders Streamlit components directly)
        
    Side Effects:
        - Modifies Streamlit session state for chat history
        - Makes API calls to ASI for compliance advice
    """
    st.header("🧾 Tax Optimization & Compliance")
    
    # Important global notice
    st.warning("""
    **Important Legal Disclaimer**:
    - This tool provides general information only, not professional tax advice
    - Tax laws vary by jurisdiction and change frequently
    - Always verify information with official sources or qualified professionals
    - The developers assume no liability for decisions made based on this tool's outputs
    """)
    
    # Rest of your existing implementation...
    
    # Create two columns for layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Tax Insights & Recommendations")
        
        # Get financial data for the year
        report = TransactionManager.get_combined_financial_report('year')
        
        # Display tax optimization components
        TaxOptimizationDashboard.display_annual_tax_summary(report)
        TaxOptimizationDashboard.display_tax_deductible_expenses(report)
    
    with col2:
        st.subheader("Compliance Assistant")
        
        # Initialize and display chat interface
        chat_interface = ComplianceChatInterface()
        
        # User can select common questions or ask their own
        selected_question = chat_interface.display_common_questions()
        user_question = st.text_input("Or ask your own question:")
        
        question_to_ask = user_question if user_question else (
            selected_question if selected_question != "Select a question..." else None
        )
        
        # Process and display questions
        chat_interface.process_user_question(question_to_ask)
        chat_interface.display_chat_history()