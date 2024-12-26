# App Version: 2.6.2
import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
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

def generate_combined_visualization(results, bar_metric, line_metric, title):
    """Generate combined bar and line visualization."""
    try:
        if not results.empty:
            logger.info("Generating combined visualization...")
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=results.iloc[:, 0],
                    y=results[bar_metric],
                    name=f"{bar_metric} (Bar)",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=results.iloc[:, 0],
                    y=results[line_metric],
                    name=f"{line_metric} (Line)",
                    mode="lines+markers",
                )
            )
            fig.update_layout(
                title=title,
                xaxis_title=results.columns[0],
                yaxis_title="Values",
                legend_title="Metrics",
            )
            st.plotly_chart(fig)
        else:
            st.warning("No data available to generate visualization.")
            logger.warning("No data available for combined visualization.")
    except Exception as e:
        logger.error(f"Error generating combined visualization: {e}")
        st.error(f"Error generating combined visualization: {e}")

def process_uploaded_file(uploaded_file):
    """Process uploaded file and store it in the database."""
    try:
        logger.info(f"Processing file: {uploaded_file.name}")
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, encoding="utf-8", engine="python", on_bad_lines="skip")
        else:
            df = pd.read_excel(uploaded_file, sheet_name=None)
        
        if isinstance(df, dict):
            st.write("Detected multiple sheets in the uploaded file.")
            for sheet_name, sheet_df in df.items():
                process_and_store(sheet_df, sheet_name)
        else:
            process_and_store(df, uploaded_file.name.split('.')[0])

        st.success("File successfully processed and saved to the database!")
    except UnicodeDecodeError:
        logger.error("File encoding not supported.")
        st.error("File encoding not supported. Please ensure the file is UTF-8 encoded.")
    except Exception as e:
        logger.error(f"Error loading file: {e}")
        st.error(f"Error loading file: {e}")

def process_and_store(df, table_name):
    """Process the DataFrame and store it in the SQLite database with aggregations."""
    try:
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
        logger.info(f"Table '{table_name}' successfully processed and saved.")
    except Exception as e:
        logger.error(f"Error processing table '{table_name}': {e}")
        st.warning(f"Error processing table '{table_name}': {e}")

def save_aggregated_view(df, table_name, period_col, suffix):
    """Save aggregated views by period."""
    try:
        if period_col in df.columns:
            agg_df = df.groupby(period_col).sum(numeric_only=True).reset_index()
            agg_table_name = f"{table_name}_{suffix}"
            agg_df.to_sql(agg_table_name, conn, if_exists="replace", index=False)
            st.write(f"Aggregated table '{agg_table_name}' created successfully.")
            logger.info(f"Aggregated table '{agg_table_name}' created successfully.")
    except Exception as e:
        logger.error(f"Could not create aggregated table for '{suffix}': {e}")
        st.warning(f"Could not create aggregated table for '{suffix}': {e}")

def execute_comparison_query(query, bar_metric, line_metric):
    """Execute the comparison query and display results."""
    try:
        comparison_results = pd.read_sql_query(query, conn)

        # Calculate percentage change for the bar metric
        comparison_results["% Change"] = (
            comparison_results[bar_metric]
            .pct_change(fill_method=None)  # Avoid deprecated fill method
            .fillna(0)
            * 100
        ).round(2)
        
        st.write("Comparison Results:")
        st.dataframe(comparison_results)

        if st.checkbox("Generate Combined Visualization for Comparison"):
            generate_combined_visualization(
                comparison_results, bar_metric, line_metric, "Comparison Results"
            )
    except Exception as e:
        logger.error(f"Error executing comparison query: {e}")
        st.error(f"Error executing comparison query: {e}")

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
            bar_metric = st.selectbox(
                "Select bar metric for comparison:",
                [col for col in pd.read_sql_query(f"PRAGMA table_info({quote_table_name(table_name)})", conn)["name"] if col != "date"],
            )
            line_metric = st.selectbox(
                "Select line metric for comparison:",
                [col for col in pd.read_sql_query(f"PRAGMA table_info({quote_table_name(table_name)})", conn)["name"] if col != "date"],
            )
            comparison_query = f"""
            SELECT 'Period 1' AS period, SUM({quote_column_name(bar_metric)}) AS {bar_metric}, SUM({quote_column_name(line_metric)}) AS {line_metric}
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
            UNION ALL
            SELECT 'Period 2' AS period, SUM({quote_column_name(bar_metric)}) AS {bar_metric}, SUM({quote_column_name(line_metric)}) AS {line_metric}
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}';
            """
            execute_comparison_query(comparison_query, bar_metric, line_metric)

def main():
    st.title("Data Autobot")
    st.write("**Tagline:** Unlock insights at the speed of thought!")
    st.write("**Version:** 2.6.2")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])

    if uploaded_file:
        process_uploaded_file(uploaded_file)
        generate_analysis_ui()

if __name__ == "__main__":
    main()
