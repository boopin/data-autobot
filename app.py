# App Version: 2.5.1
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import chardet

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'

def generate_visualization(results, metric):
    """Generate visualization for results."""
    if not results.empty:
        fig = px.bar(results, x=results.columns[0], y=metric, title=f"Visualization of {metric}")
        st.plotly_chart(fig)
    else:
        st.warning("No data available to generate visualization.")

def process_uploaded_file(uploaded_file):
    """Process uploaded file and store it in the database."""
    try:
        if uploaded_file.name.endswith(".csv"):
            # Detect encoding using chardet
            raw_data = uploaded_file.read()
            detected_encoding = chardet.detect(raw_data)["encoding"]
            st.info(f"Detected file encoding: {detected_encoding}")
            uploaded_file.seek(0)  # Reset file pointer
            df = pd.read_csv(uploaded_file, encoding=detected_encoding)
        else:
            df = pd.read_excel(uploaded_file, sheet_name=None)
        
        if isinstance(df, dict):
            st.write("Detected multiple sheets in the uploaded file.")
            for sheet_name, sheet_df in df.items():
                process_and_store(sheet_df, sheet_name)
        else:
            process_and_store(df, uploaded_file.name.split('.')[0])

        st.success("File successfully processed and saved to the database!")
    except UnicodeDecodeError as e:
        st.error(f"Error decoding file: {e}. Please upload a valid file.")
    except Exception as e:
        st.error(f"Error loading file: {e}")

def process_and_store(df, table_name):
    """Process the DataFrame and store it in the SQLite database with aggregations."""
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].notnull()]
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        save_aggregated_view(df, table_name, "week", "weekly")
        save_aggregated_view(df, table_name, "month", "monthly")
        save_aggregated_view(df, table_name, "quarter", "quarterly")

    df = df.drop_duplicates()
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    st.write(f"Table '{table_name}' created in the database with raw and aggregated views.")

def save_aggregated_view(df, table_name, period_col, suffix):
    """Save aggregated views by period."""
    try:
        if period_col in df.columns:
            agg_df = df.groupby(period_col).sum(numeric_only=True).reset_index()
            agg_table_name = f"{table_name}_{suffix}"
            agg_df.to_sql(agg_table_name, conn, if_exists="replace", index=False)
            st.write(f"Aggregated table '{agg_table_name}' created successfully.")
    except Exception as e:
        st.warning(f"Could not create aggregated table for '{suffix}': {e}")

def generate_analysis_ui():
    """Generate UI for data analysis."""
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)

    if selected_table:
        columns_query = f"PRAGMA table_info({quote_table_name(selected_table)});"
        schema = pd.read_sql_query(columns_query, conn)
        columns = schema["name"].tolist()

        st.write(f"Schema for '{selected_table}': {columns}")

        col1, col2, col3 = st.columns(3)

        with col1:
            selected_metric = st.selectbox("Select metric to analyze:", [col for col in columns if col != "date"])

        with col2:
            additional_columns = st.multiselect("Select additional columns:", [col for col in columns if col != selected_metric])

        with col3:
            sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
            row_limit = st.slider("Rows to display:", 5, 50, 10)

        if st.button("Run Analysis"):
            if selected_metric:
                run_analysis(selected_table, selected_metric, additional_columns, sort_order, row_limit)
            else:
                st.warning("Please select a metric to analyze.")

        generate_comparison_ui(selected_table)

def generate_comparison_ui(table_name):
    """Generate UI for enabling and running comparisons."""
    st.subheader("Enable Comparison")
    enable_comparison = st.checkbox("Toggle Comparison")

    if enable_comparison:
        col1, col2 = st.columns(2)
        with col1:
            start_date_1 = st.date_input("Start Date for Period 1")
            end_date_1 = st.date_input("End Date for Period 1")
        with col2:
            start_date_2 = st.date_input("Start Date for Period 2")
            end_date_2 = st.date_input("End Date for Period 2")

        if start_date_1 and end_date_1 and start_date_2 and end_date_2:
            custom_query = f"""
            SELECT 'Period 1' AS period, SUM(primary) AS total
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
            UNION ALL
            SELECT 'Period 2' AS period, SUM(primary) AS total
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}';
            """
            execute_comparison_query(custom_query)

def execute_comparison_query(query):
    """Execute the comparison query and display results."""
    try:
        comparison_results = pd.read_sql_query(query, conn)
        comparison_results["% Change"] = (
            comparison_results["total"].pct_change().fillna(0) * 100
        ).round(2)
        st.write("Comparison Results:")
        st.dataframe(comparison_results)

        if st.checkbox("Generate Visualization for Comparison"):
            generate_visualization(comparison_results, "total")
    except Exception as e:
        st.error(f"Error executing comparison query: {e}")

def run_analysis(table, metric, additional_columns, sort_order, row_limit):
    """Run the analysis and generate output."""
    try:
        select_columns = [metric] + additional_columns
        sort_clause = "DESC" if sort_order == "Highest" else "ASC"
        query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} ORDER BY {metric} {sort_clause} LIMIT {row_limit}"

        st.write("Generated Query:")
        st.code(query)

        results = pd.read_sql_query(query, conn)
        st.write("Query Results:")
        st.dataframe(results)

        if st.checkbox("Generate Visualization"):
            generate_visualization(results, metric)
    except Exception as e:
        st.error(f"Error executing query: {e}")

def main():
    st.title("Data Autobot")
    st.write("Version: 2.5.1")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])

    if uploaded_file:
        try:
            process_uploaded_file(uploaded_file)
            generate_analysis_ui()
        except Exception as e:
            st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
