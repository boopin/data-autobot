# App Version: 1.4.0
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

# Configure SQLite connection
DATABASE = ":memory:"

# Initialize Streamlit app
st.title("Data Autobot")
st.subheader("Analyze Your Data with Ease")

# Version control
st.write("**App Version:** 1.4.0")

# Utility function to clean column names
def clean_column_names(columns):
    return [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in columns]

# Utility function to preprocess data
def preprocess_data(df):
    df.columns = clean_column_names(df.columns)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

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
        elif file.name.endswith(".csv"):
            df = pd.read_csv(file)
            df = preprocess_data(df)
            table_name = file.name.lower().replace(".csv", "").replace(" ", "_")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return
        st.success("Data loaded successfully into SQLite database!")
    except Exception as e:
        st.error(f"Error loading data: {e}")

# Generate SQL Query for Comparison
def generate_comparison_query(table, compare_type, periods, metric):
    if len(periods) != 2:
        st.error("Please select exactly two periods for comparison.")
        return None

    query = f"""
        SELECT 
            SUM({metric}) as total, '{periods[0]}' as period
        FROM {table}_{compare_type.lower()}
        WHERE {compare_type.lower()} = '{periods[0]}'
        UNION ALL
        SELECT 
            SUM({metric}) as total, '{periods[1]}' as period
        FROM {table}_{compare_type.lower()}
        WHERE {compare_type.lower()} = '{periods[1]}'
    """
    return query

# Create and execute SQL queries
def generate_query(table, aggregation, metrics, sort, rows, conn):
    try:
        # Determine the period column
        if aggregation == "Daily":
            period_column = "date"
        elif aggregation == "Weekly":
            period_column = "week"
        elif aggregation == "Monthly":
            period_column = "month"
        elif aggregation == "Quarterly":
            period_column = "quarter"
        else:
            st.error("Invalid aggregation type selected.")
            return

        # Adjust sort option
        sort_order = "DESC" if sort == "Highest" else "ASC"

        # Construct the SQL query
        query = f"""
            SELECT {period_column}, {', '.join(metrics)}
            FROM {table}_{aggregation.lower()}
            ORDER BY {metrics[0]} {sort_order}
            LIMIT {rows}
        """
        st.info(f"Generated Query:\n{query}")

        # Execute the query
        result = pd.read_sql_query(query, conn)
        return result
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

    # Get tables from the database
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
    table_names = tables["name"].tolist()

    if not table_names:
        st.error("No tables found in the database.")
        return

    selected_table = st.selectbox("Select a table to analyze:", table_names)

    # Get column info for selected table
    try:
        columns = pd.read_sql_query(f"PRAGMA table_info({selected_table});", conn)
        column_names = columns["name"].tolist()
    except Exception as e:
        st.error(f"Error fetching table schema: {e}")
        return

    if "date" in column_names:
        aggregation_type = st.selectbox("Select aggregation type:", ["Daily", "Weekly", "Monthly", "Quarterly"])
    else:
        aggregation_type = None
        st.warning("Date-based aggregation options are disabled as the table has no 'date' column.")

    metrics = st.multiselect("Select metrics to analyze:", column_names)
    sort_option = st.selectbox("Sort By:", ["Highest", "Lowest"])
    rows_to_display = st.number_input("Number of rows to display:", min_value=1, max_value=100, value=10)

    comparison_mode = st.checkbox("Enable Comparison")
    if comparison_mode:
        compare_type = st.selectbox("Compare by:", ["Weekly", "Monthly", "Quarterly"])
        comparison_periods = st.multiselect(f"Select two {compare_type.lower()} periods to compare:", [])
        if st.button("Run Comparison"):
            if metrics:
                query = generate_comparison_query(selected_table, compare_type, comparison_periods, metrics[0])
                if query:
                    try:
                        result = pd.read_sql_query(query, conn)
                        result["percentage_change"] = (
                            (result.iloc[1]["total"] - result.iloc[0]["total"]) / result.iloc[0]["total"]
                        ) * 100
                        st.write("### Comparison Results")
                        st.dataframe(result)

                        # Visualization toggle
                        show_graph = st.checkbox("Generate Graph")
                        if show_graph:
                            fig = px.bar(result, x="period", y="total", title="Comparison Results")
                            st.plotly_chart(fig)
                    except Exception as e:
                        st.error(f"Error executing comparison query: {e}")
            else:
                st.error("Please select at least one metric to analyze.")

    if st.button("Generate Report"):
        if metrics:
            result = generate_query(selected_table, aggregation_type, metrics, sort_option, rows_to_display, conn)
            if result is not None:
                st.write("### Analysis Results")
                st.dataframe(result)

                # Visualization toggle
                show_graph = st.checkbox("Generate Graph")
                if show_graph:
                    fig = px.bar(result, x="date", y=metrics[0], title="Analysis Results")
                    st.plotly_chart(fig)
        else:
            st.error("Please select at least one metric to analyze.")

if __name__ == "__main__":
    main()
