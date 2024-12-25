# App Version: 1.3.1
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Initialize SQLite connection
conn = sqlite3.connect(":memory:")

def preprocess_column_names(df):
    """Preprocess column names for database compatibility."""
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_") for col in df.columns]
    return df

def quote_table_name(table_name):
    """Safely quote table names to handle special characters or spaces."""
    return f'"{table_name}"'

def load_file(file):
    """Load and preprocess the uploaded file into the database."""
    try:
        if file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(file)
            for sheet_name in excel_data.sheet_names:
                df = pd.read_excel(excel_data, sheet_name=sheet_name)
                df = preprocess_column_names(df)
                create_aggregated_tables(df, sheet_name.lower().replace(" ", "_"))
        elif file.name.endswith(".csv"):
            df = pd.read_csv(file)
            df = preprocess_column_names(df)
            table_name = file.name.replace(".csv", "").lower().replace(" ", "_")
            create_aggregated_tables(df, table_name)
        st.success("File successfully processed and loaded into the database!")
    except Exception as e:
        st.error(f"Error loading file: {e}")

def create_aggregated_tables(df, table_name):
    """Create weekly, monthly, and quarterly aggregated tables."""
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        df.to_sql(table_name, conn, index=False, if_exists="replace")
        df.groupby("week").sum().reset_index().to_sql(f"{table_name}_weekly", conn, index=False, if_exists="replace")
        df.groupby("month").sum().reset_index().to_sql(f"{table_name}_monthly", conn, index=False, if_exists="replace")
        df.groupby("quarter").sum().reset_index().to_sql(f"{table_name}_quarterly", conn, index=False, if_exists="replace")
    else:
        df.to_sql(table_name, conn, index=False, if_exists="replace")

def get_distinct_periods(table_name, period_type):
    """Retrieve distinct period values for comparison dropdowns."""
    try:
        query = f"SELECT DISTINCT {period_type} FROM {table_name}"
        return pd.read_sql_query(query, conn)[period_type].tolist()
    except Exception as e:
        st.error(f"Error fetching periods: {e}")
        return []

def generate_comparison_query(table_name, metric, compare_type, period1, period2):
    """Generate SQL query for comparison between two periods."""
    quoted_table_name = quote_table_name(f"{table_name}_{compare_type.lower()}")
    query = f"""
    SELECT
        '{period1}' AS period, SUM({metric}) AS total
    FROM
        {quoted_table_name}
    WHERE
        {compare_type.lower()} = '{period1}'
    UNION ALL
    SELECT
        '{period2}' AS period, SUM({metric}) AS total
    FROM
        {quoted_table_name}
    WHERE
        {compare_type.lower()} = '{period2}'
    """
    return query

def main():
    st.title("Data Autobot: Analyze and Compare Data")
    uploaded_file = st.file_uploader("Upload your file (CSV or Excel)", type=["csv", "xlsx"])

    if uploaded_file:
        load_file(uploaded_file)

        # Retrieve available tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        available_tables = [row[0] for row in cursor.fetchall()]

        selected_table = st.selectbox("Select table to analyze:", available_tables)

        if selected_table:
            schema_query = f"PRAGMA table_info({quote_table_name(selected_table)})"
            schema_columns = pd.read_sql_query(schema_query, conn)["name"].tolist()

            if schema_columns:
                # Dynamic Dropdown for Metrics
                numeric_columns = [col for col in schema_columns if "int" in col or "real" in col]
                selected_metric = st.selectbox("Select metric to analyze:", numeric_columns if numeric_columns else ["No numeric columns available"])

                # Optional Columns to Display
                extra_columns = st.multiselect(
                    "Select additional columns to display:",
                    [col for col in schema_columns if col not in numeric_columns]
                )

                # Sort Options
                sort_order = st.radio("Sort order:", ["Highest", "Lowest"])
                sort_column = selected_metric if selected_metric != "No numeric columns available" else None

                # Number of Rows to Display
                num_rows = st.selectbox("Number of rows to display:", [5, 10, 25, 50])

                # Comparison Options
                enable_comparison = st.checkbox("Enable Comparison")
                if enable_comparison:
                    compare_type = st.selectbox("Select comparison type:", ["Weekly", "Monthly", "Quarterly", "Custom"])
                    if compare_type != "Custom":
                        periods = get_distinct_periods(f"{selected_table}_{compare_type.lower()}", compare_type.lower())
                        if periods:
                            period1 = st.selectbox("Select Period 1:", periods)
                            period2 = st.selectbox("Select Period 2:", periods)
                            if period1 and period2 and period1 != period2:
                                query = generate_comparison_query(selected_table, selected_metric, compare_type, period1, period2)
                                try:
                                    comparison_result = pd.read_sql_query(query, conn)
                                    comparison_result["Percentage Change (%)"] = (
                                        (comparison_result.iloc[1]["total"] - comparison_result.iloc[0]["total"]) / comparison_result.iloc[0]["total"]
                                    ) * 100
                                    st.write("### Comparison Results")
                                    st.dataframe(comparison_result)

                                    if st.checkbox("Generate Comparison Chart"):
                                        fig = px.bar(comparison_result, x="period", y="total", title="Comparison Chart")
                                        st.plotly_chart(fig)
                                except Exception as e:
                                    st.error(f"Error executing comparison query: {e}")
                    else:
                        st.warning("Custom comparison is not fully implemented yet.")

if __name__ == "__main__":
    main()
