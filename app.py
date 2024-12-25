# App Version: 1.5.3
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta

DATABASE = ":memory:"

st.title("Data Autobot")
st.subheader("Analyze Your Data with Ease")
st.write("**App Version:** 1.5.3")

def preprocess_data(df):
    """Preprocess the DataFrame by cleaning column names and ensuring correct types."""
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def create_aggregation_tables(df, table_name, conn):
    """Create aggregation tables (daily, weekly, monthly, quarterly) from the base DataFrame."""
    if "date" in df.columns:
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()

        if numeric_columns:
            df.to_sql(f"{table_name}_daily", conn, index=False, if_exists="replace")
            weekly = df.groupby("week")[numeric_columns].sum().reset_index()
            weekly.to_sql(f"{table_name}_weekly", conn, index=False, if_exists="replace")
            monthly = df.groupby("month")[numeric_columns].sum().reset_index()
            monthly.to_sql(f"{table_name}_monthly", conn, index=False, if_exists="replace")
            quarterly = df.groupby("quarter")[numeric_columns].sum().reset_index()
            quarterly.to_sql(f"{table_name}_quarterly", conn, index=False, if_exists="replace")
        else:
            st.warning(f"No numeric columns found for {table_name}. Skipping aggregation.")
    else:
        st.error(f"Table '{table_name}' does not contain a 'date' column for aggregation.")

def load_data_to_sqlite(file, conn):
    """Load data from uploaded file into SQLite and create aggregation tables if applicable."""
    try:
        if file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(file)
            for sheet_name in excel_data.sheet_names:
                df = preprocess_data(excel_data.parse(sheet_name))
                table_name = sheet_name.lower().replace(" ", "_")
                df.to_sql(table_name, conn, index=False, if_exists="replace")
                create_aggregation_tables(df, table_name, conn)
        elif file.name.endswith(".csv"):
            df = preprocess_data(pd.read_csv(file))
            table_name = file.name.lower().replace(".csv", "").replace(" ", "_")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            create_aggregation_tables(df, table_name, conn)
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
    except Exception as e:
        st.error(f"Error loading data: {e}")

def generate_comparison_query(df, compare_type, selected_periods, metric):
    """Generate SQL query for comparison based on user input."""
    queries = []
    for period in selected_periods:
        queries.append(f"SELECT SUM({metric}) as total, '{period}' as period FROM {df} WHERE {compare_type} = '{period}'")
    return " UNION ALL ".join(queries)

def main():
    """Main function to handle the app flow."""
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
    st.write(f"Selected Table: {selected_table}")

    columns_info = pd.read_sql_query(f"PRAGMA table_info({selected_table});", conn)
    columns = columns_info["name"].tolist()
    
    if "date" in columns:
        aggregation_type = st.selectbox("Select aggregation type:", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
        metric = st.selectbox("Select metric to analyze:", [col for col in columns if pd.api.types.is_numeric_dtype(columns_info.loc[columns_info['name'] == col, 'type'])])
        
        if aggregation_type == "Custom":
            start_date = st.date_input("Start date:")
            end_date = st.date_input("End date:")
            if start_date and end_date:
                query = f"SELECT date, {metric} FROM {selected_table}_daily WHERE date BETWEEN '{start_date}' AND '{end_date}' ORDER BY {metric} DESC LIMIT 10"
        else:
            query = f"SELECT {aggregation_type.lower()}, {metric} FROM {selected_table}_{aggregation_type.lower()} ORDER BY {metric} DESC LIMIT 10"
    else:
        aggregation_type = None
        metric = st.selectbox("Select metric to analyze:", [col for col in columns if pd.api.types.is_numeric_dtype(columns_info.loc[columns_info['name'] == col, 'type'])])
        query = f"SELECT {', '.join(columns)}, {metric} FROM {selected_table} ORDER BY {metric} DESC LIMIT 10"
    
    if st.button("Generate"):
        try:
            result_df = pd.read_sql_query(query, conn)
            st.dataframe(result_df)
        except Exception as e:
            st.error(f"Error executing query: {e}")

    if st.checkbox("Enable Comparison"):
        compare_type = st.selectbox("Compare by:", ["Weekly", "Monthly", "Quarterly"])
        periods = sorted(pd.read_sql_query(f"SELECT DISTINCT {compare_type.lower()} FROM {selected_table}_{compare_type.lower()}", conn)[compare_type.lower()])
        selected_periods = st.multiselect("Select periods to compare:", periods)
        metric = st.selectbox("Select metric to compare:", [col for col in columns if pd.api.types.is_numeric_dtype(columns_info.loc[columns_info['name'] == col, 'type'])])

        if st.button("Compare"):
            if len(selected_periods) == 2:
                comparison_query = generate_comparison_query(selected_table, compare_type.lower(), selected_periods, metric)
                try:
                    comparison_result = pd.read_sql_query(comparison_query, conn)
                    comparison_result["Change (%)"] = (
                        (comparison_result["total"].iloc[1] - comparison_result["total"].iloc[0])
                        / comparison_result["total"].iloc[0]
                        * 100
                    ).round(2)
                    st.dataframe(comparison_result)
                except Exception as e:
                    st.error(f"Error executing comparison query: {e}")
            else:
                st.warning("Please select exactly two periods for comparison.")

if __name__ == "__main__":
    main()
