import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils.snowflake_helpers import TransactionManager, IncomeManager


def generate_financial_dashboard(time_period="month", start_date=None, end_date=None):
    st.markdown("""
    <style>
        .metric-card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .positive {
            color: #28a745;
        }
        .negative {
            color: #dc3545;
        }
        .header {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 15px;
        }
        .subheader {
            font-size: 1.2rem;
            font-weight: 500;
            margin-bottom: 10px;
        }
        .kpi-card {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #4e73df;
        }
        .kpi-title {
            font-size: 1rem;
            color: #5a5c69;
            margin-bottom: 5px;
        }
        .kpi-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #4e73df;
        }
        .kpi-change {
            font-size: 0.9rem;
            font-weight: 400;
        }
    </style>
    """, unsafe_allow_html=True)

    if time_period == "Custom":
        col1, col2 = st.sidebar.columns(2)
        start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
        end_date = col2.date_input("End Date", datetime.now())
    else:
        end_date = datetime.now()
        if time_period == "Week":
            start_date = end_date - timedelta(weeks=1)
        elif time_period == "Month":
            start_date = end_date - timedelta(days=30)
        elif time_period == "Quarter":
            start_date = end_date - timedelta(days=90)
        else:  # Year
            start_date = end_date - timedelta(days=365)

    # Get financial data for current and previous period
    current_report = TransactionManager.get_combined_financial_report(time_period.lower())

    # Calculate previous period for comparison
    prev_start_date = start_date - (end_date - start_date)
    prev_report = TransactionManager.get_combined_financial_report(
        custom_start=prev_start_date,
        custom_end=start_date
    )

    # Function to calculate percentage change
    def calculate_change(current, previous):
        if previous == 0:
            return 0
        return ((current - previous) / previous) * 100

    # KPI Metrics
    st.markdown("## Key Performance Indicators")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        current_income = current_report["income"]["total"]
        prev_income = prev_report["income"]["total"]
        change = calculate_change(current_income, prev_income)
        change_color = "positive" if change >= 0 else "negative"
        change_icon = "↑" if change >= 0 else "↓"
        
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Total Income</div>
            <div class="kpi-value">${current_income:,.2f}</div>
            <div class="kpi-change {change_color}">
                {change_icon} {abs(change):.1f}% vs previous period
            </div>
        </div>
        """, unsafe_allow_html=True)

    with kpi2:
        current_expenses = current_report["expenses"]["total"]
        prev_expenses = prev_report["expenses"]["total"]
        change = calculate_change(current_expenses, prev_expenses)
        change_color = "negative" if change >= 0 else "positive"  # Inverse for expenses
        change_icon = "↑" if change >= 0 else "↓"
        
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Total Expenses</div>
            <div class="kpi-value">${current_expenses:,.2f}</div>
            <div class="kpi-change {change_color}">
                {change_icon} {abs(change):.1f}% vs previous period
            </div>
        </div>
        """, unsafe_allow_html=True)

    with kpi3:
        current_net = current_report["net_flow"]["total"]  # Get the numeric value from the dict
        prev_net = prev_report["net_flow"]["total"] 
        change = calculate_change(current_net, prev_net)
        change_color = "positive" if change >= 0 else "negative"
        change_icon = "↑" if change >= 0 else "↓"
        
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Net Cash Flow</div>
            <div class="kpi-value {'positive' if current_net >= 0 else 'negative'}">${current_net:,.2f}</div>
            <div class="kpi-change {change_color}">
                {change_icon} {abs(change):.1f}% vs previous period
            </div>
        </div>
        """, unsafe_allow_html=True)

    with kpi4:
        current_savings = (current_report["net_flow"]["total"] / current_report["income"]["total"]) * 100 if current_report["income"]["total"] > 0 else 0
        prev_savings = (prev_report["net_flow"]["total"] / prev_report["income"]["total"]) * 100 if prev_report["income"]["total"] > 0 else 0
        change = calculate_change(current_savings, prev_savings)
        change_color = "positive" if change >= 0 else "negative"
        change_icon = "↑" if change >= 0 else "↓"
        
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Savings Rate</div>
            <div class="kpi-value {'positive' if current_savings >= 0 else 'negative'}">{current_savings:.1f}%</div>
            <div class="kpi-change {change_color}">
                {change_icon} {abs(change):.1f}% vs previous period
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Second Row of KPIs
    kpi5, kpi6, kpi7, kpi8 = st.columns(4)

    with kpi5:
        # Expense to Income Ratio
        if current_report["income"]["total"] > 0:
            ratio = (current_report["expenses"]["total"] / current_report["income"]["total"]) * 100
            prev_ratio = (prev_report["expenses"]["total"] / prev_report["income"]["total"]) * 100 if prev_report["income"]["total"] > 0 else 0
            change = calculate_change(ratio, prev_ratio)
            change_color = "negative" if change >= 0 else "positive"  # Lower ratio is better
            change_icon = "↑" if change >= 0 else "↓"
            
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Expense/Income Ratio</div>
                <div class="kpi-value">{ratio:.1f}%</div>
                <div class="kpi-change {change_color}">
                    {change_icon} {abs(change):.1f}% vs previous period
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="kpi-card">
                <div class="kpi-title">Expense/Income Ratio</div>
                <div class="kpi-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)

    with kpi6:
        # Largest Expense Category
        if current_report["expenses"]["category_breakdown"]:
            largest_cat = max(current_report["expenses"]["category_breakdown"].items(), key=lambda x: x[1])
            prev_largest = max(prev_report["expenses"]["category_breakdown"].items(), key=lambda x: x[1]) if prev_report["expenses"]["category_breakdown"] else ("N/A", 0)
            
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Largest Expense Category</div>
                <div class="kpi-value">{largest_cat[0]}</div>
                <div class="kpi-change">${largest_cat[1]:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="kpi-card">
                <div class="kpi-title">Largest Expense Category</div>
                <div class="kpi-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)

    with kpi7:
        # Top Income Source
        if current_report["income"]["top_sources"]:
            top_source = max(current_report["income"]["top_sources"].items(), key=lambda x: x[1])
            prev_top = max(prev_report["income"]["top_sources"].items(), key=lambda x: x[1]) if prev_report["income"]["top_sources"] else ("N/A", 0)
            change = calculate_change(top_source[1], prev_top[1])
            change_color = "positive" if change >= 0 else "negative"
            change_icon = "↑" if change >= 0 else "↓"
            
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Top Income Source</div>
                <div class="kpi-value">{top_source[0]}</div>
                <div class="kpi-change {change_color}">
                    {change_icon} {abs(change):.1f}% vs previous period
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="kpi-card">
                <div class="kpi-title">Top Income Source</div>
                <div class="kpi-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)

    with kpi8:
        # Average Daily Spend
        expense_df = TransactionManager.get_recent_transactions(1000)
        if not expense_df.empty:
            expense_df = expense_df[(expense_df['date'] >= pd.to_datetime(start_date)) & 
                                (expense_df['date'] <= pd.to_datetime(end_date))]
            daily_spend = expense_df.groupby(expense_df['date'].dt.date)['amount'].sum().abs().mean()
            
            # Previous period
            prev_expense_df = expense_df[(expense_df['date'] >= pd.to_datetime(prev_start_date)) & 
                                    (expense_df['date'] < pd.to_datetime(start_date))]
            prev_daily = prev_expense_df.groupby(prev_expense_df['date'].dt.date)['amount'].sum().abs().mean() if not prev_expense_df.empty else 0
            change = calculate_change(daily_spend, prev_daily)
            change_color = "negative" if change >= 0 else "positive"  # Lower is better
            change_icon = "↑" if change >= 0 else "↓"
            
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Avg Daily Spend</div>
                <div class="kpi-value">${daily_spend:,.2f}</div>
                <div class="kpi-change {change_color}">
                    {change_icon} {abs(change):.1f}% vs previous period
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="kpi-card">
                <div class="kpi-title">Avg Daily Spend</div>
                <div class="kpi-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)

    # Financial Health Indicators
    st.markdown("## Financial Health Indicators")
    health1, health2, health3 = st.columns(3)

    with health1:
        # Liquidity Ratio (Cash/Current Liabilities - simplified)
        # For demo, we'll use (Net Flow / Expenses) as a proxy
        if current_report["expenses"]["total"] > 0:
            ratio = (current_report["net_flow"]["total"] / current_report["expenses"]["total"]) * 100
            health_status = "Excellent" if ratio > 20 else "Good" if ratio > 10 else "Fair" if ratio > 0 else "Poor"
            status_color = "#28a745" if ratio > 20 else "#5cb85c" if ratio > 10 else "#f0ad4e" if ratio > 0 else "#dc3545"
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = ratio,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Liquidity Ratio"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': status_color},
                    'steps': [
                        {'range': [0, 10], 'color': "#dc3545"},
                        {'range': [10, 20], 'color': "#f0ad4e"},
                        {'range': [20, 100], 'color': "#28a745"}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': ratio
                    }
                }
            ))
            fig.update_layout(height=250, margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with health2:
        # Savings Rate Trend
        if current_report["income"]["total"] > 0 and prev_report["income"]["total"] > 0:
            current_rate = (current_report["net_flow"]["total"] / current_report["income"]["total"]) * 100
            prev_rate = (prev_report["net_flow"]["total"] / prev_report["income"]["total"]) * 100

            fig = go.Figure()
            fig.add_trace(go.Indicator(
                mode = "number+delta",
                value = current_rate,
                number = {'suffix': "%"},
                delta = {'reference': prev_rate, 'relative': False},
                title = {"text": "Savings Rate Trend"},
                domain = {'x': [0, 1], 'y': [0, 1]}
            ))
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)

    with health3:
        # Expense Breakdown Alert
        if current_report["expenses"]["category_breakdown"]:
            df = pd.DataFrame.from_dict(current_report["expenses"]["category_breakdown"], 
                                    orient='index', 
                                    columns=['Amount'])
            df['Percentage'] = (df['Amount'] / df['Amount'].sum()) * 100
            largest_cat = df['Percentage'].idxmax()
            largest_pct = df['Percentage'].max()
            
            alert = ""
            if largest_pct > 50:
                alert = f"⚠️ {largest_cat} is {largest_pct:.1f}% of expenses"
                color = "#dc3545"
            elif largest_pct > 30:
                alert = f"⚠️ {largest_cat} is {largest_pct:.1f}% of expenses"
                color = "#f0ad4e"
            else:
                alert = "Balanced spending across categories"
                color = "#28a745"
            
            st.markdown(f"""
            <div style="background-color: {color}20; border-left: 4px solid {color}; 
                        padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                <div style="font-weight: 600; color: {color}; margin-bottom: 5px;">Expense Distribution</div>
                <div>{alert}</div>
            </div>
            """, unsafe_allow_html=True)
            
            fig = px.pie(df, values='Amount', names=df.index, hole=0.4)
            fig.update_layout(height=250, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    if time_period == "Custom":
        col1, col2 = st.sidebar.columns(2)
        start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
        end_date = col2.date_input("End Date", datetime.now())
    else:
        end_date = datetime.now()
        if time_period == "Week":
            start_date = end_date - timedelta(weeks=1)
        elif time_period == "Month":
            start_date = end_date - timedelta(days=30)
        elif time_period == "Quarter":
            start_date = end_date - timedelta(days=90)
        else:  # Year
            start_date = end_date - timedelta(days=365)

    # Get financial data
    report = TransactionManager.get_combined_financial_report(time_period.lower())

    # Top Metrics Row
    st.markdown("## Financial Overview")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown('<div class="metric-card" >'
                    '<div class="header" style="color: #4e73df;">Total Income</div>'
                    f'<div style="font-size: 2rem; color: #4e73df;">${report["income"]["total"]:,.2f}</div>'
                    '</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="metric-card">'
                    '<div class="header" style="color: #4e73df;">Total Expenses</div>'
                    f'<div style="font-size: 2rem; color: #4e73df;">${report["expenses"]["total"]:,.2f}</div>'
                    '</div>', unsafe_allow_html=True)

    with col3:
        net_flow = report["net_flow"]["total"]
        net_class = "positive" if net_flow >= 0 else "negative"
        st.markdown(f'<div class="metric-card">'
                    '<div class="header" style="color: #4e73df;">Net Cash Flow</div>'
                    f'<div style="font-size: 2rem;" class="{net_class}">${net_flow:,.2f}</div>'
                    '</div>', unsafe_allow_html=True)

    with col4:
        savings_rate = (net_flow / report["income"]["total"]) * 100 if report["income"]["total"] > 0 else 0
        savings_class = "positive" if savings_rate >= 0 else "negative"
        st.markdown(f'<div class="metric-card">'
                    '<div class="header" style="color: #4e73df;">Savings Rate</div>'
                    f'<div style="font-size: 2rem;" class="{savings_class}">{savings_rate:.1f}%</div>'
                    '</div>', unsafe_allow_html=True)

    # Main Content
    tab1, tab2, tab3, tab4 = st.tabs(["Trends", "Income Analysis", "Expense Analysis", "Transactions"])

    with tab1:
        st.markdown("## Financial Trends")
        
        # Create combined income/expense trend chart
        fig = go.Figure()
        
        # Add income trend
        if report["income"]["monthly_trend"]:
            income_df = pd.DataFrame.from_dict(report["income"]["monthly_trend"], orient='index', columns=['Income'])
            fig.add_trace(go.Scatter(
                x=income_df.index,
                y=income_df['Income'],
                name='Income',
                line=dict(color='#28a745', width=3),
                mode='lines+markers'
            ))
        
        # Add expense trend
        if report["expenses"]["monthly_trend"]:
            expense_df = pd.DataFrame.from_dict(report["expenses"]["monthly_trend"], orient='index', columns=['Expenses'])
            fig.add_trace(go.Scatter(
                x=expense_df.index,
                y=expense_df['Expenses'],
                name='Expenses',
                line=dict(color='#dc3545', width=3),
                mode='lines+markers'
            ))
        
        fig.update_layout(
            title='Monthly Income vs Expenses',
            xaxis_title='Month',
            yaxis_title='Amount ($)',
            hovermode='x unified',
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Cash flow composition
        st.markdown("### Cash Flow Composition")
        col1, col2 = st.columns(2)
        
        with col1:
            if report["income"]["total"] > 0:
                fig = px.pie(
                    names=list(report["income"]["top_sources"].keys()),
                    values=list(report["income"]["top_sources"].values()),
                    title='Income Sources',
                    color_discrete_sequence=px.colors.sequential.Greens
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if report["expenses"]["total"] > 0:
                fig = px.pie(
                    names=list(report["expenses"]["category_breakdown"].keys()),
                    values=list(report["expenses"]["category_breakdown"].values()),
                    title='Expense Categories',
                    color_discrete_sequence=px.colors.sequential.Reds
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("## Income Analysis")
        
        # Top income sources
        st.markdown("### Top Income Sources")
        if report["income"]["top_sources"]:
            income_sources = pd.DataFrame.from_dict(report["income"]["top_sources"], 
                                                orient='index', 
                                                columns=['Amount'])
            income_sources = income_sources.sort_values('Amount', ascending=False)
            
            fig = px.bar(
                income_sources,
                x=income_sources.index,
                y='Amount',
                color='Amount',
                color_continuous_scale='Greens',
                labels={'index': 'Source', 'Amount': 'Amount ($)'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No income data available for the selected period")
        
        # Income trend with forecast
        st.markdown("### Income Trend")
        if report["income"]["monthly_trend"]:
            income_trend = pd.DataFrame.from_dict(report["income"]["monthly_trend"], 
                                                orient='index', 
                                                columns=['Amount'])
            income_trend.index = pd.to_datetime(income_trend.index)
            income_trend = income_trend.sort_index()
            
            # Simple forecasting (moving average)
            forecast_periods = 3
            forecast = income_trend['Amount'].rolling(3).mean().iloc[-forecast_periods:]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=income_trend.index,
                y=income_trend['Amount'],
                name='Actual',
                line=dict(color='#28a745', width=3)
            ))
            fig.add_trace(go.Scatter(
                x=pd.date_range(income_trend.index[-1], periods=forecast_periods+1, freq='M')[1:],
                y=forecast,
                name='Forecast',
                line=dict(color='#28a745', width=3, dash='dot')
            ))
            
            fig.update_layout(
                title='Income Trend with Forecast',
                xaxis_title='Date',
                yaxis_title='Amount ($)',
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.markdown("## Expense Analysis")
        
        # Expense categories breakdown
        st.markdown("### Expense Categories")
        if report["expenses"]["category_breakdown"]:
            expense_cats = pd.DataFrame.from_dict(report["expenses"]["category_breakdown"], 
                                                orient='index', 
                                                columns=['Amount'])
            expense_cats = expense_cats.sort_values('Amount', ascending=False)
            
            fig = px.bar(
                expense_cats,
                x=expense_cats.index,
                y='Amount',
                color='Amount',
                color_continuous_scale='Reds',
                labels={'index': 'Category', 'Amount': 'Amount ($)'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No expense data available for the selected period")
        
        # Top merchants
        st.markdown("### Top Merchants")
        if report["expenses"]["top_merchants"]:
            top_merchants = pd.DataFrame.from_dict(report["expenses"]["top_merchants"], 
                                                orient='index', 
                                                columns=['Amount'])
            top_merchants = top_merchants.sort_values('Amount', ascending=False)
            
            fig = px.treemap(
                top_merchants,
                path=[top_merchants.index],
                values='Amount',
                color='Amount',
                color_continuous_scale='Reds',
                title='Spending by Merchant'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Expense alert system
        st.markdown("### Expense Alerts")
        expense_df = TransactionManager.get_recent_transactions(1000)
        if not expense_df.empty:
            # Filter by date
            expense_df = expense_df[(expense_df['date'] >= pd.to_datetime(start_date)) & 
                                (expense_df['date'] <= pd.to_datetime(end_date))]
            
            # Large transactions
            large_txns = expense_df[expense_df['amount'].abs() > expense_df['amount'].abs().quantile(0.9)]
            if not large_txns.empty:
                st.warning(f"⚠️ {len(large_txns)} large transactions detected (top 10%)")
                st.dataframe(large_txns[['date', 'merchant', 'amount', 'category']])
            
            # Unusual spending patterns
            daily_spending = expense_df.groupby(expense_df['date'].dt.date)['amount'].sum().abs()
            avg_spending = daily_spending.mean()
            std_spending = daily_spending.std()
            unusual_days = daily_spending[daily_spending > (avg_spending + 2*std_spending)]
            
            if not unusual_days.empty:
                st.warning(f"⚠️ {len(unusual_days)} days with unusually high spending detected")
                st.write(unusual_days)

    with tab4:
        st.markdown("## Transaction Details")
        
        # Combined transactions view
        st.markdown("### All Transactions")
        income_df = IncomeManager.get_recent_income(1000)
        expense_df = TransactionManager.get_recent_transactions(1000)
        
        if not income_df.empty or not expense_df.empty:
            income_df = income_df.loc[:, ~income_df.columns.duplicated()]
            # Combine data
            combined = pd.concat([
                income_df[['date', 'merchant', 'amount', 'category', 'description']],
                expense_df[['date', 'merchant', 'amount', 'category', 'description']]
            ])
            
            # Filter by date
            combined = combined[(combined['date'] >= pd.to_datetime(start_date)) & 
                            (combined['date'] <= pd.to_datetime(end_date))]
            
            # Add amount display column
            combined['amount_display'] = combined['amount'].abs()
            
            # Display with filters
            col1, col2 = st.columns(2)
            with col1:
                category_filter = st.multiselect(
                    "Filter by Category",
                    options=combined['category'].unique(),
                    default=combined['category'].unique()
                )

            # Apply filtering only by category
            filtered = combined[
                combined['category'].isin(category_filter)
            ].sort_values('date', ascending=False)
            filtered = filtered.loc[:, ~filtered.columns.duplicated()].reset_index(drop=True)
                        
            # Format display
            def color_amount(val):
                color = 'green' if val > 0 else 'red'
                return f'color: {color}'
            def highlight_amount(row):
                color = 'green' if row['amount'] > 0 else 'red'
                return ['color: {}'.format(color) if col == 'amount' else '' for col in row.index]
            
            
            st.dataframe(
                filtered.style.apply(highlight_amount, axis=1),
                use_container_width=True,
                height=600
            )
            
            # Download option
            csv = filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Transactions",
                csv,
                "transactions.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.warning("No transaction data available")