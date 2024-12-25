import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import duckdb
from datetime import datetime
import io
from pathlib import Path
import re
import numpy as np

# Set page config
st.set_page_config(page_title="Data Analysis App", layout="wide")

# Initialize session state
if 'tables' not in st.session_state:
    st.session_state.tables = {}
if 'conn' not in st.session_state:
    st.session_state.conn = duckdb.connect(database=':memory:', read_only=False)

def clean_column_name(name):
    """Clean column names by removing brackets and converting to lowercase"""
    name = str(name).lower()
    name = re.sub(r'[\(\)\[\]\{\}]', '_', name)
    name = re.sub(r'_+', '_', name)  # Replace multiple underscores with single
    name = name.strip('_')  # Remove leading/trailing underscores
    return name

def process_date_columns(df):
    """Identify and process date columns, adding weekly, monthly, and quarterly versions"""
    date_columns = []
    for col in df.columns:
        try:
            if pd.api.types.is_datetime64_any_dtype(df[col]) or df[col].dtype == 'object':
                # Try converting to datetime
                df[col] = pd.to_datetime(df[col])
                # If successful, create additional date columns
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
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
                st.session_state.tables = {'main': {'df': df, 'date_columns': []}}
            else:
                # Read all sheets from Excel
                xlsx = pd.ExcelFile(uploaded_file)
                st.session_state.tables = {}
                for sheet_name in xlsx.sheet_names:
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                    st.session_state.tables[sheet_name] = {'df': df, 'date_columns': []}
            
            # Process each table
            for name, table_info in st.session_state.tables.items():
                df = table_info['df']
                # Clean column names
                df.columns = [clean_column_name(col) for col in df.columns]
                # Process date columns and get list of date columns
                df, date_columns = process_date_columns(df)
                # Update the table info
                st.session_state.tables[name] = {'df': df, 'date_columns': date_columns}
                # Update the table in DuckDB
                st.session_state.conn.execute(f"DROP TABLE IF EXISTS {name}")
                st.session_state.conn.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
            
            st.success("Data loaded successfully!")
            return True
            
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
            return False
    return False

def get_numeric_columns(table_name):
    """Get numeric columns from a table"""
    query = f"SELECT * FROM {table_name} LIMIT 1"
    df = st.session_state.conn.execute(query).df()
    return [col for col, dtype in df.dtypes.items() if np.issubdtype(dtype, np.number)]

def get_date_columns(table_name):
    """Get date columns from a table"""
    return st.session_state.tables[table_name]['date_columns']

def export_data(df, format_type):
    """Export dataframe to specified format"""
    if format_type == 'csv':
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        return buffer.getvalue()
    else:  # xlsx
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        return buffer.getvalue()

def main():
    st.title("Data Analysis App")
    
    # Data loading section
    st.header("1. Data Upload")
    data_loaded = load_data()
    
    if data_loaded and st.session_state.tables:
        # Analysis section
        st.header("2. Analysis Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Table selection
            table_name = st.selectbox(
                "Select table to analyze",
                options=list(st.session_state.tables.keys())
            )
            
            # Metric selection
            metrics = get_numeric_columns(table_name)
            selected_metrics = st.multiselect(
                "Select metrics to analyze",
                options=metrics
            )
        
        with col2:
            # Get date columns for the selected table
            date_columns = get_date_columns(table_name)
            
            # Only show date-related options if date columns exist
            if date_columns:
                date_column = st.selectbox(
                    "Select date column",
                    options=date_columns
                )
                
                # Analysis type selection with time-based options
                analysis_type = st.selectbox(
                    "Select analysis type",
                    options=['Time Series', 'Comparison', 'Summary Statistics']
                )
            else:
                st.info("No date columns detected in this table.")
                # Limited analysis options for non-date tables
                analysis_type = st.selectbox(
                    "Select analysis type",
                    options=['Summary Statistics', 'Distribution Analysis']
                )
        
        # Analysis execution
        if st.button("Analyze") and selected_metrics:
            st.header("3. Analysis Results")
            
            if date_columns and analysis_type == 'Time Series':
                # Execute query for time series
                query = f"""
                SELECT {date_column}, {', '.join(selected_metrics)}
                FROM {table_name}
                ORDER BY {date_column}
                """
                result_df = st.session_state.conn.execute(query).df()
                
                # Create time series plot
                fig = go.Figure()
                for metric in selected_metrics:
                    fig.add_trace(go.Scatter(
                        x=result_df[date_column],
                        y=result_df[metric],
                        name=metric
                    ))
                fig.update_layout(title="Time Series Analysis", xaxis_title=date_column)
                st.plotly_chart(fig, use_container_width=True)
                
            elif analysis_type == 'Summary Statistics':
                # Execute query for summary statistics
                query = f"""
                SELECT 
                    {', '.join([f'AVG({m}) as avg_{m}, MIN({m}) as min_{m}, MAX({m}) as max_{m}, 
                    STDDEV({m}) as std_{m}' for m in selected_metrics])}
                FROM {table_name}
                """
                result_df = st.session_state.conn.execute(query).df()
                st.dataframe(result_df)
                
            elif analysis_type == 'Distribution Analysis':
                # Create distribution plots for selected metrics
                for metric in selected_metrics:
                    fig = px.histogram(
                        st.session_state.conn.execute(f"SELECT {metric} FROM {table_name}").df(),
                        x=metric,
                        title=f"Distribution of {metric}"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # Display results table
            st.subheader("Data Table")
            result_df = st.session_state.conn.execute(f"SELECT * FROM {table_name} LIMIT 1000").df()
            st.dataframe(result_df)
            
            # Export options
            st.subheader("Export Results")
            export_format = st.radio("Select export format:", ('csv', 'xlsx'))
            export_data_val = export_data(result_df, export_format)
            
            st.download_button(
                label=f"Download as {export_format.upper()}",
                data=export_data_val,
                file_name=f"analysis_results.{export_format}",
                mime='text/csv' if export_format == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

if __name__ == "__main__":
    main()
