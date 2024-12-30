# Part 1: Basic Setup and Data Processing
# App Version: 2.7.0

import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'

def quote_column_name(column_name):
    """Properly quote column names for SQLite."""
    return f'"{column_name}"'

def generate_combined_visualization(df, bar_metric, line_metric, time_period):
    """Generate combined visualization using Plotly."""
    fig = px.bar(df, x=time_period, y=bar_metric, title=f"{bar_metric} Analysis Over {time_period.capitalize()}")
    if line_metric:
        fig.add_scatter(x=df[time_period], y=df[line_metric], mode='lines', name=line_metric)
    fig.update_layout(template="plotly_white")
    return fig

# Streamlit Configuration
st.set_page_config(
    page_title="Data Autobot - Analytics Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Add CSS styling
st.markdown(
    """
    <style>
    .main-heading {
        font-size: 32px;
        font-weight: bold;
        color: #4A90E2;
    }
    .sub-heading {
        font-size: 20px;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
        color: #333;
    }
    .data-section {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar Navigation
st.sidebar.title("Navigation")
nav_option = st.sidebar.radio(
    "Choose a Section:",
    ["Upload & Process Data", "Data Analysis", "Visualization"]
)

if nav_option == "Upload & Process Data":
    # Section 1: Upload and Process Data
    st.markdown("<div class='main-heading'>Upload Your Data</div>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload your Excel or CSV file:", type=["csv", "xlsx"])

    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.success("File successfully uploaded!")
        table_name = "uploaded_data"
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        st.write("**Preview of Uploaded Data:**")
        st.dataframe(df.head())
if nav_option == "Data Analysis":
    # Section 2: Data Analysis
    st.markdown("<div class='main-heading'>Data Analysis</div>", unsafe_allow_html=True)
    
    table_name = "uploaded_data"
    
    # Select a metric for analysis
    metric = st.selectbox(
        "Select a Metric for Analysis:",
        ["impressions_total", "clicks_total", "impressions_organic"]
    )
    
    # Allow selection of additional columns for analysis
    additional_columns = st.multiselect(
        "Additional Columns for Analysis:",
        ["date", "week"]
    )
    
    # Button to execute analysis
    if st.button("Run Analysis"):
        # SQL query to fetch selected data
        query = f"SELECT {quote_column_name(metric)}, {', '.join(map(quote_column_name, additional_columns))} FROM {quote_table_name(table_name)}"
        analysis_df = pd.read_sql(query, conn)
        
        # Display the results
        st.write("**Analysis Results:**")
        st.dataframe(analysis_df)
if nav_option == "Visualization":
    # Section 3: Visualization
    st.markdown("<div class='main-heading'>Data Visualization</div>", unsafe_allow_html=True)
    
    # Select bar chart metric
    bar_metric = st.selectbox(
        "Select Bar Chart Metric:",
        ["impressions_total", "clicks_total"]
    )
    
    # Optional line chart metric
    line_metric = st.selectbox(
        "Add Line Chart Metric (Optional):",
        [None, "clicks_total", "impressions_organic"],
        index=0
    )
    
    # Select time period
    time_period = st.radio("Time Period:", ["week", "date"])
    
    # Button to generate visualization
    if st.button("Generate Visualization"):
        # SQL query to fetch data for visualization
        query = f"SELECT {quote_column_name(bar_metric)}, {quote_column_name(line_metric)}, {quote_column_name(time_period)} FROM {quote_table_name(table_name)}"
        viz_df = pd.read_sql(query, conn)
        
        # Generate and display visualization
        fig = generate_combined_visualization(viz_df, bar_metric, line_metric, time_period)
        st.plotly_chart(fig, use_container_width=True)
