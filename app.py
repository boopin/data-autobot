import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

# Create Aggregations for Weekly, Monthly, and Quarterly
def create_aggregations(df, table_name, conn):
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Convert datetime to periods
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["week"] = df["date"].dt.strftime("%U")
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        # Select numeric columns for aggregation
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()

        # Aggregations
        df_weekly = df.groupby(["week"])[numeric_columns].sum().reset_index()
        df_monthly = df.groupby(["month"])[numeric_columns].sum().reset_index()
        df_quarterly = df.groupby(["quarter"])[numeric_columns].sum().reset_index()

        # Save results to database
        df_weekly.to_sql(f"{table_name}_weekly", conn, if_exists="replace", index=False)
        df_monthly.to_sql(f"{table_name}_monthly", conn, if_exists="replace", index=False)
        df_quarterly.to_sql(f"{table_name}_quarterly", conn, if_exists="replace", index=False)

# Main App Functionality
def main():
    st.title("Data Analysis Dashboard with Comparison")

    uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "csv"])
    if not uploaded_file:
        st.info("Please upload a file to get started.")
        return

    try:
        conn = sqlite3.connect(":memory:")
        table_names = []

        if uploaded_file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(uploaded_file)
            for sheet_name in excel_data.sheet_names:
                df = pd.read_excel(excel_data, sheet_name=sheet_name)
                df.columns = [col.lower().replace(" ", "_").replace("-", "_") for col in df.columns]
                table_name = sheet_name.lower().replace(" ", "_")
                df.to_sql(table_name, conn, if_exists="replace", index=False)
                create_aggregations(df, table_name, conn)
                table_names.append(table_name)
        elif uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            df.columns = [col.lower().replace(" ", "_").replace("-", "_") for col in df.columns]
            table_name = uploaded_file.name.split(".")[0].lower().replace(" ", "_")
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            create_aggregations(df, table_name, conn)
            table_names.append(table_name)
        else:
            st.error("Unsupported file type. Please upload an Excel or CSV file.")

        st.success("File successfully processed!")

        selected_table = st.selectbox("Select a table for analysis", table_names)

        date_range = st.selectbox("Select Date Range", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
        comparison_mode = st.checkbox("Enable Comparison")

        if comparison_mode:
            st.subheader("Select Periods for Comparison")
            period_1 = st.selectbox("Select First Period", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"])
            period_2 = st.selectbox("Select Second Period", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"])

        if date_range == "Custom":
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")

        columns_query = f"PRAGMA table_info({selected_table});"
        columns_info = pd.read_sql(columns_query, conn)
        available_columns = [col["name"] for col in columns_info.to_dict(orient="records")]

        selected_columns = st.multiselect("Select Columns for Analysis", available_columns)
        order_column = st.selectbox("Select Column to Sort By", available_columns)
        limit = st.selectbox("Limit Results To", [5, 10, 25, 50, 100])

        if st.button("Run Analysis"):
            where_clause = ""
            if date_range == "Custom" and start_date and end_date:
                where_clause = f"WHERE date BETWEEN '{start_date}' AND '{end_date}'"

            # Fix table suffix for aggregated data
            table_suffix = {"Weekly": "_weekly", "Monthly": "_monthly", "Quarterly": "_quarterly"}.get(date_range, "")
            query_table = f"{selected_table}{table_suffix}"

            # Fix time column name for ordering
            time_column = "date" if date_range == "Daily" else ("month" if date_range == "Monthly" else "quarter" if date_range == "Quarterly" else "week")
            if date_range != "Custom" and time_column not in available_columns:
                st.error(f"The table does not support {date_range} aggregation.")
                return

            try:
                if comparison_mode:
                    sql_query_1 = f"SELECT SUM({order_column}) as total, '{period_1}' as period FROM {query_table} WHERE quarter = '{period_1}'"
                    sql_query_2 = f"SELECT SUM({order_column}) as total, '{period_2}' as period FROM {query_table} WHERE quarter = '{period_2}'"
                    st.info(f"Generated Queries:\n{sql_query_1}\n{sql_query_2}")

                    result_1 = pd.read_sql(sql_query_1, conn)
                    result_2 = pd.read_sql(sql_query_2, conn)

                    comparison_result = pd.concat([result_1, result_2])
                    st.write("### Comparison Results")
                    st.dataframe(comparison_result)
                else:
                    sql_query = f"SELECT {', '.join(selected_columns)} FROM {query_table} {where_clause} ORDER BY {order_column} DESC LIMIT {limit}"
                    st.info(f"Generated Query: {sql_query}")

                    result = pd.read_sql(sql_query, conn)
                    st.write("### Query Results")
                    st.dataframe(result)
            except Exception as e:
                st.error(f"Query Error: {e}")

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
