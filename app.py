# App Version: 2.0.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Configure app
st.set_page_config(page_title="Data Analytics Aggregator", layout="wide")

def preprocess_data(df):
    """Clean and preprocess data for easier handling."""
    df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df

def create_aggregations(df, table_name, conn):
    """Create weekly, monthly, and quarterly aggregations."""
    if 'date' in df.columns:
        df['week'] = df['date'].dt.to_period('W').apply(lambda r: r.start_time)
        df['month'] = df['date'].dt.to_period('M').apply(lambda r: r.start_time)
        df['quarter'] = df['date'].dt.to_period('Q').apply(lambda r: r.start_time)

        for period in ['week', 'month', 'quarter']:
            agg_table_name = f"{table_name}_{period}"
            agg_df = df.groupby(period).sum().reset_index()
            agg_df.to_sql(agg_table_name, conn, index=False, if_exists="replace")

def get_table_schema(conn, table_name):
    """Fetch schema of the selected table."""
    query = f"PRAGMA table_info({table_name});"
    schema_info = pd.read_sql(query, conn)
    return schema_info

def generate_query(table_name, columns, date_filter=None, limit=None):
    """Build SQL query dynamically."""
    base_query = f"SELECT {', '.join(columns)} FROM {table_name}"
    where_clause = f"WHERE {date_filter}" if date_filter else ""
    order_clause = f"ORDER BY {columns[-1]} DESC" if len(columns) > 1 else ""
    limit_clause = f"LIMIT {limit}" if limit else ""
    query = f"{base_query} {where_clause} {order_clause} {limit_clause};"
    return query

# Streamlit app layout
def main():
    st.title("Data Analytics Aggregator")

    uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to start analysis.")
        return

    conn = sqlite3.connect(":memory:")

    if uploaded_file.name.endswith('.xlsx'):
        excel_data = pd.ExcelFile(uploaded_file)
        sheet_names = excel_data.sheet_names
        st.write("Available Sheets:", sheet_names)
        
        for sheet in sheet_names:
            df = pd.read_excel(uploaded_file, sheet_name=sheet)
            df = preprocess_data(df)
            table_name = sheet.lower().replace(" ", "_")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            create_aggregations(df, table_name, conn)
    elif uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
        df = preprocess_data(df)
        table_name = uploaded_file.name.lower().replace(".csv", "").replace(" ", "_")
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        create_aggregations(df, table_name, conn)

    st.success("File successfully processed and saved to the database!")

    table_names = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
    selected_table = st.selectbox("Select a table to analyze:", table_names["name"])

    if selected_table:
        schema_info = get_table_schema(conn, selected_table)
        st.write("Table Schema:", schema_info)

        # Dropdowns for query building
        date_column = st.selectbox("Select Date Column", schema_info["name"][schema_info["name"].str.contains('date')])
        selected_columns = st.multiselect("Select Columns to Analyze", schema_info["name"])
        top_n = st.selectbox("Number of Records", [5, 10, 25, 50])

        if st.button("Run Query"):
            if not selected_columns:
                st.error("Please select at least one column for analysis.")
            else:
                query = generate_query(selected_table, selected_columns, date_filter=None, limit=top_n)
                st.info(f"Generated Query:\n{query}")
                try:
                    result = pd.read_sql(query, conn)
                    st.write("Query Results:", result)
                except Exception as e:
                    st.error(f"Error running query: {e}")

if __name__ == "__main__":
    main()
