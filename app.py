import datetime
import io
import pandas as pd
import plotly.express as px
import streamlit as st

# Page Configuration
st.set_page_config(page_title="RFM Growth Engine", layout="wide", page_icon="📊")
st.title("📊 RFM Customer Segmentation Engine")

# --- Helper Functions ---

def _suggest_column(columns, keywords):
    """
    Attempt to intelligently find the correct column based on keywords.
    """
    lowered = [col.lower() for col in columns]
    for idx, col_lower in enumerate(lowered):
        if any(key in col_lower for key in keywords):
            return columns[idx]
    return columns[0] if columns else None

def clean_data(df, mapping):
    """
    Standardize column names and ensure correct data formats.
    Handles column name collisions if user maps a column to a name that already exists.
    """
    # Create a copy to avoid SettingWithCopy warnings
    df = df.copy()
    
    # Anti-Collision Logic:
    target_cols = ['CustomerID', 'InvoiceDate', 'Amount', 'InvoiceNo']
    
    for target in target_cols:
        source = mapping[target]
        if target in df.columns and source != target:
            df.rename(columns={target: f"{target}_Original"}, inplace=True)
    
    # Rename columns based on user selection
    df = df.rename(columns={
        mapping['CustomerID']: 'CustomerID',
        mapping['InvoiceDate']: 'InvoiceDate',
        mapping['Amount']: 'Amount',
        mapping['InvoiceNo']: 'InvoiceNo'
    })
    
    df = df.dropna(subset=['CustomerID'])
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], errors='coerce')
    
    # Handle timezones robustly
    if pd.api.types.is_datetime64_any_dtype(df['InvoiceDate']):
        df['InvoiceDate'] = df['InvoiceDate'].dt.tz_localize(None)
    
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
    
    return df.dropna(subset=['InvoiceDate', 'Amount'])

