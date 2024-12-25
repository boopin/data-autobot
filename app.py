# App Version: 1.2.1
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# Connect to SQLite database
conn = sqlite3.connect(":memory:")

def preprocess_dataframe(df):
    """Cleans and standardizes column names for database compatibility."""
    df.columns = [col.strip().replace(" ", "_").replace("(", "").replace(")", "").lower() for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def create_aggregated_tables(df, table_name):
    """Creates daily, weekly, monthly, and quarterly aggregated tables for date-based analysis."""
    if "date" in df.columns:
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        # Exclude non-numeric columns for aggregation
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()

        if numeric_columns:
            df_weekly = df.groupby("week")[numeric_columns].sum().reset_index()
            df_monthly = df.groupby("month")[numeric_columns].sum().reset_index()
            df_quarterly = df.groupby("quarter")[numeric_columns].sum().reset_index()

            df_weekly.to_sql(f"{table_name}_weekly", conn, index=False, if_exists="replace")
            df_monthly.to_sql(f"{table_name}_monthly", conn, index=False, if_exists="replace")
            df_quarterly.to_sql(f"{table_name}_quarterly", conn, index=False, if_exists="replace")
        else:
            st.warning(f"No numeric columns available for aggregation in table '{table_name}'.")

def load_file(uploaded_file):
    """Loads and processes the uploaded file."""
    if uploaded_file.name.endswith(".xlsx"):
        excel_data = pd.ExcelFile(uploaded_file)
        for sheet in excel_data.sheet_names:
            df = pd.read_excel(excel_data, sheet_name=sheet)
            df = preprocess_dataframe(df)
            table_name = sheet.lower().replace(" ", "_")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            create_aggregated_tables(df, table_name)
    elif uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        df = preprocess_dataframe(df)
        table_name = uploaded_file.name.replace(".csv", "").lower().replace(" ", "_")
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        create_aggregated_tables(df, table_name)
    else:
        st.error("Unsupported file format. Please upload a CSV or Excel file.")

def generate_query(selected_table, selected_columns, sort_by, rows, compare_start=None, compare_end=None, compare_type=None):
    """Generates the SQL query based on user selections."""
    base_query = f"SELECT {', '.join(selected_columns)} FROM {selected_table}"
    where_clause = ""
    if compare_type and compare_start and compare_end:
        where_clause = f" WHERE {compare_type} BETWEEN '{compare_start}' AND '{compare_end}'"
    order_clause = f" ORDER BY {sort_by} DESC" if sort_by else ""
    limit_clause = f" LIMIT {rows}" if rows else ""
    return f"{base_query}{where_clause}{order_clause}{limit_clause}"

def main():
    st.title("Data Autobot - Comparison Enabled Analysis")
    st.subheader("Upload your data and start analyzing")

    uploaded_file = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to continue.")
        return

    load_file(uploaded_file)
    st.success("File uploaded and processed successfully!")

    # Table selection
    table_options = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)["name"].tolist()
    selected_table = st.selectbox("Select table to analyze:", table_options)

    # Retrieve columns
    column_info = pd.read_sql_query(f"PRAGMA table_info({selected_table})", conn)
    available_columns = column_info["name"].tolist()

    # Dropdown for metrics
    st.subheader("Analysis Options")
    selected_columns = st.multiselect("Select columns to display:", available_columns, default=available_columns[:3])
    metric_to_analyze = st.selectbox("Select metric to analyze:", [col for col in available_columns if "impressions" in col or "clicks" in col])
    sort_by = st.radio("Sort by:", ["Highest", "Lowest"], horizontal=True)
    rows_to_display = st.slider("Number of rows to display:", 5, 50, step=5)

    # Comparison options
    comparison_enabled = st.checkbox("Enable Comparison")
    compare_start, compare_end = None, None
    compare_type = None
    if comparison_enabled:
        compare_type = st.radio("Select comparison type:", ["Weekly", "Monthly", "Quarterly", "Custom"])
        if compare_type in ["Weekly", "Monthly", "Quarterly"]:
            periods = pd.read_sql_query(f"SELECT DISTINCT {compare_type.lower()} FROM {selected_table}_{compare_type.lower()}", conn)[compare_type.lower()].tolist()
            compare_start, compare_end = st.select_slider(f"Select two {compare_type} periods:", options=periods, value=(periods[0], periods[-1]))
        elif compare_type == "Custom":
            compare_start = st.date_input("Select start date for comparison:")
            compare_end = st.date_input("Select end date for comparison:")

    if st.button("Generate Analysis"):
        try:
            query = generate_query(selected_table, selected_columns, metric_to_analyze, rows_to_display, compare_start, compare_end, compare_type.lower() if comparison_enabled else None)
            result = pd.read_sql_query(query, conn)
            if comparison_enabled and compare_start and compare_end:
                result["percentage_change"] = ((result.iloc[1] - result.iloc[0]) / result.iloc[0]) * 100
            st.write("### Query Results")
            st.dataframe(result)

            # Visualization option
            if st.checkbox("Generate Visualization"):
                chart = px.bar(result, x="date", y=metric_to_analyze, text="percentage_change" if comparison_enabled else None, title="Analysis Chart")
                st.plotly_chart(chart)

        except Exception as e:
            st.error(f"Error executing query: {e}")

if __name__ == "__main__":
    main()
