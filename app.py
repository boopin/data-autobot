import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
from datetime import datetime, timedelta

def load_data(file):
    """Load Excel/CSV file into DuckDB."""
    if file.name.endswith('.xlsx'):
        excel_data = pd.ExcelFile(file)
        table_names = []
        for sheet_name in excel_data.sheet_names:
            df = excel_data.parse(sheet_name)
            df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
            conn.sql(f"CREATE OR REPLACE TABLE {sheet_name.lower()} AS SELECT * FROM df")
            table_names.append(sheet_name.lower())
    elif file.name.endswith('.csv'):
        df = pd.read_csv(file)
        df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
        table_name = file.name.lower().replace(".csv", "").replace(" ", "_")
        conn.sql(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
        return [table_name]
    return table_names

def create_aggregations(table_name):
    """Generate weekly, monthly, quarterly aggregations."""
    df = conn.sql(f"SELECT * FROM {table_name}").df()
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df['week'] = df['date'].dt.to_period('W').apply(str)
        df['month'] = df['date'].dt.to_period('M').apply(str)
        df['quarter'] = df['date'].dt.to_period('Q').apply(str)
        conn.sql(f"CREATE OR REPLACE TABLE {table_name}_weekly AS SELECT * FROM df")
        conn.sql(f"CREATE OR REPLACE TABLE {table_name}_monthly AS SELECT * FROM df")
        conn.sql(f"CREATE OR REPLACE TABLE {table_name}_quarterly AS SELECT * FROM df")
    else:
        st.warning(f"Table {table_name} does not have a date column. Aggregations skipped.")

def render_comparison():
    """Render comparison options for weekly/monthly/quarterly selections."""
    agg_level = st.selectbox("Select comparison level", ["Weekly", "Monthly", "Quarterly"])
    table = st.selectbox("Select table for comparison", table_names)
    if agg_level.lower() in table:
        first_period = st.selectbox("Select first period", conn.sql(f"SELECT DISTINCT {agg_level.lower()} FROM {table}_{agg_level.lower()}").df()[agg_level.lower()])
        second_period = st.selectbox("Select second period", conn.sql(f"SELECT DISTINCT {agg_level.lower()} FROM {table}_{agg_level.lower()}").df()[agg_level.lower()])
        if st.button("Compare"):
            compare_query = f"""
                SELECT '{first_period}' AS period, SUM(impressions_total) AS total FROM {table}_{agg_level.lower()} WHERE {agg_level.lower()} = '{first_period}'
                UNION ALL
                SELECT '{second_period}' AS period, SUM(impressions_total) AS total FROM {table}_{agg_level.lower()} WHERE {agg_level.lower()} = '{second_period}'
            """
            comparison_df = conn.sql(compare_query).df()
            comparison_df['percentage_change'] = comparison_df['total'].pct_change() * 100
            st.write(comparison_df)

def main():
    st.title("Data Autobot with DuckDB")
    uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file.")
        return

    global conn, table_names
    conn = duckdb.connect(database=":memory:")
    table_names = load_data(uploaded_file)

    st.success("File successfully processed!")
    selected_table = st.selectbox("Select a table for analysis", table_names)

    if "date" in conn.sql(f"PRAGMA table_info('{selected_table}')").df()["column_name"].values:
        create_aggregations(selected_table)
        render_comparison()
    else:
        st.warning("This table does not support date-based aggregations.")

    # Render columns dynamically
    st.write("### Select columns for analysis")
    columns = conn.sql(f"PRAGMA table_info('{selected_table}')").df()["column_name"].values
    selected_columns = st.multiselect("Select columns to display", columns)
    if selected_columns:
        st.dataframe(conn.sql(f"SELECT {', '.join(selected_columns)} FROM {selected_table} LIMIT 10").df())
