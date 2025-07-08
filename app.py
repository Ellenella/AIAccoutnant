import streamlit as st
from dashboard.financial_report import generate_financial_dashboard
from dashboard.savingandinvest import savings_and_investing_tab
from dashboard.taxandcomp import tax_optimization_tab
from utils.income_manager import IncomeManager
from utils.snowflake_conn import init_db
from utils.snowflake_helpers import TransactionManager
from utils.groq_client import GroqClient
import os
from datetime import datetime
import pandas as pd
import numpy as np



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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Upload Receipt", "Income Management","View Income and Expense", "Financial Reports", "Tax & Compliance", "Savings & Investing"])

with tab1:
    # Create two columns for layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("🔍 Single Receipt Processing")
        
        # Unified file uploader for single file
        uploaded_file = st.file_uploader(
            "Upload Receipt (PDF, Image, or Text)",
            type=["pdf", "jpg", "jpeg", "png", "txt"],
            help="Upload a receipt in any format",
            key="single_upload"
        )
        
        # Text fallback
        receipt_text = st.text_area(
            "Or paste receipt text directly",
            height=200,
            placeholder="Paste receipt text here...",
            key="single_text"
        )
        
        if st.button("Process Receipt", type="primary", key="process_single"):
            if uploaded_file or receipt_text:
                with st.spinner("🧠 Analyzing receipt content..."):
                    try:
                        file_bytes = None
                        file_type = None
                        extracted_text = receipt_text
                        
                        if uploaded_file:
                            file_bytes = uploaded_file.read()
                            file_ext = os.path.splitext(uploaded_file.name)[1].lower()[1:]
                            
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
                        st.session_state.bulk_processing = False
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error processing receipt: {str(e)}")
            else:
                st.warning("Please upload a file or paste receipt text")

    with col2:
        st.header("⚡ Bulk Receipt Processing")
        
        # Multi-file uploader
        bulk_files = st.file_uploader(
            "Upload Multiple Receipts",
            type=["pdf", "jpg", "jpeg", "png", "txt"],
            accept_multiple_files=True,
            help="Upload multiple receipts at once",
            key="bulk_upload"
        )
        
        if st.button("Process Multiple Receipts", type="primary", key="process_bulk"):
            if bulk_files:
                with st.spinner(f"🧠 Analyzing {len(bulk_files)} receipts..."):
                    try:
                        # Process files in bulk
                        files_to_process = []
                        for uploaded_file in bulk_files:
                            file_bytes = uploaded_file.read()
                            file_ext = os.path.splitext(uploaded_file.name)[1].lower()[1:]
                            files_to_process.append((file_bytes, file_ext))
                            
                        results = groq_client.process_bulk_receipts(files=files_to_process)
                        
                        # Store in session state
                        st.session_state.bulk_results = results
                        st.session_state.bulk_processing = True
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Bulk processing failed: {str(e)}")
            else:
                st.warning("Please upload at least one file")

    # Display results based on processing mode
    if st.session_state.get('bulk_processing', False) and 'bulk_results' in st.session_state:
        st.subheader("📊 Bulk Processing Results")
        
        # Create summary table
        summary_data = []
        for i, result in enumerate(st.session_state.bulk_results):
            summary_data.append({
                "#": i+1,
                "Merchant": result['merchant']['value'],
                "Amount": f"${result['amount']['value']:.2f}",
                "Confidence": f"{result['amount']['confidence']*100:.1f}%",
                "Category": result['category']['value'],
                "Date": result['date']['value'] or "N/A"
            })
        
        st.dataframe(
            pd.DataFrame(summary_data),
            column_config={
                "#": st.column_config.NumberColumn(width="small"),
                "Amount": st.column_config.TextColumn(width="small")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Bulk save options
        with st.expander("💾 Save All Transactions"):
            if st.button("Save All to Database", key="save_all_bulk"):
                with st.spinner(f"Saving {len(st.session_state.bulk_results)} transactions..."):
                    try:
                        transaction_ids = transaction_manager.log_bulk_receipts(st.session_state.bulk_results)

                        st.success(f"✅ Successfully saved {len(transaction_ids)} transactions!")
                        del st.session_state.bulk_results
                        del st.session_state.bulk_processing
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to save transactions: {str(e)}")
            
            # Option to edit individual transactions before saving
            if st.checkbox("Review individual transactions before saving"):
                for i, result in enumerate(st.session_state.bulk_results):
                    with st.container(border=True):
                        cols = st.columns([1, 3])
                        with cols[0]:
                            st.markdown(f"**Receipt #{i+1}**")
                            st.metric("Amount", f"${result['amount']['value']:.2f}")
                        with cols[1]:
                            with st.form(f"edit_receipt_{i}"):
                                merchant = st.text_input(
                                    "Merchant",
                                    value=result['merchant']['value'],
                                    key=f"merchant_{i}"
                                )
                                category = st.selectbox(
                                    "Category",
                                    options=["Meals", "Travel", "Office", "Software", "Rent", "Utilities", "Other"],
                                    index=["Meals", "Travel", "Office", "Software", "Rent", "Utilities", "Other"].index(
                                        result['category']['value']
                                    ),
                                    key=f"category_{i}"
                                )
                                date = st.date_input(
                                    "Date",
                                    value=datetime.strptime(
                                        result['date']['value'], '%Y-%m-%d'
                                    ).date() if result['date']['value'] else datetime.now().date(),
                                    key=f"date_{i}"
                                )
                                
                                if st.form_submit_button(f"Update Receipt #{i+1}"):
                                    st.session_state.bulk_results[i]['merchant']['value'] = merchant
                                    st.session_state.bulk_results[i]['category']['value'] = category
                                    st.session_state.bulk_results[i]['date']['value'] = date.strftime('%Y-%m-%d')
                                    st.success(f"Receipt #{i+1} updated!")
                                    st.rerun()

    elif 'receipt_data' in st.session_state and not st.session_state.get('bulk_processing', True):
        # Single receipt processing results (existing code)
        st.subheader("✅ Analysis Results")
        with st.container():
            cols = st.columns(2)
            
            with cols[0]:
                st.metric(
                    "Total Amount", 
                    f"${st.session_state.receipt_data['amount']['value']:.2f}", 
                    f"Confidence: {st.session_state.receipt_data['amount']['confidence']*100:.1f}%"
                )
                st.metric(
                    "Merchant",
                    st.session_state.receipt_data['merchant']['value'],
                    f"Confidence: {st.session_state.receipt_data['merchant']['confidence']*100:.1f}%"
                )
            
            with cols[1]:
                st.metric(
                    "Category",
                    st.session_state.receipt_data['category']['value'],
                    f"Confidence: {st.session_state.receipt_data['category']['confidence']*100:.1f}%"
                )
                st.metric(
                    "Date",
                    st.session_state.receipt_data['date']['value'] or 'Not detected',
                    f"Confidence: {st.session_state.receipt_data['date']['confidence']*100:.1f}%"
                )
        
        if st.session_state.receipt_data.get('line_items'):
            st.subheader("📝 Line Items")
            line_items_df = pd.DataFrame(st.session_state.receipt_data['line_items'])
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

        # Save to database section (existing code)
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
            st.success(f"✅ Transaction {st.session_state.last_transaction_id} saved successfully!")
            if st.button("➕ New Transaction"):
                del st.session_state.receipt_data
                st.session_state.form_submitted = False
                del st.session_state.last_transaction_id
                st.rerun()
with tab2:
    st.header("💰 Income Management")
    
    # Income entry form
    with st.form("income_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            amount = st.number_input("Amount", min_value=0.01, step=0.01, format="%.2f")
            source = st.text_input("Income Source", placeholder="Employer, Client, etc.")
            payment_method = st.selectbox(
                "Payment Method",
                options=["Direct Deposit", "Check", "Cash", "Bank Transfer", "Other"]
            )
        
        with col2:
            date = st.date_input("Date Received", value=datetime.now())
            category = st.selectbox(
                "Income Category",
                options=["Salary", "Freelance", "Investment", "Gift", "Other"]
            )
            tags = st.multiselect(
                "Tags",
                options=["Recurring", "Bonus", "Taxable", "Non-Taxable"]
            )
        
        description = st.text_area("Description/Notes")
        
        submitted = st.form_submit_button("Record Income", type="primary")
        if submitted:
            try:
                income_data = {
                    "amount": amount,
                    "source": source,
                    "date": date,
                    "payment_method": payment_method,
                    "category": category,
                    "tags": tags,
                    "description": description
                }
                transaction_id = IncomeManager.log_income(income_data)
                st.success(f"Income recorded successfully! Transaction ID: {transaction_id}")
            except Exception as e:
                st.error(f"Error recording income: {str(e)}")
    
    # Income history and reports
    st.subheader("Income History")
    
    income_report = IncomeManager.get_income_report()
    if income_report:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Income", f"${income_report['total_income']:,.2f}")
            st.metric("Average Income", f"${income_report['average_income']:,.2f}")
        
        with col2:
            st.write("**Top Income Sources**")
            for source, amount in income_report['top_sources'].items():
                st.write(f"- {source}: ${amount:,.2f}")
        
        st.subheader("Monthly Income Trend")
        monthly_df = pd.DataFrame.from_dict(
            income_report['income_by_month'],
            orient='index',
            columns=['Amount']
        )
        st.line_chart(monthly_df)
    else:
        st.info("No income records found")
        
with tab3:
    st.header("Expense and Income History")
    
    view_type = st.radio(
        "View:",
        options=["All", "Expenses Only", "Income Only"],
        horizontal=True,
        key="transaction_view_type"
    )
    
    try:
        # Initialize empty DataFrames
        expenses_df = pd.DataFrame()
        income_df = pd.DataFrame()
        combined_df = pd.DataFrame()

        # Get expenses data with duplicate column handling
        try:
            expenses_data = transaction_manager.get_recent_transactions(200)
            if isinstance(expenses_data, pd.DataFrame) and not expenses_data.empty:
                expenses_df = pd.DataFrame(expenses_data)
                # Clean column names
                expenses_df.columns = [str(col).lower() for col in expenses_df.columns]
                expenses_df = expenses_df.loc[:, ~expenses_df.columns.duplicated()]
                
                # Prepare expense-specific columns
                if not expenses_df.empty:
                    expenses_df['type'] = 'expense'
                    if 'amount' in expenses_df.columns:
                        expenses_df['amount_display'] = np.abs(expenses_df['amount'])
                    if 'date' in expenses_df.columns:
                        expenses_df['date'] = pd.to_datetime(expenses_df['date'])
        except Exception as e:
            st.error(f"Error loading expenses: {str(e)}")

        # Get income data with duplicate column handling
        try:
            income_df = IncomeManager.get_income_for_transactions_view(200)
        except Exception as e:
            st.error(f"Error loading income: {str(e)}")
            income_df = pd.DataFrame()

        # Combine data based on view type
        dfs_to_combine = []
        if view_type in ["All", "Expenses Only"] and not expenses_df.empty:
            dfs_to_combine.append(expenses_df)
        if view_type in ["All", "Income Only"] and not income_df.empty:
            dfs_to_combine.append(income_df)

        if dfs_to_combine:
            try:
                combined_df = pd.concat(dfs_to_combine, ignore_index=True)
                if not combined_df.empty and 'date' in combined_df.columns:
                    combined_df = combined_df.sort_values('date', ascending=False)
            except Exception as e:
                st.error(f"Error combining data: {str(e)}")

        if not combined_df.empty:
            # Display the transactions table
            display_columns = ['date', 'merchant', 'amount_display', 'type', 'category']
            display_columns = [col for col in display_columns if col in combined_df.columns]
            
            st.dataframe(
                combined_df[display_columns].style.applymap(
                    lambda x: 'color: green' if x == 'income' else 'color: red', 
                    subset=['type']
                ),
                column_config={
                    "date": st.column_config.DateColumn("Date"),
                    "merchant": "Merchant/Source",
                    "amount_display": st.column_config.NumberColumn(
                        "Amount",
                        format="$%.2f"
                    ),
                    "type": "Type",
                    "category": "Category"
                },
                hide_index=True,
                use_container_width=True,
                height=600
            )

            # [Rest of your transaction details and summary view...]
            # Keep your existing code for transaction details and summary statistics

        else:
            st.info("No transactions found for the selected view")
            
    except Exception as e:
        st.error(f"Failed to load transactions: {str(e)}")
with tab4:
    st.header("📊 Comprehensive Financial Reports")   
        # Time period selector
    time_period = st.selectbox(
            "Select Time Period",
            ["Week", "Month", "Quarter", "Year"],
            index=1
        )
    generate_financial_dashboard(time_period)
with tab5:
    tax_optimization_tab()

with tab6:
    savings_and_investing_tab()