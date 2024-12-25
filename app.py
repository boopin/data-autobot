import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime


def clean_column_name(column_name):
    """Sanitize column names for DuckDB compatibility."""
    return (
        column_name.lower()
        .strip()
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("-", "_")
    )


def preprocess_data(df):
    """Preprocess dataframe: clean column names and handle datetime conversion."""
    original_columns = df.columns.tolist()
    df.columns = [clean_column_name(col) for col in df.columns]
    column_mapping = dict(zip(original_columns, df.columns))
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df, column_mapping


def create_db_tables(excel_file, conn):
    """Create DuckDB tables for each sheet in the uploaded Excel file."""
    table_names = {}
    excel_data = pd.ExcelFile(excel_file)
    for sheet_name in excel_data.sheet_names:
        df = pd.read_excel(excel_data, sheet_name=sheet_name)
        df, column_mapping = preprocess_data(df)
        table_name = clean_column_name(sheet_name)
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        table_names[table_name] = column_mapping
    return table_names


def fetch_schema(table_name, conn):
    """Fetch schema of a table."""
    try:
        schema_info = conn.execute(f"DESCRIBE {table_name}").fetchdf()
        return schema_info["column_name"].tolist()
    except Exception as e:
        st.error(f"Error fetching schema: {e}")
        return []


def main():
    st.title("Dynamic Data Analyzer with DuckDB")

    uploaded_file = st.file_uploader("Upload an Excel File", type=["xlsx"])
    if not uploaded_file:
        st.info("Please upload an Excel file.")
        return

    conn = duckdb.connect(database=":memory:")
    table_mappings = {}

    if uploaded_file:
        try:
            table_mappings = create_db_tables(uploaded_file, conn)
            st.success("File successfully processed and saved to the database!")
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return

    # Let the user select a table
    table_names = list(table_mappings.keys())
    selected_table = st.selectbox("Select a table for analysis:", table_names)

    if not selected_table:
        st.warning("No table selected.")
        return

    # Fetch schema dynamically
    available_columns = fetch_schema(selected_table, conn)
    if not available_columns:
        st.warning("This table does not contain any columns. Analysis cannot proceed.")
        return

    # Column Selection
    st.subheader("Select Columns to Display")
    selected_columns = st.multiselect(
        "Columns to include in the query", available_columns, default=available_columns
    )

    if not selected_columns:
        st.warning("No columns selected for display.")
        return

    # Date Range Selection
    if "date" in available_columns:
        date_range = st.radio(
            "Select Date Range",
            ["All", "Custom", "Weekly", "Monthly", "Quarterly"],
            index=0,
        )

        where_clause = ""
        if date_range == "Custom":
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
            if start_date and end_date:
                where_clause = f"WHERE date BETWEEN '{start_date}' AND '{end_date}'"
        elif date_range == "Weekly":
            st.info("Weekly aggregations are coming soon.")
        elif date_range == "Monthly":
            st.info("Monthly aggregations are coming soon.")
        elif date_range == "Quarterly":
            st.info("Quarterly aggregations are coming soon.")

    # Query Generation
    limit = st.number_input("Number of Records to Display", min_value=1, max_value=100, value=10)
    sql_query = f'SELECT {", ".join(selected_columns)} FROM {selected_table} {where_clause} LIMIT {limit}'

    st.write("Generated Query:", sql_query)

    if st.button("Run Query"):
        try:
            query_result = conn.execute(sql_query).fetchdf()
            st.dataframe(query_result)
        except Exception as e:
            st.error(f"Error executing query: {e}")


if __name__ == "__main__":
    main()
