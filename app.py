import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

def clean_table_name(name):
    return name.strip().replace(" ", "_").lower()

def preprocess_data(df):
    df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def create_aggregations(df, table_name, conn):
    if "date" in df.columns:
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        df["week"] = df["date"].dt.to_period("W").astype(str)
        
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        
        for period, agg_name in [("week", f"{table_name}_weekly"),
                                 ("month", f"{table_name}_monthly"),
                                 ("quarter", f"{table_name}_quarterly")]:
            agg_df = df.groupby(period).sum(numeric_only=True).reset_index()
            agg_df.to_sql(agg_name, conn, index=False, if_exists="replace")
    else:
        df.to_sql(table_name, conn, index=False, if_exists="replace")

def fetch_schema(table_name, conn):
    schema_query = f"PRAGMA table_info({table_name});"
    schema_info = pd.read_sql_query(schema_query, conn)
    return schema_info["name"].tolist()

def main():
    st.title("Data Autobot - Analyze and Compare")
    
    uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["xlsx", "csv"])
    
    if uploaded_file:
        try:
            conn = sqlite3.connect(":memory:")
            table_names = []

            if uploaded_file.name.endswith(".xlsx"):
                excel_data = pd.ExcelFile(uploaded_file)
                for sheet in excel_data.sheet_names:
                    df = excel_data.parse(sheet)
                    df = preprocess_data(df)
                    table_name = clean_table_name(sheet)
                    create_aggregations(df, table_name, conn)
                    table_names.append(table_name)
            elif uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
                df = preprocess_data(df)
                table_name = clean_table_name(uploaded_file.name.replace(".csv", ""))
                create_aggregations(df, table_name, conn)
                table_names.append(table_name)

            st.success("File successfully processed and saved to the database!")
            selected_table = st.selectbox("Select a Table for Analysis", table_names)

            if selected_table:
                available_columns = fetch_schema(selected_table, conn)
                if "date" in available_columns:
                    st.write("### Aggregation Options")
                    period = st.selectbox("Select Aggregation Period", ["Original", "Weekly", "Monthly", "Quarterly"])
                    if period != "Original":
                        selected_table = f"{selected_table}_{period.lower()}"

                st.write("### Query Builder")
                if available_columns:
                    selected_columns = st.multiselect("Select Columns to Display", available_columns, default=available_columns)
                    limit = st.number_input("Number of Records to Display", min_value=1, max_value=100, value=10)
                    
                    sql_query = f"SELECT {', '.join(selected_columns)} FROM {selected_table} LIMIT {limit}"
                    st.write("Generated Query:", sql_query)
                    query_result = pd.read_sql_query(sql_query, conn)
                    st.dataframe(query_result)

                    # Comparison Options
                    st.write("### Comparison Mode")
                    comparison_toggle = st.checkbox("Enable Comparison")
                    if comparison_toggle:
                        compare_period = st.radio("Compare by", ["Weekly", "Monthly", "Quarterly"])
                        compare_table = f"{selected_table}_{compare_period.lower()}"
                        compare_options = pd.read_sql_query(f"SELECT DISTINCT {compare_period.lower()} FROM {compare_table}", conn)[compare_period.lower()]
                        
                        if len(compare_options) > 1:
                            period1 = st.selectbox("Select First Period", compare_options)
                            period2 = st.selectbox("Select Second Period", compare_options)
                            
                            if period1 and period2:
                                comparison_query = f"""
                                SELECT SUM(impressions_total) as total, '{period1}' as period 
                                FROM {compare_table} WHERE {compare_period.lower()} = '{period1}'
                                UNION ALL
                                SELECT SUM(impressions_total) as total, '{period2}' as period 
                                FROM {compare_table} WHERE {compare_period.lower()} = '{period2}'
                                """
                                st.write("Generated Comparison Query:", comparison_query)
                                comparison_result = pd.read_sql_query(comparison_query, conn)
                                comparison_result["change_%"] = comparison_result["total"].pct_change() * 100
                                st.dataframe(comparison_result)
                        else:
                            st.warning("Not enough data for comparison.")
                else:
                    st.warning("No columns available for selection.")
        except Exception as e:
            st.error(f"Error loading file: {e}")
    else:
        st.info("Please upload a file to begin analysis.")

if __name__ == "__main__":
    main()
