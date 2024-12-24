import streamlit as st
import pandas as pd
import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(filename="app.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

def preprocess_file(uploaded_file):
    """Preprocess uploaded file and return dataframe."""
    try:
        if uploaded_file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(uploaded_file)
            sheets = {sheet_name: pd.read_excel(excel_data, sheet_name=sheet_name) for sheet_name in excel_data.sheet_names}
        elif uploaded_file.name.endswith(".csv"):
            sheets = {"default": pd.read_csv(uploaded_file)}
        else:
            raise ValueError("Unsupported file format.")
        return sheets
    except Exception as e:
        logger.error(f"Error preprocessing file: {e}")
        st.error("Error reading the file. Ensure it's a valid CSV or Excel file.")
        return None

def create_aggregations_with_quarters(df, table_name, conn):
    """Add 'quarter' column and create weekly, monthly, and quarterly aggregations."""
    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])  # Drop rows where the 'date' could not be converted
            df["quarter"] = df["date"].dt.to_period("Q").astype(str)  # Adds Q1 2024, etc.

            # Save raw table with quarter information
            df.to_sql(f"{table_name}_raw", conn, index=False, if_exists="replace")

            # Weekly aggregation
            df_weekly = df.groupby(df["date"].dt.to_period("W")).sum(numeric_only=True).reset_index()
            df_weekly["date"] = df_weekly["date"].dt.start_time
            df_weekly.to_sql(f"{table_name}_weekly", conn, index=False, if_exists="replace")

            # Monthly aggregation
            df_monthly = df.groupby(df["date"].dt.to_period("M")).sum(numeric_only=True).reset_index()
            df_monthly["date"] = df_monthly["date"].dt.start_time
            df_monthly.to_sql(f"{table_name}_monthly", conn, index=False, if_exists="replace")

            # Quarterly aggregation
            df_quarterly = df.groupby("quarter").sum(numeric_only=True).reset_index()
            df_quarterly.to_sql(f"{table_name}_quarterly", conn, index=False, if_exists="replace")
        except Exception as e:
            logger.error(f"Error creating aggregations for table '{table_name}': {e}")
            st.error(f"Error creating aggregations for table '{table_name}'.")
    else:
        logger.warning(f"Table '{table_name}' does not have a 'date' column for aggregation.")
        st.warning(f"Table '{table_name}' does not have a 'date' column for aggregation.")

def main():
    st.title("Data Analysis Autobot")

    uploaded_file = st.file_uploader("Upload your file", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to start analysis.")
        return

    conn = sqlite3.connect(":memory:")

    # Preprocess file and load data into SQLite
    sheets = preprocess_file(uploaded_file)
    if not sheets:
        return

    st.success("File successfully processed and saved to the database!")
    table_names = []
    for sheet_name, df in sheets.items():
        try:
            df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
            df.to_sql(sheet_name, conn, index=False, if_exists="replace")
            table_names.append(sheet_name)

            # Create aggregations
            create_aggregations_with_quarters(df, sheet_name, conn)
        except Exception as e:
            logger.error(f"Error processing sheet {sheet_name}: {e}")
            st.error(f"Error processing sheet {sheet_name}.")

    # Dropdown for table selection
    selected_table = st.selectbox("Select a table for analysis:", table_names)
    if not selected_table:
        st.warning("No table selected.")
        return

    # Dropdown for date ranges and comparison
    date_range = st.selectbox("Select Date Range", ["Weekly", "Monthly", "Quarterly", "Custom"])
    compare = st.checkbox("Comparison Mode")
    date_start, date_end = None, None

    if date_range == "Custom":
        date_start = st.date_input("Start Date")
        date_end = st.date_input("End Date")

    # Dropdown for columns to include
    columns_query = f"PRAGMA table_info({selected_table});"
    columns_info = pd.read_sql_query(columns_query, conn)
    columns_list = [col["name"] for col in columns_info.to_dict(orient="records")]

    selected_columns = st.multiselect("Select columns for analysis:", columns_list, default=columns_list[:3])

    # Dropdown for number of rows
    num_rows = st.selectbox("Number of rows to display:", [5, 10, 25, 50])

    if st.button("Run Analysis"):
        if not selected_columns:
            st.error("Please select at least one column.")
            return

        try:
            where_clause = ""
            if date_range == "Custom" and date_start and date_end:
                where_clause = f"WHERE date BETWEEN '{date_start}' AND '{date_end}'"
            elif date_range in ["Weekly", "Monthly", "Quarterly"]:
                table_suffix = date_range.lower()
                selected_table += f"_{table_suffix}"

            order_by_column = selected_columns[-1] if selected_columns else "id"
            sql_query = f"SELECT {', '.join(selected_columns)} FROM {selected_table} {where_clause} ORDER BY {order_by_column} DESC LIMIT {num_rows}"
            st.info(f"Generated Query: {sql_query}")

            df_result = pd.read_sql_query(sql_query, conn)
            st.write("### Query Results")
            st.dataframe(df_result)
        except Exception as e:
            logger.error(f"Error running query: {e}")
            st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
