# App Version: 1.5.0
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta
import plotly.express as px

DATABASE = ":memory:"

# Initialize Streamlit app
st.title("Data Autobot")
st.subheader("Analyze Your Data with Ease")

# Version control
st.write("**App Version:** 1.5.0")

# Utility function to clean column names
def clean_column_names(columns):
    return [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in columns]

# Utility function to preprocess data
def preprocess_data(df):
    df.columns = clean_column_names(df.columns)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    return df

# Precompute aggregation tables
def create_aggregation_tables(df, table_name, conn):
    if "date" in df.columns:
        df.to_sql(f"{table_name}_daily", conn, index=False, if_exists="replace")
        weekly = df.groupby("week").sum().reset_index()
        weekly.to_sql(f"{table_name}_weekly", conn, index=False, if_exists="replace")
        monthly = df.groupby("month").sum().reset_index()
        monthly.to_sql(f"{table_name}_monthly", conn, index=False, if_exists="replace")
        quarterly = df.groupby("quarter").sum().reset_index()
        quarterly.to_sql(f"{table_name}_quarterly", conn, index=False, if_exists="replace")

# Load data into SQLite
def load_data_to_sqlite(file, conn):
    try:
        if file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(file)
            for sheet_name in excel_data.sheet_names:
                df = excel_data.parse(sheet_name)
                df = preprocess_data(df)
                table_name = sheet_name.lower().replace(" ", "_")
                df.to_sql(table_name, conn, index=False, if_exists="replace")
                create_aggregation_tables(df, table_name, conn)
        elif file.name.endswith(".csv"):
            df = pd.read_csv(file)
            df = preprocess_data(df)
            table_name = file.name.lower().replace(".csv", "").replace(" ", "_")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            create_aggregation_tables(df, table_name, conn)
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return
        st.success("Data loaded successfully into SQLite database!")
    except Exception as e:
        st.error(f"Error loading data: {e}")

# Generate SQL Query
def generate_query(table, aggregation, metrics, sort, rows, conn):
    try:
        period_column = {"Daily": "date", "Weekly": "week", "Monthly": "month", "Quarterly": "quarter"}.get(aggregation)
        if not period_column:
            st.error("Invalid aggregation type selected.")
            return

        sort_order = "DESC" if sort == "Highest" else "ASC"
        query = f"""
            SELECT {period_column}, {', '.join(metrics)}
            FROM {table}_{aggregation.lower()}
            ORDER BY {metrics[0]} {sort_order}
            LIMIT {rows}
        """
        st.info(f"Generated Query:\n{query}")
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error executing query: {e}")
        return None

# Main app logic
def main():
    uploaded_file = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to get started.")
        return

    conn = sqlite3.connect(DATABASE)
    load_data_to_sqlite(uploaded_file, conn)

    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)["name"].tolist()

    if not tables:
        st.error("No tables found in the database.")
        return

    selected_table = st.selectbox("Select a table to analyze:", tables)
    columns = pd.read_sql_query(f"PRAGMA table_info({selected_table});", conn)["name"].tolist()

    if "date" in columns:
        aggregation_type = st.selectbox("Select aggregation type:", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
    else:
        aggregation_type = None
        st.warning("Date-based aggregation options are disabled as the table has no 'date' column.")

    metrics = st.multiselect("Select metrics to analyze:", columns)
    sort_option = st.selectbox("Sort By:", ["Highest", "Lowest"])
    rows_to_display = st.number_input("Number of rows to display:", min_value=1, max_value=100, value=10)

    if aggregation_type == "Custom":
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")

    if st.button("Generate Report"):
        if metrics:
            if aggregation_type == "Custom":
                query = f"""
                    SELECT date, {', '.join(metrics)}
                    FROM {selected_table}
                    WHERE date BETWEEN '{start_date}' AND '{end_date}'
                    ORDER BY {metrics[0]} {'DESC' if sort_option == 'Highest' else 'ASC'}
                    LIMIT {rows_to_display}
                """
            else:
                result = generate_query(selected_table, aggregation_type, metrics, sort_option, rows_to_display, conn)
            if result is not None:
                st.dataframe(result)
        else:
            st.error("Please select at least one metric to analyze.")

if __name__ == "__main__":
    main()
