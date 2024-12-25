import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Helper functions
def load_data_to_db(file):
    """
    Load the uploaded file into an SQLite database, creating tables for each sheet or CSV.
    """
    conn = sqlite3.connect(":memory:")
    table_names = []
    if file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(file)
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            df.to_sql(sheet_name.lower().replace(" ", "_"), conn, index=False, if_exists="replace")
            table_names.append(sheet_name.lower().replace(" ", "_"))
    elif file.name.endswith(".csv"):
        df = pd.read_csv(file)
        table_name = file.name.lower().replace(".csv", "").replace(" ", "_")
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        table_names.append(table_name)
    return conn, table_names

def get_schema(table_name, conn):
    """
    Retrieve the schema (columns) of a given table.
    """
    query = f"PRAGMA table_info({table_name})"
    schema_info = pd.read_sql_query(query, conn)
    return list(schema_info['name'])

def is_numeric(column, conn, table_name):
    """
    Check if a column is numeric by inspecting the first few rows of the table.
    """
    query = f"SELECT {column} FROM {table_name} LIMIT 5"
    try:
        df = pd.read_sql_query(query, conn)
        return pd.api.types.is_numeric_dtype(df[column])
    except Exception:
        return False

def generate_query(selected_table, date_filter, metric, aggregation, sorting, start_date=None, end_date=None):
    """
    Generate SQL query for date-based tables.
    """
    if date_filter in ["Daily", "Weekly", "Monthly", "Quarterly"]:
        date_column = date_filter.lower()
    else:
        date_column = "date"

    where_clause = ""
    if start_date and end_date:
        where_clause = f"WHERE {date_column} BETWEEN '{start_date}' AND '{end_date}'"

    query = f"""
    SELECT {date_column}, {metric}
    FROM {selected_table}
    {where_clause}
    ORDER BY {metric} {sorting}
    LIMIT {aggregation};
    """
    return query.strip()

def generate_non_date_query(selected_table, metric, sorting, aggregation, display_columns):
    """
    Generate SQL query for tables without a 'date' column.
    """
    query = f"""
    SELECT {', '.join(display_columns)}, {metric}
    FROM {selected_table}
    ORDER BY {metric} {sorting}
    LIMIT {aggregation};
    """
    return query.strip()

# Main app logic
def main():
    st.title("Data AutoBot - Simplified Analytics")

    # Upload File
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to start.")
        return

    # Load data and create database
    conn, table_names = load_data_to_db(uploaded_file)

    # Select Table
    selected_table = st.selectbox("Select Table:", table_names)
    schema = get_schema(selected_table, conn)

    # Check if 'date' column exists
    if "date" in schema:
        # Show date-based filtering options
        st.write("### Date-Based Filtering")
        date_filter = st.selectbox("Date Filter:", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
        start_date, end_date = None, None
        if date_filter == "Custom":
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")

        st.write("### Metric-Based Filtering")
        metric = st.selectbox("Metrics:", schema)
        aggregation = st.selectbox("Rows to Display:", [5, 10, 25, 50])
        sorting = st.selectbox("Sorting:", ["DESC", "ASC"])

        if st.button("Run Analysis"):
            query = generate_query(
                selected_table=selected_table,
                date_filter=date_filter,
                metric=metric,
                aggregation=aggregation,
                sorting=sorting,
                start_date=start_date,
                end_date=end_date,
            )
            try:
                result = pd.read_sql_query(query, conn)
                st.write("### Analysis Results")
                st.dataframe(result)
            except Exception as e:
                st.error(f"Error executing query: {e}")

    else:
        # Show metric-based filtering options for non-date tables
        st.write("### Metric-Based Filtering")
        metric = st.selectbox("Metrics:", [col for col in schema if is_numeric(col, conn, selected_table)])
        aggregation = st.selectbox("Rows to Display:", [5, 10, 25, 50])
        sorting = st.selectbox("Sorting:", ["DESC", "ASC"])
        display_columns = st.multiselect("Columns to Display:", schema)

        if st.button("Generate Table"):
            if not display_columns:
                st.error("Please select at least one column to display.")
                return

            query = generate_non_date_query(
                selected_table=selected_table,
                metric=metric,
                sorting=sorting,
                aggregation=aggregation,
                display_columns=display_columns,
            )
            try:
                result = pd.read_sql_query(query, conn)
                st.write("### Analysis Results")
                st.dataframe(result)
            except Exception as e:
                st.error(f"Error executing query: {e}")

if __name__ == "__main__":
    main()
