import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px
import logging

# Configure logging
logging.basicConfig(filename="workflow.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

def create_aggregations_with_quarters(df, table_name, conn):
    """Add 'quarter' column and create weekly, monthly, and quarterly aggregations."""
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)  # Adds Q1 2024, etc.

        # Save raw table with quarter information
        df.to_sql(f"{table_name}_raw", conn, index=False, if_exists="replace")

        # Weekly aggregation
        df_weekly = df.groupby(df["date"].dt.to_period("W")).sum().reset_index()
        df_weekly.to_sql(f"{table_name}_weekly", conn, index=False, if_exists="replace")

        # Monthly aggregation
        df_monthly = df.groupby(df["date"].dt.to_period("M")).sum().reset_index()
        df_monthly.to_sql(f"{table_name}_monthly", conn, index=False, if_exists="replace")

        # Quarterly aggregation
        df_quarterly = df.groupby("quarter").sum().reset_index()
        df_quarterly.to_sql(f"{table_name}_quarterly", conn, index=False, if_exists="replace")
    else:
        st.warning(f"Table '{table_name}' does not have a 'date' column for aggregation.")

def main():
    st.title("Data AutoBot with Comparison and Time Period Analysis")

    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to start analysis.")
        return

    try:
        conn = sqlite3.connect(":memory:")
        table_names = []

        # Load file and process
        if uploaded_file.name.endswith('.xlsx'):
            excel_data = pd.ExcelFile(uploaded_file)
            for sheet in excel_data.sheet_names:
                df = pd.read_excel(excel_data, sheet_name=sheet)
                table_name = sheet.lower().replace(" ", "_")
                create_aggregations_with_quarters(df, table_name, conn)
                table_names.append(table_name)

        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            table_name = uploaded_file.name.replace(".csv", "").lower().replace(" ", "_")
            create_aggregations_with_quarters(df, table_name, conn)
            table_names.append(table_name)

        else:
            st.error("Unsupported file type. Please upload a CSV or Excel file.")
            return

        st.success("File successfully processed and saved to the database!")

        # Select table for analysis
        selected_table = st.selectbox("Select a table to analyze:", table_names)

        # Date range selection
        st.write("### Select Time Period")
        period_type = st.radio("Time Period", ["Weekly", "Monthly", "Quarterly", "Custom"], index=2)
        compare_toggle = st.checkbox("Enable Comparison")

        if period_type == "Custom":
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date")
            with col2:
                end_date = st.date_input("End Date")

        # Run comparison or analysis
        if compare_toggle:
            st.write("### Comparison Settings")
            col1, col2 = st.columns(2)
            with col1:
                period_1 = st.selectbox("Select First Period:", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"])
            with col2:
                period_2 = st.selectbox("Select Second Period:", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"])

            query_1 = f"SELECT SUM(impressions_total) as total, '{period_1}' as period FROM {selected_table}_quarterly WHERE quarter = '{period_1}'"
            query_2 = f"SELECT SUM(impressions_total) as total, '{period_2}' as period FROM {selected_table}_quarterly WHERE quarter = '{period_2}'"
            combined_query = f"{query_1} UNION ALL {query_2}"
            result = pd.read_sql_query(combined_query, conn)
            result["percentage_change"] = result["total"].pct_change().fillna(0) * 100
            st.write("### Comparison Results")
            st.dataframe(result)
        else:
            # Normal query without comparison
            if period_type == "Weekly":
                period_table = f"{selected_table}_weekly"
            elif period_type == "Monthly":
                period_table = f"{selected_table}_monthly"
            elif period_type == "Quarterly":
                period_table = f"{selected_table}_quarterly"
            elif period_type == "Custom":
                period_table = f"{selected_table}_raw"
                query_filter = f"WHERE date BETWEEN '{start_date}' AND '{end_date}'"
            else:
                period_table = f"{selected_table}_raw"

            # Dynamic column selection
            columns_query = f"PRAGMA table_info({period_table});"
            columns_info = pd.read_sql_query(columns_query, conn)["name"].tolist()
            selected_columns = st.multiselect("Select columns to display:", columns_info, default=columns_info[:5])

            # Generate SQL Query
            query = f"SELECT {', '.join(selected_columns)} FROM {period_table}"
            if period_type == "Custom":
                query += f" {query_filter}"
            query += " LIMIT 10"
            st.info(f"Generated Query: {query}")
            result = pd.read_sql_query(query, conn)
            st.write("### Query Results")
            st.dataframe(result)

    except Exception as e:
        st.error(f"Error: {e}")
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()
