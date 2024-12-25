# App Version: 1.3.0
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

DATABASE = "data_analysis.db"

def preprocess_column_names(columns):
    """Utility function to standardize column names."""
    return [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_") for col in columns]

def load_data_to_sqlite(uploaded_file, conn):
    """Load uploaded data into SQLite."""
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        df.columns = preprocess_column_names(df.columns)
        table_name = uploaded_file.name.lower().replace(".csv", "").replace(" ", "_").replace("-", "_")
        df.to_sql(table_name, conn, if_exists="replace", index=False)
    elif uploaded_file.name.endswith(".xlsx"):
        excel_data = pd.ExcelFile(uploaded_file)
        for sheet_name in excel_data.sheet_names:
            df = excel_data.parse(sheet_name)
            df.columns = preprocess_column_names(df.columns)
            table_name = sheet_name.lower().replace(" ", "_").replace("-", "_")
            df.to_sql(table_name, conn, if_exists="replace", index=False)
    st.success("Data successfully loaded into SQLite!")

def create_aggregations(table_name, conn):
    """Create aggregated tables for weekly, monthly, and quarterly data."""
    query = f"SELECT * FROM {table_name}"
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        for period in ["week", "month", "quarter"]:
            agg_table_name = f"{table_name}_{period}"
            agg_df = df.groupby(period).sum(numeric_only=True).reset_index()
            agg_df.to_sql(agg_table_name, conn, if_exists="replace", index=False)

        st.success(f"Aggregated tables created for '{table_name}': weekly, monthly, and quarterly.")
    else:
        st.warning(f"Table '{table_name}' does not contain a 'date' column. Skipping aggregation.")

def main():
    st.title("Data Analysis App with SQLite")
    st.markdown("Version 1.3.0")

    conn = sqlite3.connect(DATABASE)

    uploaded_file = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to start analysis.")
        return

    load_data_to_sqlite(uploaded_file, conn)

    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)["name"].tolist()
    if not tables:
        st.error("No tables found in the database.")
        return

    selected_table = st.selectbox("Select a table to analyze:", tables)
    if not selected_table:
        st.warning("Please select a table to continue.")
        return

    create_aggregations(selected_table, conn)

    columns_info = pd.read_sql_query(f"PRAGMA table_info({selected_table});", conn)
    columns = columns_info["name"].tolist()
    numeric_columns = [col for col in columns if col != "date"]

    if not numeric_columns:
        st.warning(f"No numeric columns found in the '{selected_table}' table for analysis.")
        return

    metric = st.selectbox("Select Metric to Analyze:", numeric_columns, disabled=not numeric_columns)

    aggregation_type = st.selectbox("Select aggregation type:", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
    sort_order = st.selectbox("Sort By:", ["Highest", "Lowest"])
    rows_to_display = st.selectbox("Number of rows to display:", [5, 10, 25, 50])

    if aggregation_type == "Custom":
        start_date = st.date_input("Start date:")
        end_date = st.date_input("End date:")
        if start_date and end_date:
            query = f"""
            SELECT date, {metric} FROM {selected_table} 
            WHERE date BETWEEN '{start_date}' AND '{end_date}' 
            ORDER BY {metric} {'DESC' if sort_order == 'Highest' else 'ASC'} 
            LIMIT {rows_to_display}
            """
    else:
        agg_table = f"{selected_table}_{aggregation_type.lower()}"
        query = f"""
        SELECT {aggregation_type.lower()}, {metric} 
        FROM {agg_table} 
        ORDER BY {metric} {'DESC' if sort_order == 'Highest' else 'ASC'} 
        LIMIT {rows_to_display}
        """

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
        compare_type = st.selectbox("Select comparison type:", ["Weekly", "Monthly", "Quarterly", "Custom"])
        if compare_type == "Custom":
            period1 = st.date_input("Select first custom period:")
            period2 = st.date_input("Select second custom period:")
            if st.button("Compare"):
                query = f"""
                SELECT SUM({metric}) as total, '{period1}' as period 
                FROM {selected_table} 
                WHERE date = '{period1}' 
                UNION ALL 
                SELECT SUM({metric}) as total, '{period2}' as period 
                FROM {selected_table} 
                WHERE date = '{period2}'
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
        else:
            agg_table = f"{selected_table}_{compare_type.lower()}"
            st.write(f"Comparison mode enabled: {compare_type}")

            try:
                periods = pd.read_sql_query(f"SELECT DISTINCT {compare_type.lower()} FROM {agg_table}", conn)
                period1 = st.selectbox("Select first period:", periods[compare_type.lower()])
                period2 = st.selectbox("Select second period:", periods[compare_type.lower()])

                if period1 and period2 and st.button("Compare"):
                    query = f"""
                    SELECT SUM({metric}) as total, '{period1}' as period 
                    FROM {agg_table} 
                    WHERE {compare_type.lower()} = '{period1}' 
                    UNION ALL 
                    SELECT SUM({metric}) as total, '{period2}' as period 
                    FROM {agg_table} 
                    WHERE {compare_type.lower()} = '{period2}'
                    """
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
