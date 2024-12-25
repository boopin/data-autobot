# App Version: 1.2.0
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

DATABASE = "data_analysis.db"

# Utility function to preprocess column names
def preprocess_column_names(columns):
    return [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_") for col in columns]

# Function to load data into SQLite
def load_data_to_sqlite(uploaded_file, conn):
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith(".xlsx"):
        df = pd.ExcelFile(uploaded_file)
        for sheet in df.sheet_names:
            data = df.parse(sheet)
            data.columns = preprocess_column_names(data.columns)
            table_name = sheet.lower().replace(" ", "_").replace("-", "_")
            data.to_sql(table_name, conn, if_exists="replace", index=False)
    st.success("Data successfully loaded into SQLite!")

# Function to create aggregated tables
def create_aggregations(table_name, conn):
    query = f"SELECT * FROM {table_name}"
    df = pd.read_sql_query(query, conn)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        for period in ["week", "month", "quarter"]:
            agg_df = df.groupby(period).sum(numeric_only=True).reset_index()
            agg_table_name = f"{table_name}_{period}"
            agg_df.to_sql(agg_table_name, conn, if_exists="replace", index=False)
    else:
        st.warning(f"The table '{table_name}' does not have a 'date' column for aggregation.")

# Main Streamlit app
def main():
    st.title("Data Analysis App with SQLite")
    st.markdown("Version 1.2.0")

    uploaded_file = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to start analysis.")
        return

    conn = sqlite3.connect(DATABASE)
    load_data_to_sqlite(uploaded_file, conn)

    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)["name"].tolist()
    if not tables:
        st.error("No tables found in the database.")
        return

    selected_table = st.selectbox("Select a table to analyze:", tables)
    st.write(f"Selected Table: {selected_table}")

    columns_info = pd.read_sql_query(f"PRAGMA table_info({selected_table});", conn)
    columns = columns_info["name"].tolist()
    numeric_columns = [col for col in columns if col != "date"]

    if not numeric_columns:
        st.warning(f"No numeric columns found in the '{selected_table}' table for analysis.")
        return

    metric = st.selectbox("Select Metric to Analyze:", numeric_columns, disabled=not numeric_columns)

    if metric:
        aggregation_type = st.selectbox("Select aggregation type:", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
        if aggregation_type == "Custom":
            start_date = st.date_input("Start date:")
            end_date = st.date_input("End date:")
            if start_date and end_date:
                query = f"SELECT date, {metric} FROM {selected_table}_daily WHERE date BETWEEN '{start_date}' AND '{end_date}' ORDER BY {metric} DESC LIMIT 10"
        else:
            query = f"SELECT {aggregation_type.lower()}, {metric} FROM {selected_table}_{aggregation_type.lower()} ORDER BY {metric} DESC LIMIT 10"

        if st.button("Generate"):
            try:
                result_df = pd.read_sql_query(query, conn)
                st.dataframe(result_df)

                if st.checkbox("Show as Chart"):
                    fig = px.bar(result_df, x=aggregation_type.lower(), y=metric, title=f"{metric} Analysis")
                    st.plotly_chart(fig)

            except Exception as e:
                st.error(f"Error executing query: {e}")

    if st.checkbox("Enable Comparison"):
        compare_type = st.selectbox("Select comparison type:", ["Weekly", "Monthly", "Quarterly"])
        if compare_type:
            st.write(f"Comparison mode enabled: {compare_type}")
            options = sorted(df[compare_type.lower()].unique())
            period1 = st.selectbox("Select first period:", options)
            period2 = st.selectbox("Select second period:", options)

            if period1 and period2 and st.button("Compare"):
                query = f"""
                SELECT SUM({metric}) as total, '{period1}' as period FROM {selected_table}_{compare_type.lower()} WHERE {compare_type.lower()} = '{period1}'
                UNION ALL
                SELECT SUM({metric}) as total, '{period2}' as period FROM {selected_table}_{compare_type.lower()} WHERE {compare_type.lower()} = '{period2}'
                """
                try:
                    comparison_df = pd.read_sql_query(query, conn)
                    comparison_df["Percentage Change"] = comparison_df["total"].pct_change() * 100
                    st.dataframe(comparison_df)

                    if st.checkbox("Show Comparison Chart"):
                        fig = px.bar(comparison_df, x="period", y="total", title=f"{metric} Comparison")
                        st.plotly_chart(fig)
                except Exception as e:
                    st.error(f"Error executing comparison query: {e}")

if __name__ == "__main__":
    main()
