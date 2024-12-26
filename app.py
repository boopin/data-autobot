# App Version: 2.6.0
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

# Visualization Function
def generate_visualization(results, y_metric, optional_metric=None):
    try:
        if not results.empty:
            results["% Change (Bar)"] = results[y_metric].pct_change().fillna(0).round(2) * 100
            if optional_metric:
                results["% Change (Line)"] = results[optional_metric].pct_change().fillna(0).round(2) * 100

            st.write("Comparison Results with % Change:")
            st.dataframe(results)

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
                xaxis=dict(title="Period"),
                yaxis=dict(title=y_metric, side="left"),
                yaxis2=dict(title=optional_metric, side="right", overlaying="y") if optional_metric else None,
                legend=dict(orientation="h", y=-0.2),
                margin=dict(l=40, r=40, t=40, b=40)
            )

            st.plotly_chart(fig)
        else:
            st.warning("No data available for visualization.")
    except Exception as e:
        st.error(f"Error generating visualization: {e}")

# Process and Store File
def process_uploaded_file(uploaded_file):
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, encoding="utf-8", engine="python", on_bad_lines="skip")
        else:
            df = pd.read_excel(uploaded_file)

        df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df.dropna(subset=["date"], inplace=True)
        df.to_sql(uploaded_file.name.split('.')[0], conn, if_exists="replace", index=False)
        st.success("File successfully processed and saved to the database!")
    except Exception as e:
        st.error(f"Error processing file: {e}")

# Analysis UI
def generate_analysis_ui():
    try:
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

        selected_table = st.selectbox("Select table to analyze:", tables)
        if selected_table:
            columns = get_table_columns(selected_table)

            st.write(f"Schema for '{selected_table}': {columns}")
            col1, col2, col3 = st.columns(3)

            with col1:
                selected_metric = st.selectbox("Select metric to analyze:", columns)

            with col2:
                additional_columns = st.multiselect("Select additional columns:", columns)

            with col3:
                sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
                row_limit = st.slider("Rows to display:", 5, 50, 10)

            if st.button("Run Analysis"):
                query = f"SELECT {', '.join([selected_metric] + additional_columns)} FROM {quote_table_name(selected_table)} ORDER BY {selected_metric} {'DESC' if sort_order == 'Highest' else 'ASC'} LIMIT {row_limit}"
                results = pd.read_sql_query(query, conn)
                st.write("Query Results:")
                st.dataframe(results)

                if st.checkbox("Generate Visualization"):
                    generate_visualization(results, selected_metric)
    except Exception as e:
        st.error(f"Error generating analysis UI: {e}")

# Comparison UI
def generate_comparison_ui(table_name):
    st.subheader("Enable Comparison")
    enable_comparison = st.checkbox("Toggle Comparison")
    if enable_comparison:
        col1, col2 = st.columns(2)
        with col1:
            start_date_1 = st.date_input("Start Date for Period 1")
            end_date_1 = st.date_input("End Date for Period 1")
            custom_name_1 = st.text_input("Custom Name for Period 1", value="Period 1")
        with col2:
            start_date_2 = st.date_input("Start Date for Period 2")
            end_date_2 = st.date_input("End Date for Period 2")
            custom_name_2 = st.text_input("Custom Name for Period 2", value="Period 2")

        if start_date_1 and end_date_1 and start_date_2 and end_date_2:
            col3, col4 = st.columns(2)
            with col3:
                metric_bar = st.selectbox("Select metric for bar chart:", get_table_columns(table_name, exclude=["date"]))
            with col4:
                metric_line = st.selectbox("Select metric for line chart (optional):", ["None"] + get_table_columns(table_name, exclude=["date"]))

            if st.button("Generate Combined Visualization"):
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
                generate_visualization(results, metric_bar, optional_metric=(metric_line if metric_line != "None" else None))

# Extended Visualization UI
def generate_extended_visualization_ui(table_name):
    st.subheader("Extended Visualization")
    col1, col2 = st.columns(2)
    with col1:
        metric_bar = st.selectbox("Select metric for bar chart:", get_table_columns(table_name, exclude=["date"]))
    with col2:
        metric_line = st.selectbox("Select metric for line chart (optional):", ["None"] + get_table_columns(table_name, exclude=["date"]))

    time_period = st.selectbox("Select time period:", ["week", "month", "quarter"])
    if st.button("Generate Extended Visualization"):
        query = f"""
        SELECT {time_period}, SUM({quote_column_name(metric_bar)}) AS {metric_bar},
               SUM({quote_column_name(metric_line)}) AS {metric_line} 
        FROM {quote_table_name(table_name)} 
        GROUP BY {time_period};
        """
        results = pd.read_sql_query(query, conn)
        generate_visualization(results, metric_bar, optional_metric=(metric_line if metric_line != "None" else None))

# Main App
def main():
    st.title("Data Autobot")
    st.write("**Tagline:** Unlock insights at the speed of thought!")
    st.write("**Version:** 2.6.0")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    if uploaded_file:
        process_uploaded_file(uploaded_file)
        generate_analysis_ui()
        generate_comparison_ui(uploaded_file.name.split('.')[0])
        generate_extended_visualization_ui(uploaded_file.name.split('.')[0])

if __name__ == "__main__":
    main()
