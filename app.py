# App Version: 2.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

def create_database_connection():
    """Create an SQLite in-memory database connection."""
    return sqlite3.connect(":memory:")

def preprocess_dataframe(df):
    """Preprocess the dataframe for database compatibility."""
    df.columns = [col.lower().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def load_file(file):
    """Load the uploaded file into the database."""
    conn = create_database_connection()
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
        df = preprocess_dataframe(df)
        table_name = file.name.replace(".csv", "").replace(" ", "_").lower()
        df.to_sql(table_name, conn, index=False, if_exists="replace")
    elif file.name.endswith(".xlsx"):
        excel_data = pd.ExcelFile(file)
        for sheet_name in excel_data.sheet_names:
            df = excel_data.parse(sheet_name)
            df = preprocess_dataframe(df)
            table_name = sheet_name.replace(" ", "_").lower()
            df.to_sql(table_name, conn, index=False, if_exists="replace")
    return conn

def get_table_names(conn):
    """Retrieve table names from the database."""
    query = "SELECT name FROM sqlite_master WHERE type='table';"
    return [row[0] for row in conn.execute(query).fetchall()]

def get_table_schema(conn, table_name):
    """Retrieve the schema of a specific table."""
    query = f"PRAGMA table_info({table_name});"
    columns = [row[1] for row in conn.execute(query).fetchall()]
    return columns

def run_analysis_query(conn, table_name, selected_metric, display_columns, rows, sort_order):
    """Run a query to fetch the analysis data."""
    sort_column = f"{selected_metric} DESC" if sort_order == "Highest" else f"{selected_metric} ASC"
    selected_columns = ", ".join(display_columns)
    query = f"SELECT {selected_columns} FROM {table_name} ORDER BY {sort_column} LIMIT {rows}"
    return pd.read_sql_query(query, conn)

def create_visualization(df):
    """Generate a Plotly visualization based on the query result."""
    if len(df.columns) < 2:
        st.warning("Data must have at least two columns for visualization.")
        return None
    chart = px.bar(
        df,
        x=df.columns[0],
        y=df.columns[1],
        title="Generated Visualization",
        labels={df.columns[0]: "Category", df.columns[1]: "Value"}
    )
    return chart

def main():
    st.title("Data Autobot")
    st.write("Version: 2.0")

    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if not uploaded_file:
        st.warning("Please upload a file to proceed.")
        return

    conn = load_file(uploaded_file)
    table_names = get_table_names(conn)
    selected_table = st.selectbox("Select Table to Analyze", table_names)

    if selected_table:
        schema = get_table_schema(conn, selected_table)
        st.write(f"Schema for `{selected_table}`:", schema)

        metric_options = [col for col in schema if "int" in str(conn.execute(f"PRAGMA table_info({selected_table})").fetchall())]
        selected_metric = st.selectbox("Select Metric to Analyze", metric_options)
        display_columns = st.multiselect("Select Columns to Display", schema)
        rows_to_display = st.slider("Rows to Display", 5, 50, 10)
        sort_order = st.radio("Sort By", ["Highest", "Lowest"])

        if st.button("Run Query"):
            if selected_metric and display_columns:
                query_result = run_analysis_query(conn, selected_table, selected_metric, display_columns, rows_to_display, sort_order)
                st.write("### Query Results")
                st.dataframe(query_result)
            else:
                st.warning("Please select a metric and columns to display.")

        if st.button("Generate Visualization"):
            if not query_result.empty:
                chart = create_visualization(query_result)
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.warning("No data to visualize. Please run a query first.")

    conn.close()

if __name__ == "__main__":
    main()
