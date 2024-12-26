# Full app.py (Updated with Fixes)
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

# Extended Visualization UI
def generate_extended_visualization_ui(table_name):
    st.subheader(f"Extended Visualization for Table: {table_name}")
    col1, col2 = st.columns(2)
    with col1:
        metric_bar = st.selectbox(
            "Select metric for bar chart:",
            get_table_columns(table_name, exclude=["date"]),
            key=f"{table_name}_bar_metric"
        )
    with col2:
        metric_line = st.selectbox(
            "Select metric for line chart (optional):",
            ["None"] + get_table_columns(table_name, exclude=["date"]),
            key=f"{table_name}_line_metric"
        )

    time_period = st.selectbox(
        "Select time period:",
        ["week", "month", "quarter"],
        key=f"{table_name}_time_period"
    )

    if st.button("Generate Extended Visualization", key=f"{table_name}_extended_visualization"):
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

# Main App
def main():
    st.title("Data Autobot")
    st.write("**Tagline:** Unlock insights at the speed of thought!")
    st.write("**Version:** 2.6.1")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    if uploaded_file:
        # Process uploaded file and generate UI
        process_uploaded_file(uploaded_file)
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql_query(tables_query, conn)["name"].tolist()
        for table in tables:
            generate_extended_visualization_ui(table)

if __name__ == "__main__":
    main()
