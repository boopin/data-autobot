# App Version: 2.6.1
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

# App Metadata
APP_NAME = "Data Autobot"
TAGLINE = "Unlock insights at the speed of thought!"
VERSION = "2.6.1"


def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'


def quote_column_name(column_name):
    """Properly quote column names for SQLite."""
    return f'"{column_name}"'


def generate_visualization(results, metric, optional_metric=None):
    """Generate visualization for results."""
    if not results.empty:
        fig = px.bar(results, x=results.columns[0], y=metric, title=f"Visualization of {metric}")

        # Add optional line chart
        if optional_metric:
            fig.add_scatter(x=results[results.columns[0]], y=results[optional_metric], mode="lines", name=optional_metric)

        st.plotly_chart(fig)
    else:
        st.warning("No data available to generate visualization.")


def process_uploaded_file(uploaded_file):
    """Process uploaded file and store it in the database."""
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, encoding="utf-8", engine="python", on_bad_lines="skip")
        else:
            df = pd.read_excel(uploaded_file, sheet_name=None)

        if isinstance(df, dict):
            for sheet_name, sheet_df in df.items():
                process_and_store(sheet_df, sheet_name)
        else:
            process_and_store(df, uploaded_file.name.split('.')[0])

        st.success("File successfully processed and saved to the database!")
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

    df.to_sql(table_name, conn, if_exists="replace", index=False)
    st.write(f"Table '{table_name}' created in the database.")


def save_aggregated_view(df, table_name, period_col, suffix):
    """Save aggregated views by period."""
    if period_col in df.columns:
        agg_df = df.groupby(period_col).sum(numeric_only=True).reset_index()
        agg_table_name = f"{table_name}_{suffix}"
        agg_df.to_sql(agg_table_name, conn, if_exists="replace", index=False)


def generate_analysis_ui():
    """Generate UI for data analysis."""
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)

    if selected_table:
        columns_query = f"PRAGMA table_info({quote_table_name(selected_table)});"
        schema = pd.read_sql_query(columns_query, conn)
        columns = schema["name"].tolist()

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
    with st.expander("Enable Comparison", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            start_date_1 = st.date_input("Start Date for Period 1")
            end_date_1 = st.date_input("End Date for Period 1")
        with col2:
            start_date_2 = st.date_input("Start Date for Period 2")
            end_date_2 = st.date_input("End Date for Period 2")

        custom_name_1 = st.text_input("Custom Name for Period 1", "Period 1")
        custom_name_2 = st.text_input("Custom Name for Period 2", "Period 2")

        col1, col2 = st.columns(2)
        with col1:
            metric_bar = st.selectbox("Select metric for bar chart:", [])
        with col2:
            metric_line = st.selectbox("Select metric for line chart (optional):", [])

        if st.button("Generate Combined Visualization"):
            comparison_query = f"""
            SELECT '{custom_name_1}' AS period, SUM({quote_column_name(metric_bar)}) AS total
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
            UNION ALL
            SELECT '{custom_name_2}' AS period, SUM({quote_column_name(metric_bar)}) AS total
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}';
            """
            execute_comparison_query(comparison_query, metric_bar, metric_line, custom_name_1, custom_name_2)


def execute_comparison_query(query, metric_bar, metric_line, custom_name_1, custom_name_2):
    """Execute the comparison query and display results."""
    try:
        comparison_results = pd.read_sql_query(query, conn)
        st.dataframe(comparison_results)

        if metric_line:
            generate_visualization(comparison_results, metric_bar, optional_metric=metric_line)
        else:
            generate_visualization(comparison_results, metric_bar)
    except Exception as e:
        st.error(f"Error executing comparison query: {e}")


def run_analysis(table, metric, additional_columns, sort_order, row_limit):
    """Run the analysis and generate output."""
    select_columns = [quote_column_name(metric)] + [quote_column_name(col) for col in additional_columns]
    sort_clause = "DESC" if sort_order == "Highest" else "ASC"
    query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} ORDER BY {quote_column_name(metric)} {sort_clause} LIMIT {row_limit}"

    results = pd.read_sql_query(query, conn)
    st.dataframe(results)

    if st.checkbox("Generate Visualization"):
        generate_visualization(results, metric)


def main():
    st.title(APP_NAME)
    st.write(f"**Tagline:** {TAGLINE}")
    st.write(f"**Version:** {VERSION}")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])

    if uploaded_file:
        process_uploaded_file(uploaded_file)
        generate_analysis_ui()


if __name__ == "__main__":
    main()
