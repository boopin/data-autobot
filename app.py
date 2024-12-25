# App Version: 2.2
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
    columns_info = conn.execute(query).fetchall()
    columns = [row[1] for row in columns_info]
    column_types = [row[2] for row in columns_info]
    return columns, column_types


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


def add_comparison(conn, table_name, metric, compare_type, period1, period2):
    """Run a comparison query between two periods."""
    query = f"""
        SELECT '{period1}' AS period, SUM({metric}) AS total
        FROM {table_name}_{compare_type}
        WHERE {compare_type} = '{period1}'
        UNION ALL
        SELECT '{period2}' AS period, SUM({metric}) AS total
        FROM {table_name}_{compare_type}
        WHERE {compare_type} = '{period2}'
    """
    return pd.read_sql_query(query, conn)


def main():
    st.title("Data Autobot")
    st.write("Version: 2.2")

    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if not uploaded_file:
        st.warning("Please upload a file to proceed.")
        return

    conn = load_file(uploaded_file)
    table_names = get_table_names(conn)
    selected_table = st.selectbox("Select Table to Analyze", table_names)

    if selected_table:
        schema, column_types = get_table_schema(conn, selected_table)
        st.write(f"Schema for `{selected_table}`:", schema)

        # Metrics Dropdown
        metrics_columns = [col for col, col_type in zip(schema, column_types) if "int" in col_type or "real" in col_type]
        selected_metric = st.selectbox("Select Metric to Analyze", metrics_columns, disabled=not metrics_columns)

        # Display Columns Dropdown
        additional_columns = st.multiselect("Select Additional Columns to Display", schema, default=["date"] if "date" in schema else [])

        # Additional user settings
        rows_to_display = st.slider("Rows to Display", 5, 50, 10)
        sort_order = st.radio("Sort By", ["Highest", "Lowest"])

        # Comparison Section
        comparison_enabled = st.checkbox("Enable Comparison")
        if comparison_enabled:
            compare_type = st.radio("Select Comparison Type", ["Weekly", "Monthly", "Quarterly"])
            period1 = st.selectbox("Select Period 1", [])
            period2 = st.selectbox("Select Period 2", [])

        if st.button("Run Query"):
            if selected_metric:
                display_columns = [selected_metric] + additional_columns
                query_result = run_analysis_query(conn, selected_table, selected_metric, display_columns, rows_to_display, sort_order)
                st.write("### Query Results")
                st.dataframe(query_result)

                if comparison_enabled and period1 and period2:
                    compare_result = add_comparison(conn, selected_table, selected_metric, compare_type, period1, period2)
                    compare_result["Change (%)"] = ((compare_result["total"].iloc[1] - compare_result["total"].iloc[0]) / compare_result["total"].iloc[0]) * 100
                    st.write("### Comparison Results")
                    st.dataframe(compare_result)
            else:
                st.warning("Please select a metric to analyze.")

        if st.button("Generate Visualization"):
            if 'query_result' in locals() and not query_result.empty:
                chart = create_visualization(query_result)
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.warning("No data to visualize. Please run a query first.")

    conn.close()


if __name__ == "__main__":
    main()
