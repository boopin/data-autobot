import streamlit as st
import pandas as pd
import sqlite3
import re

# Helper functions
def normalize_column_names(df):
    """
    Normalize column names to lowercase and replace spaces/special characters.
    """
    df.columns = [
        re.sub(r"[^\w]+", "_", col.strip().lower().replace("(", "").replace(")", ""))
        for col in df.columns
    ]
    return df

def load_data_to_db(file):
    """
    Load uploaded file into an SQLite database, normalizing column names.
    """
    conn = sqlite3.connect(":memory:")
    table_names = []
    if file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(file)
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            df = normalize_column_names(df)
            table_name = sheet_name.lower().replace(" ", "_")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            table_names.append(table_name)
    elif file.name.endswith(".csv"):
        df = pd.read_csv(file)
        df = normalize_column_names(df)
        table_name = file.name.lower().replace(".csv", "").replace(" ", "_")
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        table_names.append(table_name)
    return conn, table_names

def get_schema(table_name, conn):
    """
    Retrieve normalized schema (columns) of a given table.
    """
    query = f"PRAGMA table_info({table_name})"
    schema_info = pd.read_sql_query(query, conn)
    return list(schema_info['name'])

def generate_query(selected_table, metric, sorting, aggregation, display_columns, date_filter=None, start_date=None, end_date=None):
    """
    Generate SQL query for analysis.
    """
    where_clause = ""
    if date_filter and start_date and end_date:
        where_clause = f"WHERE date BETWEEN '{start_date}' AND '{end_date}'"
    columns = ", ".join(display_columns + [metric])
    query = f"""
    SELECT {columns}
    FROM {selected_table}
    {where_clause}
    ORDER BY {metric} {sorting}
    LIMIT {aggregation};
    """
    return query.strip()

def generate_comparison_query(selected_table, metric, compare_type, period1, period2):
    """
    Generate SQL query for comparison.
    """
    query = f"""
    SELECT '{period1}' as period, SUM({metric}) as total
    FROM {selected_table}
    WHERE {compare_type} = '{period1}'
    UNION ALL
    SELECT '{period2}' as period, SUM({metric}) as total
    FROM {selected_table}
    WHERE {compare_type} = '{period2}';
    """
    return query.strip()

# Main app logic
def main():
    st.title("Data AutoBot - Enhanced Analytics")

    # File Upload
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to start.")
        return

    # Load data and create database
    conn, table_names = load_data_to_db(uploaded_file)

    # Select Table
    selected_table = st.selectbox("Select Table:", table_names)
    schema = get_schema(selected_table, conn)

    # Date-based Filtering
    if "date" in schema:
        st.write("### Date-Based Analysis")
        date_filter = st.selectbox("Date Filter:", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
        start_date, end_date = None, None
        if date_filter == "Custom":
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")

        # Metric-Based Filtering
        st.write("### Metric-Based Filtering")
        metric = st.selectbox("Metrics:", [col for col in schema if col != "date"])
        aggregation = st.selectbox("Rows to Display:", [5, 10, 25, 50])
        sorting = st.selectbox("Sorting:", ["DESC", "ASC"])
        display_columns = st.multiselect("Columns to Display:", schema, default=["date", metric])

        if st.button("Run Analysis"):
            query = generate_query(
                selected_table=selected_table,
                metric=metric,
                sorting=sorting,
                aggregation=aggregation,
                display_columns=display_columns,
                date_filter=date_filter,
                start_date=start_date,
                end_date=end_date,
            )
            try:
                result = pd.read_sql_query(query, conn)
                st.write("### Analysis Results")
                st.dataframe(result)
            except Exception as e:
                st.error(f"Error executing query: {e}")

        # Comparison Mode
        if st.checkbox("Enable Comparison"):
            compare_type = st.selectbox("Comparison Type:", ["Weekly", "Monthly", "Quarterly"])
            periods = [p for p in schema if p.startswith(compare_type.lower())]
            period1 = st.selectbox(f"Select {compare_type} Period 1:", periods)
            period2 = st.selectbox(f"Select {compare_type} Period 2:", periods)
            if st.button("Run Comparison"):
                compare_query = generate_comparison_query(selected_table, metric, compare_type.lower(), period1, period2)
                try:
                    comparison_result = pd.read_sql_query(compare_query, conn)
                    comparison_result["Percentage Change"] = (
                        (comparison_result.iloc[1]["total"] - comparison_result.iloc[0]["total"])
                        / comparison_result.iloc[0]["total"]
                    ) * 100
                    st.write("### Comparison Results")
                    st.dataframe(comparison_result)
                except Exception as e:
                    st.error(f"Error executing comparison query: {e}")

    else:
        # Non-date tables
        st.write("### Metric-Based Filtering for Non-Date Tables")
        metric = st.selectbox("Metrics:", schema)
        aggregation = st.selectbox("Rows to Display:", [5, 10, 25, 50])
        sorting = st.selectbox("Sorting:", ["DESC", "ASC"])
        display_columns = st.multiselect("Columns to Display:", schema, default=[metric])

        if st.button("Run Analysis"):
            query = generate_query(
                selected_table=selected_table,
                metric=metric,
                sorting=sorting,
                aggregation=aggregation,
                display_columns=display_columns,
            )
            try:
                result = pd.read_sql_query(query, conn)
                st.write("### Analysis Results")
                st.dataframe(result)
            except Exception as e:
                st.error(f"Error executing query: {e}")

if __name__ == "__main__":
    main()
