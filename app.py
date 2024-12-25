import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import io
import re
from pathlib import Path

# Set page config
st.set_page_config(page_title="Data Analysis App", layout="wide")

# Initialize SQLite connection
@st.cache_resource
def get_db_connection():
    return sqlite3.connect(':memory:', check_same_thread=False)

def clean_column_name(name):
    """Clean column names by removing brackets and converting to lowercase"""
    name = str(name).lower()
    name = re.sub(r'[\(\)\[\]\{\}]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_')

@st.cache_data
def process_date_columns(df):
    """Process date columns efficiently"""
    date_columns = []
    for col in df.columns:
        try:
            if pd.api.types.is_datetime64_any_dtype(df[col]) or df[col].dtype == 'object':
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if not df[col].isna().all():
                    df[f'{col}_week'] = df[col].dt.isocalendar().week
                    df[f'{col}_month'] = df[col].dt.month
                    df[f'{col}_quarter'] = df[col].dt.quarter
                    df[f'{col}_year'] = df[col].dt.year
                    date_columns.append(col)
        except:
            continue
    return df, date_columns

def load_data():
    """Load and process uploaded file"""
    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=['xlsx', 'csv'])
    
    if uploaded_file is not None:
        try:
            conn = get_db_connection()
            
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
                tables = {'main': {'df': df, 'date_columns': []}}
            else:
                xlsx = pd.ExcelFile(uploaded_file)
                tables = {
                    sheet_name: {'df': pd.read_excel(uploaded_file, sheet_name=sheet_name), 
                               'date_columns': []}
                    for sheet_name in xlsx.sheet_names
                }
            
            # Process each table
            for name, table_info in tables.items():
                df = table_info['df']
                # Clean column names
                df.columns = [clean_column_name(col) for col in df.columns]
                # Process date columns
                df, date_columns = process_date_columns(df)
                # Update the table info
                tables[name] = {'df': df, 'date_columns': date_columns}
                # Save to SQLite
                df.to_sql(name, conn, if_exists='replace', index=False)
            
            st.success("Data loaded successfully!")
            return tables, conn
            
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
            return None, None
    return None, None

def get_numeric_columns(df):
    """Get numeric columns from dataframe"""
    return [col for col, dtype in df.dtypes.items() if pd.api.types.is_numeric_dtype(dtype)]

def build_stats_query(metrics, table_name):
    """Build the SQL query for summary statistics"""
    stat_expressions = []
    for m in metrics:
        stat_expressions.extend([
            f"AVG({m}) as avg_{m}",
            f"MIN({m}) as min_{m}",
            f"MAX({m}) as max_{m}"
        ])
    return f"SELECT {', '.join(stat_expressions)} FROM {table_name}"

def main():
    st.title("Data Analysis App")
    
    # Data loading section
    st.header("1. Data Upload")
    tables, conn = load_data()
    
    if tables and conn:
        # Analysis section
        st.header("2. Analysis Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Table selection
            table_name = st.selectbox(
                "Select table to analyze",
                options=list(tables.keys())
            )
            
            if table_name:
                current_df = tables[table_name]['df']
                metrics = get_numeric_columns(current_df)
                selected_metrics = st.multiselect(
                    "Select metrics to analyze",
                    options=metrics
                )
        
        with col2:
            date_columns = tables[table_name]['date_columns']
            
            if date_columns:
                date_column = st.selectbox(
                    "Select date column",
                    options=date_columns
                )
                
                analysis_type = st.selectbox(
                    "Select analysis type",
                    options=['Time Series', 'Summary Statistics']
                )
            else:
                st.info("No date columns detected in this table.")
                analysis_type = 'Summary Statistics'
        
        # Analysis execution
        if st.button("Analyze") and selected_metrics:
            st.header("3. Analysis Results")
            
            if date_columns and analysis_type == 'Time Series':
                # Time series analysis
                query = f"SELECT {date_column}, {', '.join(selected_metrics)} FROM {table_name} ORDER BY {date_column}"
                result_df = pd.read_sql_query(query, conn)
                
                fig = px.line(
                    result_df,
                    x=date_column,
                    y=selected_metrics,
                    title="Time Series Analysis"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Summary statistics
            stats_query = build_stats_query(selected_metrics, table_name)
            stats_df = pd.read_sql_query(stats_query, conn)
            st.dataframe(stats_df)
            
            # Display results table
            st.subheader("Data Preview")
            result_df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 1000", conn)
            st.dataframe(result_df)
            
            # Export options
            st.subheader("Export Results")
            export_format = st.radio("Select format:", ('csv', 'xlsx'))
            
            if export_format == 'csv':
                csv = result_df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    f"analysis_results.csv",
                    "text/csv"
                )
            else:
                buffer = io.BytesIO()
                result_df.to_excel(buffer, index=False)
                st.download_button(
                    "Download Excel",
                    buffer.getvalue(),
                    f"analysis_results.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()