def calculate_rfm(df, weights):
    """
    Calculate Recency, Frequency, and Monetary scores and apply custom weighting.
    """
    max_date = df['InvoiceDate'].max()
    reference_date = max_date + datetime.timedelta(days=1)
    
    # 1. Identify Extra Columns
    core_cols = ['CustomerID', 'InvoiceDate', 'InvoiceNo', 'Amount']
    extra_cols = [c for c in df.columns if c not in core_cols]
    
    # 2. Define Aggregation Logic
    agg_dict = {
        'InvoiceDate': lambda x: (reference_date - x.max()).days, # Recency calculation
        'InvoiceNo': 'nunique', # Frequency count
        'Amount': 'sum' # Monetary sum
    }
    
    for col in extra_cols:
        agg_dict[col] = 'first'
    
    # 3. Perform GroupBy & Aggregation
    rfm = df.groupby('CustomerID').agg(agg_dict).reset_index()
    
    rfm.rename(columns={'InvoiceDate': 'Recency', 'InvoiceNo': 'Frequency', 'Amount': 'Monetary'}, inplace=True)
    
    # Check for sufficient data
    if len(rfm) < 5:
        st.warning("⚠️ Not enough data for quantile scoring. Assigning default scores.")
        rfm['R_Score'] = 1
        rfm['F_Score'] = 1
        rfm['M_Score'] = 1
    else:
        # 4. Calculate Scores (1-5) using Quantiles
        rfm['R_Score'] = pd.qcut(rfm['Recency'].rank(method='first'), 5, labels=[5, 4, 3, 2, 1]).astype(int)
        rfm['F_Score'] = pd.qcut(rfm['Frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        rfm['M_Score'] = pd.qcut(rfm['Monetary'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    
    # Create RFM String
    rfm['RF_Score_Str'] = rfm['R_Score'].astype(str) + rfm['F_Score'].astype(str)
    rfm['RFM_Combo'] = rfm['RF_Score_Str'] + rfm['M_Score'].astype(str)
    
    # 5. Calculate Weighted Growth Score
    r_w, f_w, m_w = weights
    total_weight = r_w + f_w + m_w
    
    if total_weight == 0:
        total_weight = 1
        r_w, f_w, m_w = 0, 0, 0
    
    # Weighted Average Score
    rfm['Growth_Score'] = (
        (rfm['R_Score'] * r_w) + 
        (rfm['F_Score'] * f_w) + 
        (rfm['M_Score'] * m_w)
    ) / (total_weight * 5) * 100
    
    rfm['Growth_Score'] = rfm['Growth_Score'].fillna(0).round(1)
    
    return rfm

def segment_customers(rfm, r_weight):
    """
    Map RFM scores to segments based on Weighted Growth Score.
    Handles low Recency weight to avoid misleading labels.
    """
    if r_weight < 1:
        # Fallback segmentation for when Recency is ignored (purely value-based)
        bins = [0, 40, 70, 90, 101]
        labels = [
            'Low Value (Inactive?)', 
            'Mid Value', 
            'High Value', 
            'Top Spenders (Churn Status Unknown)'
        ]
        rfm['Segment'] = pd.cut(rfm['Growth_Score'], bins=bins, labels=labels, right=False)
        rfm['Segment'] = rfm['Segment'].astype(str).replace('nan', 'Low Value (Inactive?)')
    else:
        # Standard RFM Segments
        bins = [0, 30, 40, 50, 60, 70, 75, 80, 85, 90, 101]
        labels = [
            'Hibernating', 'At Risk', 'Can\'t Lose Them', 'About To Sleep', 
            'Need Attention', 'Promising', 'New Customers', 'Potential Loyalists', 
            'Loyal Customers', 'Champions'
        ]
        rfm['Segment'] = pd.cut(rfm['Growth_Score'], bins=bins, labels=labels, right=False)
        rfm['Segment'] = rfm['Segment'].astype(str).replace('nan', 'Hibernating')
    
    return rfm

def to_excel(df):
    """Convert DataFrame to Excel byte stream."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='RFM Analysis')
    processed_data = output.getvalue()
    return processed_data

# --- Main UI ---

# Initialize Session State
if 'analysis_active' not in st.session_state:
    st.session_state['analysis_active'] = False

uploaded_file = st.file_uploader("📂 Upload Customer Data (Excel)", type=["xlsx"])

if uploaded_file:
    # removed global try-except to show real errors if any
    raw_df = pd.read_excel(uploaded_file)
    cols = list(raw_df.columns)
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        with st.expander("📝 Column Mapping", expanded=True):
            st.info("Map your excel columns:")
            c_id = st.selectbox("Customer ID", cols, index=cols.index(_suggest_column(cols, ["id", "cust"])))
            c_date = st.selectbox("Invoice Date", cols, index=cols.index(_suggest_column(cols, ["date", "time"])))
            c_amt = st.selectbox("Total Amount", cols, index=cols.index(_suggest_column(cols, ["amount", "price"])))
            c_inv = st.selectbox("Invoice Number", cols, index=cols.index(_suggest_column(cols, ["invoice", "no"])))
            
            st.caption("ℹ️ Any other columns (Email, Phone, etc.) will be automatically preserved in the final report.")
        
        with st.expander("⚖️ Strategy Weights (Scale 0-10)", expanded=True):
            
            # Reset Button Callback
            def reset_weights():
                st.session_state['w_r_v9'] = 5
                st.session_state['w_f_v9'] = 5
                st.session_state['w_m_v9'] = 5
            
            st.button("Reset to Standard", on_click=reset_weights)
            
            st.caption("Rate the importance of each metric from 0 to 10:")
            # Updated keys to v9 to force full reset
            w_r = st.slider("Recency Importance", 0, 10, 5, key='w_r_v9')
            w_f = st.slider("Frequency Importance", 0, 10, 5, key='w_f_v9')
            w_m = st.slider("Monetary Importance", 0, 10, 5, key='w_m_v9')
            
            total_check = w_r + w_f + w_m
            
            # --- Smart Strategy Feedback ---
            if w_r == 0:
                st.warning("⚠️ **Critical Warning:** Recency weight is 0. The system cannot distinguish between 'Loyal' and 'Lost' customers. High-value churned customers may be misclassified as Champions.")
            elif w_f == 0:
                st.info("ℹ️ **Strategy Update:** Frequency analysis is disabled. Ideal for high-ticket businesses with one-time purchases.")
            elif w_m == 0:
                st.info("ℹ️ **Strategy Update:** Monetary analysis is disabled. Focusing purely on engagement and retention (Recency/Frequency).")
            
    # --- Auto-Run Analysis Logic ---
    if total_check == 0:
        st.error("⚠️ Total weight cannot be zero. Please increase at least one slider to see results.")
    else:
        # 1. Processing
        mapping = {'CustomerID': c_id, 'InvoiceDate': c_date, 'Amount': c_amt, 'InvoiceNo': c_inv}
        clean_df = clean_data(raw_df, mapping)
        
        # 2. RFM Calculation & Dynamic Segmentation
        weights = (int(w_r), int(w_f), int(w_m))
        rfm_data = calculate_rfm(clean_df, weights)
        final_df = segment_customers(rfm_data, w_r)
        
        # 3. Dynamic Analysis
        st.success(f"Analysis Active! Weighting Factors: R={w_r}, F={w_f}, M={w_m}")
        
        # Top Metrics
        # Calculations for new metrics
        total_customers = len(final_df)
        
        # Date Range Calculation
        min_date = clean_df['InvoiceDate'].min().strftime('%b %d, %Y')
        max_date = clean_df['InvoiceDate'].max().strftime('%b %d, %Y')
        date_range_caption = f"{min_date} - {max_date}"
        
        # Avg CLV
        avg_clv = final_df['Monetary'].mean()
        
        # Loyalty Rate (Champions + Loyal Customers)
        # Note: Need to handle case where these segments might not exist if weights are 0
        loyalty_segments = ['Champions', 'Loyal Customers']
        # Filter strictly for segments that exist in the current dataframe
        loyalty_count = final_df[final_df['Segment'].isin(loyalty_segments)].shape[0]
        loyalty_rate = (loyalty_count / total_customers * 100) if total_customers > 0 else 0
        
        # Churn Risk (At Risk + Hibernating + Can't Lose Them)
        churn_segments = ['At Risk', 'Hibernating', "Can't Lose Them"]
        churn_count = final_df[final_df['Segment'].isin(churn_segments)].shape[0]
        churn_rate = (churn_count / total_customers * 100) if total_customers > 0 else 0

        # Display Metrics
        m1, m2, m3, m4 = st.columns(4)
        
        m1.metric("Customer Base", f"{total_customers:,}", help=f"Date Range: {date_range_caption}")
        # Adding caption manually since metric help is a tooltip, but prompt asked for caption below. 
        # Streamlit st.metric doesn't natively support a subtitle below the value in standard theme easily without custom html or delta.
        # We can simulate context using the 'delta' parameter or just leave it clean. 
        # Let's use st.caption below the metric for the date range to match the request "Display the Date Range... below the number".
        with m1:
            st.caption(date_range_caption)

        m2.metric("Avg CLV", f"${avg_clv:,.0f}")
        
        m3.metric("Loyalty Rate", f"{loyalty_rate:.1f}%", help="Champions + Loyal Customers")
        
        m4.metric("Churn Risk", f"{churn_rate:.1f}%", help="At Risk + Hibernating + Can't Lose Them")
        
        st.divider()
        
        col_chart, col_data = st.columns([1, 2])
        
        with col_chart:
            st.subheader("Dynamic Segment Map")
            segment_counts = final_df['Segment'].value_counts().reset_index()
            segment_counts.columns = ['Segment', 'Count']
            
            fig = px.treemap(segment_counts, path=['Segment'], values='Count',
                             color='Count', color_continuous_scale='Spectral',
                             title='Dynamic RFM Distribution')
            st.plotly_chart(fig, use_container_width=True)

        with col_data:
            st.subheader("Customer Leaderboard")
            sorted_df = final_df.sort_values(by='Growth_Score', ascending=False)
            
            display_cols = ['CustomerID', 'Segment', 'Growth_Score', 'Recency', 'Frequency', 'Monetary']
            extra_cols = [c for c in sorted_df.columns if c not in display_cols and c not in ['R_Score', 'F_Score', 'M_Score', 'RF_Score_Str', 'RFM_Combo']]
            if len(extra_cols) <= 3: 
                display_cols.extend(extra_cols)
                
            st.dataframe(
                sorted_df[display_cols], 
                use_container_width=True,
                height=400
            )
        
        # Download
        excel_data = to_excel(sorted_df)
        st.download_button(
            label="📥 Download Full Report (Includes Emails/Phones)",
            data=excel_data,
            file_name="RFM_Dynamic_Segmentation.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👆 Upload your Excel file to generate insights.")

# --- Footer ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        Built with ❤️ by <a href='https://github.com/naserr/' target='_blank' style='text-decoration: none; color: #E11D48; font-weight: bold;'>Naser Rahmani</a> | Technical Growth Engineer
    </div>
    """, 
    unsafe_allow_html=True
)