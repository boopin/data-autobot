import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'

def quote_column_name(column_name):
    """Properly quote column names for SQLite."""
    return f'"{column_name}"'

def generate_combined_visualization(df, bar_metric, line_metric, x_column, title):
    """Generate combined bar and line visualization."""
    try:
        fig = px.bar(
            df, x=x_column, y=bar_metric, title=title, labels={x_column: "Time Period"}
        )
        # Add a line chart with a dual y-axis
        fig.add_scatter(
            x=df[x_column],
            y=df[line_metric],
            mode="lines+markers",
            name=line_metric,
            yaxis="y2"
        )
        fig.update_layout(
            yaxis=dict(title="Impressions Total"),
            yaxis2=dict(title="Clicks Total", overlaying="y", side="right"),
            legend=dict(orientation="h")
        )
        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error generating combined visualization: {e}")

def generate_extended_visualization(table, bar_metric, line_metric, period_type):
    """Generate extended visualization for predefined time periods."""
    try:
        query = f"SELECT {period_type}, SUM({bar_metric}) AS {bar_metric}, SUM({line_metric}) AS {line_metric} FROM {quote_table_name(table)} GROUP BY {period_type} ORDER BY {period_type}"
        df = pd.read_sql_query(query, conn)

        generate_combined_visualization(
            df,
            bar_metric,
            line_metric,
            period_type,
            f"{bar_metric} (Bar) and {line_metric} (Line) Over {period_type.capitalize()}",
        )
    except Exception as e:
        st.error(f"Error generating extended visualization: {e}")

def process_uploaded_file(uploaded_file):
    """Process uploaded file and store it in the database."""
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Unsupported file format.")
            return None

        # Dynamically populate dropdown options
        columns = [col for col in df.columns if col not in ["date", "week", "month", "quarter"]]
        st.write("Available columns:", columns)

        # Dropdowns for metric selection
        with st.expander("Generate Extended Time Period Visualization"):
            bar_metric = st.selectbox(
                "Select metric for bar chart:",
                options=columns,
                help="Choose a metric for the bar chart."
            )

            line_metric = st.selectbox(
                "Select metric for line chart:",
                options=columns,
                help="Choose a metric for the line chart."
            )

            period_type = st.selectbox("Select time period:", ["week", "month", "quarter"])

            if bar_metric and line_metric:
                if st.button("Generate Combined Visualization"):
                    generate_combined_visualization(df, bar_metric, line_metric, "time_period", "Comparison of Metrics")
            else:
                st.warning("Please select both bar and line metrics.")

        return df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

def preprocess_data(df):
    """Automatically add derived columns like week, month, quarter, and year."""
    try:
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            if not df["date"].isnull().all():
                df["week"] = df["date"].dt.to_period("W-SUN").astype(str)
                df["year_month"] = df["date"].dt.to_period("M").astype(str)
                df["quarter"] = "Q" + df["date"].dt.quarter.astype(str) + " " + df["date"].dt.year.astype(str)
                df["year"] = df["date"].dt.year.astype(str)
            else:
                raise ValueError("The 'date' column contains no valid dates.")
        else:
            raise ValueError("The dataset is missing a 'date' column.")
    except Exception as e:
        st.error(f"Error preprocessing data: {e}")

# Main application logic
st.title("Data Autobot")
st.write("Version 2.6.0")

# File uploader
uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
if uploaded_file is not None:
    df = process_uploaded_file(uploaded_file)
    if df is not None:
        preprocess_data(df)
