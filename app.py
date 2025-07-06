import json
import streamlit as st
from utils.snowflake_conn import init_db
from utils.snowflake_helpers import TransactionManager
from utils.groq_client import GroqClient
import os
import tempfile
from datetime import datetime
import pandas as pd


st.set_page_config(layout="wide", page_title="AI Accountant", page_icon="🧾")
# Initialize clients
groq_client = GroqClient()
transaction_manager = TransactionManager()

# Initialize database (run once)
@st.cache_resource
def initialize_database():
    try:
        init_db()
        return True
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        return False

if not initialize_database():
    st.stop()
    
if 'form_submitted' not in st.session_state:
    st.session_state.form_submitted = False
st.title("📄 Smart Receipt Processor")

# Tab interface
tab1, tab2 = st.tabs(["Upload Receipt", "View Transactions"])

with tab1:
    st.header("🔍 Process New Receipt")
    
    # Unified file uploader
    uploaded_file = st.file_uploader(
        "Upload Receipt (PDF, Image, or Text)",
        type=["pdf", "jpg", "jpeg", "png", "txt"],
        help="Upload a receipt in any format"
    )
    
    # Text fallback
    receipt_text = st.text_area(
        "Or paste receipt text directly",
        height=200,
        placeholder="Paste receipt text here..."
    )
    
    if st.button("Process Receipt", type="primary"):
        if uploaded_file or receipt_text:
            with st.spinner("🧠 Analyzing receipt content..."):
                try:
                    file_bytes = None
                    file_type = None
                    extracted_text = receipt_text
                    
                    if uploaded_file:
                        file_bytes = uploaded_file.read()
                        file_ext = os.path.splitext(uploaded_file.name)[1].lower()[1:]  # Get extension without dot
                        
                        if file_ext == 'pdf':
                            file_type = 'pdf'
                            extracted_text = groq_client._extract_text_from_pdf(file_bytes)
                        elif file_ext in ['jpg', 'jpeg', 'png']:
                            file_type = file_ext
                            extracted_text = groq_client._extract_text_from_image(file_bytes)
                        elif file_ext == 'txt':
                            extracted_text = file_bytes.decode('utf-8')
                    
                    # Process with Groq
                    result = groq_client.process_receipt(
                        file_bytes=file_bytes,
                        text=extracted_text,
                        file_type=file_type
                    )
                    
                    # Store in session state
                    st.session_state.receipt_data = result
                    st.session_state.analysis_time = datetime.now()
                    
                    # Display results
                    st.subheader("✅ Analysis Results")
                    with st.container():
                        cols = st.columns(2)
                        
                        with cols[0]:
                            st.metric(
                                "Total Amount", 
                                f"${result['amount']['value']:.2f}", 
                                f"Confidence: {result['amount']['confidence']*100:.1f}%"
                            )
                            st.metric(
                                "Merchant",
                                result['merchant']['value'],
                                f"Confidence: {result['merchant']['confidence']*100:.1f}%"
                            )
                        
                        with cols[1]:
                            st.metric(
                                "Category",
                                result['category']['value'],
                                f"Confidence: {result['category']['confidence']*100:.1f}%"
                            )
                            st.metric(
                                "Date",
                                result['date']['value'] or 'Not detected',
                                f"Confidence: {result['date']['confidence']*100:.1f}%"
                            )
                    
                    # Show line items if available
                    if result.get('line_items'):
                        st.subheader("📝 Line Items")
                        line_items_df = pd.DataFrame(result['line_items'])
                        st.dataframe(
                            line_items_df,
                            column_config={
                                "amount": st.column_config.NumberColumn(
                                    "Amount",
                                    format="$%.2f"
                                )
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                    
                except Exception as e:
                    st.error(f"❌ Error processing receipt: {str(e)}")
        else:
            st.warning("Please upload a file or paste receipt text")

    # Save to database section
    # Save to database section
if 'receipt_data' in st.session_state:
    # If transaction hasn't been submitted yet
    if not st.session_state.form_submitted:
        with st.form("save_transaction"):
            st.subheader("💾 Save to Database")

            amount = st.number_input(
                "Amount",
                value=float(st.session_state.receipt_data['amount']['value']),
                min_value=0.0,
                step=0.01,
                format="%.2f"
            )

            merchant = st.text_input(
                "Merchant",
                value=st.session_state.receipt_data['merchant']['value']
            )

            category = st.selectbox(
                "Category",
                options=["Meals", "Travel", "Office", "Software", "Rent", "Utilities", "Other"],
                index=["Meals", "Travel", "Office", "Software", "Rent", "Utilities", "Other"].index(
                    st.session_state.receipt_data['category']['value']
                )
            )

            date = st.date_input(
                "Date",
                value=datetime.strptime(
                    st.session_state.receipt_data['date']['value'], '%Y-%m-%d'
                ).date() if st.session_state.receipt_data['date']['value'] else datetime.now().date()
            )

            submitted = st.form_submit_button("Save Transaction", type="primary")

            if submitted:
                try:
                    receipt_data = st.session_state.receipt_data.copy()
                    receipt_data['amount']['value'] = amount
                    receipt_data['merchant']['value'] = merchant
                    receipt_data['category']['value'] = category
                    receipt_data['date']['value'] = date.strftime('%Y-%m-%d')

                    transaction_id = transaction_manager.log_receipt(receipt_data)

                    st.session_state.form_submitted = True
                    st.session_state.last_transaction_id = transaction_id
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error saving transaction: {str(e)}")
    else:
        # ✅ After form is submitted and rerun
        st.success(f"✅ Transaction {st.session_state.last_transaction_id} saved successfully!")

        if st.button("➕ New Transaction"):
            del st.session_state.receipt_data
            st.session_state.form_submitted = False
            del st.session_state.last_transaction_id
            st.rerun()

with tab2:
    st.header("Transaction History")
    
    try:
        df = transaction_manager.get_recent_transactions(100)
        
        if not df.empty:
            # Display the transactions table with your existing formatting
            st.dataframe(
                df,
                column_config={
                    "date": st.column_config.DateColumn("Date"),
                    "amount": st.column_config.NumberColumn(
                        "Amount",
                        format="$%.2f"
                    ),
                    "amount_confidence": st.column_config.ProgressColumn(
                        "Amount Confidence",
                        format="%.0f%%",
                        min_value=0,
                        max_value=1
                    ),
                    "quality_score": st.column_config.ProgressColumn(
                        "Quality Score",
                        format="%.0f%%",
                        min_value=0,
                        max_value=1
                    )
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Add row selection using a select box styled to look like clickable rows
            st.markdown("""
            <style>
                div[data-baseweb="select"] {
                    margin-top: -10px;
                    margin-bottom: 10px;
                }
                div[data-baseweb="select"] > div {
                    border-radius: 8px;
                    border: 1px solid #e6e6e6;
                    font-size: 16px;
                    
                    padding: 12px 18px;
                    min-height: 45px; 
                    overflow: visible;
                }
            </style>
            """, unsafe_allow_html=True)
            
            selected_index = st.selectbox(
                "Select a transaction to view details:",
                options=df.index,
                format_func=lambda x: f"{df.loc[x, 'merchant']} - ${df.loc[x, 'amount']:.2f} - {df.loc[x, 'date'].strftime('%Y-%m-%d')}",
                label_visibility="collapsed"
            )
            
            # Show analysis for selected transaction
            if selected_index is not None:
                selected_trans = df.loc[selected_index]
                
                # Parse metadata if it exists
                metadata = selected_trans.get('metadata', {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                
                analysis_data = metadata.get('raw_data', {})
                
                # Display analysis in the same format as the upload tab
                st.subheader("🔍 Transaction Analysis")
                with st.container():
                    cols = st.columns(2)
                    
                    with cols[0]:
                        st.metric(
                            "Total Amount", 
                            f"${analysis_data.get('amount', {}).get('value', selected_trans['amount']):.2f}", 
                            f"Confidence: {analysis_data.get('amount', {}).get('confidence', selected_trans.get('amount_confidence', 1))*100:.1f}%"
                        )
                        st.metric(
                            "Merchant",
                            analysis_data.get('merchant', {}).get('value', selected_trans['merchant']),
                            f"Confidence: {analysis_data.get('merchant', {}).get('confidence', selected_trans.get('merchant_confidence', 1))*100:.1f}%"
                        )
                    
                    with cols[1]:
                        st.metric(
                            "Category",
                            analysis_data.get('category', {}).get('value', selected_trans['category']),
                            f"Confidence: {analysis_data.get('category', {}).get('confidence', selected_trans.get('category_confidence', 1))*100:.1f}%"
                        )
                        st.metric(
                            "Date",
                            analysis_data.get('date', {}).get('value', selected_trans['date'].strftime('%Y-%m-%d')),
                            f"Confidence: {analysis_data.get('date', {}).get('confidence', selected_trans.get('date_confidence', 1))*100:.1f}%"
                        )
                
                # Show line items if available
                if analysis_data and analysis_data.get('line_items'):
                    st.subheader("📝 Line Items")
                    line_items_df = pd.DataFrame(analysis_data['line_items'])
                    st.dataframe(
                        line_items_df,
                        column_config={
                            "amount": st.column_config.NumberColumn(
                                "Amount",
                                format="$%.2f"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                
                # Show quality metrics from the database
                st.subheader("Quality Metrics")
                qual_cols = st.columns(3)
                with qual_cols[0]:
                    st.metric("Amount Confidence", f"{selected_trans.get('amount_confidence', 0)*100:.1f}%")
                with qual_cols[1]:
                    st.metric("Category Confidence", f"{selected_trans.get('category_confidence', 0)*100:.1f}%")
                with qual_cols[2]:
                    st.metric("Overall Quality", f"{selected_trans.get('quality_score', 0)*100:.1f}%")
                
                
                    
        else:
            st.info("No transactions found")
    except Exception as e:
        st.error(f"Failed to load transactions: {str(e)}")