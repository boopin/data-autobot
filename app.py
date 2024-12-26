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

# SQLite in-memory database
conn = sqlite3.connect(":memory:")

# Utility functions
def quote_table_name(table_name):
    return f'"{table_name}"'

def quote_column_name(column_name):
    return f'"{column_name}"'

def get_table_columns(table_name, exclude=[]):
    query = f"PRAGMA table_info({quote_table_name(table_name)});"
    schema = pd.read_sql_query(query, conn)
    return [col for col in schema["name"].tolist() if col not in exclude]

# File processing
def process_uploaded_file(uploaded_file):
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            table_name = uploaded_file.name.split(".")[0]
            process_and_store(df, table_name)
        elif uploaded_file.name.endswith(".xlsx"):
            sheets = pd.read_excel(uploaded_file, sheet_name=None)
            for sheet_name, df in sheets.items():
                process_and_store(df, sheet_name)
        st.success("File successfully processed and saved to the database!")
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        st.error(f"Error processing file: {e}")

def process_and_store(df, table_name):
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].notnull()]
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    logger.info(f"Table '{table_name}' created in the database.")

# Individual Metrics Analysis
def generate_analysis_ui():
    st.subheader("Analyze Individual Metrics")
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)
    if selected_table:
        columns = get_table_columns(selected_table)
        metric = st.selectbox("Select metric to analyze:", columns)
        additional_columns = st.multiselect("Additional columns to display:", columns, default=columns)
        sort_order = st.radio("Sort order:", ["Highest", "Lowest"])
        limit = st.slider("Number of rows to display:", 5, 50, 10)

        if st.button("Run Analysis"):
            query = f"""
            SELECT {', '.join(quote_column_name(col) for col in additional_columns)}
            FROM {quote_table_name(selected_table)}
            ORDER BY {quote_column_name(metric)} {'DESC' if sort_order == 'Highest' else 'ASC'}
            LIMIT {limit};
            """
            try:
                results = pd.read_sql_query(query, conn)
                st.dataframe(results)
            except Exception as e:
                st.error(f"Error running analysis: {e}")

# Comparison Functionality
def generate_comparison_ui(table_name):
    st.subheader("Enable Comparison")
    col1, col2 = st.columns(2)

    with col1:
        start_date_1 = st.date_input("Start Date for Period 1")
        end_date_1 = st.date_input("End Date for Period 1")
        custom_name_1 = st.text_input("Custom Name for Period 1", value="Period 1")

    with col2:
        start_date_2 = st.date_input("Start Date for Period 2")
        end_date_2 = st.date_input("End Date for Period 2")
        custom_name_2 = st.text_input("Custom Name for Period 2", value="Period 2")

    metric_bar = st.selectbox("Select metric for bar chart:", get_table_columns(table_name, exclude=["date"]))
    metric_line = st.selectbox("Select metric for line chart (optional):", ["None"] + get_table_columns(table_name, exclude=["date"]))

    if st.button("Generate Combined Visualization"):
        try:
            query = f"""
            SELECT '{custom_name_1}' AS period, SUM({quote_column_name(metric_bar)}) AS {metric_bar}, 
                   SUM({quote_column_name(metric_line)}) AS {metric_line}
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
            UNION ALL
            SELECT '{custom_name_2}' AS period, SUM({quote_column_name(metric_bar)}) AS {metric_bar}, 
                   SUM({quote_column_name(metric_line)}) AS {metric_line}
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}';
            """
            results = pd.read_sql_query(query, conn)
            generate_visualization(
                results,
                metric_bar,
                optional_metric=(metric_line if metric_line != "None" else None)
            )
        except Exception as e:
            st.error(f"Error generating combined visualization: {e}")

# Extended Visualization
def generate_extended_visualization_ui(table_name):
    st.subheader("Extended Visualization")
    col1, col2 = st.columns(2)

    with col1:
        metric_bar = st.selectbox(
            "Select metric for bar chart:", get_table_columns(table_name, exclude=["date"])
        )

    with col2:
        metric_line = st.selectbox(
            "Select metric for line chart (optional):", ["None"] + get_table_columns(table_name, exclude=["date"])
        )

    time_period = st.selectbox("Select time period:", ["week", "month", "quarter"])

    if st.button("Generate Extended Visualization"):
        try:
            query = f"""
            SELECT {time_period}, SUM({quote_column_name(metric_bar)}) AS {metric_bar}, 
                   SUM({quote_column_name(metric_line)}) AS {metric_line}
            FROM {quote_table_name(table_name)}
            GROUP BY {time_period};
            """
            results = pd.read_sql_query(query, conn)
            generate_visualization(
                results,
                metric_bar,
                optional_metric=(metric_line if metric_line != "None" else None)
            )
        except Exception as e:
            st.error(f"Error generating extended visualization: {e}")

# Visualization Function
def generate_visualization(results, y_metric, optional_metric=None):
    try:
        if not results.empty:
            fig = go.Figure()
            fig.add_bar(
                x=results[results.columns[0]],
                y=results[y_metric],
                name=y_metric,
                yaxis="y"
            )
            if optional_metric:
                fig.add_scatter(
                    x=results[results.columns[0]],
                    y=results[optional_metric],
                    name=optional_metric,
                    mode="lines+markers",
                    yaxis="y2"
                )

            fig.update_layout(
                title=f"{y_metric} (Bar) and {optional_metric} (Line)" if optional_metric else f"Visualization of {y_metric}",
                xaxis=dict(title="Time Period"),
                yaxis=dict(title=y_metric, side="left"),
                yaxis2=dict(title=optional_metric, side="right", overlaying="y") if optional_metric else None,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            st.plotly_chart(fig)
        else:
            st.warning("No data available for visualization.")
    except Exception as e:
        logger.error(f"Error generating visualization: {e}")
        st.error(f"Error generating visualization: {e}")

# Main App
def main():
    st.title("Data Autobot")
    st.write("**Tagline:** Unlock insights at the speed of thought!")
    st.write("**Version:** 2.6.3")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    if uploaded_file:
        process_uploaded_file(uploaded_file)
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql_query(tables_query, conn)["name"].tolist()
        for table in tables:
            generate_analysis_ui()
            generate_comparison_ui(table)
            generate_extended_visualization_ui(table)

if __name__ == "__main__":
    main()
