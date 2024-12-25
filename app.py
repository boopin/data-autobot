import streamlit as st
import pandas as pd
import plotly.express as px  # Lighter than importing both px and go
import duckdb
import io
import re
from functools import lru_cache  # For caching heavy computations

# Streamlit configuration for performance
st.set_page_config(
    page_title="Data Analysis App",
    layout="wide",
    initial_sidebar_state="collapsed"  # Reduces initial render time
)

# Initialize connection only when needed
@st.cache_resource
def init_db():
    return duckdb.connect(database=':memory:', read_only=False)

# Cache data cleaning functions
@st.cache_data
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

@st.cache_data
def load_data(uploaded_file):
    """Load and process uploaded file with caching"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            return {'main': {'df': df, 'date_columns': []}}
        else:
            xlsx = pd.ExcelFile(uploaded_file)
            return {
                sheet_name: {'df': pd.read_excel(uploaded_file, sheet_name=sheet_name), 'date_columns': []}
                for sheet_name in xlsx.sheet_names
            }
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return None

@st.cache_data
def get_numeric_columns(df):
    """Get numeric columns from dataframe"""
    return [col for col, dtype in df.dtypes.items() if pd.api.types.is_numeric_dtype(dtype)]

def main():
    st.title("Data Analysis App")
    
    # Initialize database connection
    conn = init_db()
    
    # Data loading section
    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=['xlsx', 'csv'])
    
    if uploaded_file:
        tables = load_data(uploaded_file)
        
        if tables:
            # Process tables
            for name, table_info in tables.items():
                df = table_info['df']
                df.columns = [clean_column_name(col) for col in df.columns]
                df, date_columns = process_date_columns(df)
                tables[name] = {'df': df, 'date_columns': date_columns}
                conn.execute(f"DROP TABLE IF EXISTS {name}")
                conn.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
            
            # Analysis configuration
            col1, col2 = st.columns(2)
            
            with col1:
                table_name = st.selectbox(
                    "Select table",
                    options=list(tables.keys())
                )
                
                if table_name:
                    current_df = tables[table_name]['df']
                    metrics = get_numeric_columns(current_df)
                    selected_metrics = st.multiselect(
                        "Select metrics",
                        options=metrics
                    )
            
            with col2:
                date_columns = tables[table_name]['date_columns']
                
                if date_columns:
                    date_column = st.selectbox("Select date column", options=date_columns)
                    analysis_type = st.selectbox(
                        "Select analysis type",
                        options=['Time Series', 'Summary Statistics']
                    )
                else:
                    st.info("No date columns detected.")
                    analysis_type = 'Summary Statistics'
            
            # Analysis execution
            if st.button("Analyze") and selected_metrics:
                st.header("Analysis Results")
                
                if date_columns and analysis_type == 'Time Series':
                    # Time series analysis
                    result_df = conn.execute(f"""
                        SELECT {date_column}, {', '.join(selected_metrics)}
                        FROM {table_name}
                        ORDER BY {date_column}
                    """).df()
                    
                    fig = px.line(
                        result_df,
                        x=date_column,
                        y=selected_metrics,
                        title="Time Series Analysis"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                else:
                    # Summary statistics
                    stats_query = f"""
                    SELECT 
                        {', '.join([f'AVG({m}) as avg_{m}, MIN({m}) as min_{m}, 
                        MAX({m}) as max_{m}' for m in selected_metrics])}
                    FROM {table_name}
                    """
                    stats_df = conn.execute(stats_query).df()
                    st.dataframe(stats_df)
                
                # Export options
                st.subheader("Export Results")
                export_format = st.radio("Select format:", ('csv', 'xlsx'))
                
                if export_format == 'csv':
                    result_df = conn.execute(f"SELECT * FROM {table_name}").df()
                    csv = result_df.to_csv(index=False)
                    st.download_button(
                        "Download CSV",
                        csv,
                        f"analysis_results.csv",
                        "text/csv"
                    )
                else:
                    buffer = io.BytesIO()
                    result_df = conn.execute(f"SELECT * FROM {table_name}").df()
                    result_df.to_excel(buffer, index=False)
                    st.download_button(
                        "Download Excel",
                        buffer.getvalue(),
                        f"analysis_results.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

if __name__ == "__main__":
    main()
