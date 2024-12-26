# App Version: 2.5.5
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import logging

# Configure logging
logging.basicConfig(
    filename="data_autobot.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger()

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'

def quote_column_name(column_name):
    """Properly quote column names for SQLite."""
    return f'"{column_name}"'

def generate_combined_visualization(results, bar_metric, line_metric):
    """Generate combined visualization for results."""
    try:
        if not results.empty:
            logger.info("Generating combined visualization...")
            fig = px.bar(
                results,
                x=results.columns[0],
                y=bar_metric,
                title=f"Visualization of {bar_metric} (Bar) and {line_metric} (Line)",
                labels={bar_metric: "Values", results.columns[0]: "Category"},
            )
            fig.add_scatter(
                x=results[results.columns[0]],
                y=results[line_metric],
                mode='lines+markers',
                name=line_metric,
            )
            st.plotly_chart(fig)
        else:
            st.warning("No data available to generate visualization.")
            logger.warning("No data available for visualization.")
    except Exception as e:
        logger.error(f"Error generating combined visualization: {e}")
        st.error(f"Error generating visualization: {e}")

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
            period_1_name = st.text_input("Custom Name for Period 1", "Period 1")
            period_2_name = st.text_input("Custom Name for Period 2", "Period 2")

            bar_metric = st.selectbox("Select metric for Bar Chart:", [col for col in pd.read_sql_query(f"PRAGMA table_info({quote_table_name(table_name)})", conn)["name"] if col != "date"])
            line_metric = st.selectbox("Select metric for Line Chart:", [col for col in pd.read_sql_query(f"PRAGMA table_info({quote_table_name(table_name)})", conn)["name"] if col != "date"])

            if bar_metric and line_metric:
                comparison_query = f"""
                SELECT '{period_1_name}' AS period, 
                       SUM({quote_column_name(bar_metric)}) AS {quote_column_name(bar_metric)},
                       SUM({quote_column_name(line_metric)}) AS {quote_column_name(line_metric)}
                FROM {quote_table_name(table_name)}
                WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
                UNION ALL
                SELECT '{period_2_name}' AS period, 
                       SUM({quote_column_name(bar_metric)}) AS {quote_column_name(bar_metric)},
                       SUM({quote_column_name(line_metric)}) AS {quote_column_name(line_metric)}
                FROM {quote_table_name(table_name)}
                WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}';
                """
                execute_comparison_query(comparison_query, bar_metric, line_metric)

def execute_comparison_query(query, bar_metric, line_metric):
    """Execute the comparison query and display results."""
    try:
        comparison_results = pd.read_sql_query(query, conn)
        comparison_results["% Change (Bar)"] = (
            comparison_results[bar_metric].pct_change().fillna(0) * 100
        ).round(2)
        comparison_results["% Change (Line)"] = (
            comparison_results[line_metric].pct_change().fillna(0) * 100
        ).round(2)
        st.write("Comparison Results:")
        st.dataframe(comparison_results)

        if st.checkbox("Generate Visualization for Comparison"):
            generate_combined_visualization(comparison_results, bar_metric, line_metric)
    except Exception as e:
        logger.error(f"Error executing comparison query: {e}")
        st.error(f"Error executing comparison query: {e}")

def generate_analysis_ui():
    """Generate UI for data analysis."""
    try:
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
    except Exception as e:
        logger.error(f"Error in generating analysis UI: {e}")
        st.error(f"Error in generating analysis UI: {e}")

def main():
    st.title("Data Autobot")
    st.write("**Tagline:** Unlock insights at the speed of thought!")
    st.write("**Version:** 2.5.5")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])

    if uploaded_file:
        process_uploaded_file(uploaded_file)
        generate_analysis_ui()

if __name__ == "__main__":
    main()
