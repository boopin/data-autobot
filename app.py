import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
from datetime import datetime

# Initialize database connection
conn = duckdb.connect()

def initialize_database(uploaded_file):
    """Process uploaded file and save it into DuckDB."""
    try:
        if uploaded_file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(uploaded_file)
            for sheet in excel_data.sheet_names:
                df = pd.read_excel(excel_data, sheet_name=sheet)
                table_name = sheet.lower().replace(" ", "_")
                df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
                df.to_parquet(f"{table_name}.parquet")
                conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{table_name}.parquet')")
        elif uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            table_name = uploaded_file.name.lower().replace(".csv", "").replace(" ", "_")
            df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
            df.to_parquet(f"{table_name}.parquet")
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{table_name}.parquet')")
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return []
        return conn.execute("SHOW TABLES").fetchall()
    except Exception as e:
        st.error(f"Error initializing database: {e}")
        return []

def dynamic_date_aggregation(df):
    """Create weekly, monthly, and quarterly aggregations."""
    if "date" not in df.columns:
        return
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["week"] = df["date"].dt.to_period("W").astype(str)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    return df

def display_schema_options(table_name):
    """Show schema options for a selected table."""
    try:
        schema = conn.execute(f"DESCRIBE {table_name}").fetchdf()
        st.write(f"Schema for {table_name}:")
        st.dataframe(schema)
        return schema["name"].tolist()
    except Exception as e:
        st.error(f"Error fetching schema: {e}")
        return []

def render_visualizations(df, chart_type):
    """Render visualizations using Plotly."""
    if chart_type == "Bar Chart":
        column = st.selectbox("Select a column for bar chart:", df.columns)
        fig = px.bar(df, x=df.index, y=column, title=f"Bar Chart for {column}")
        st.plotly_chart(fig)
    elif chart_type == "Line Chart":
        column = st.selectbox("Select a column for line chart:", df.columns)
        fig = px.line(df, x=df.index, y=column, title=f"Line Chart for {column}")
        st.plotly_chart(fig)

def main():
    st.title("Data Autobot with DuckDB")
    st.info("Upload a CSV or Excel file to start analysis.")

    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if not uploaded_file:
        return

    tables = initialize_database(uploaded_file)
    if not tables:
        return

    selected_table = st.selectbox("Select a table:", [table[0] for table in tables])
    schema_options = display_schema_options(selected_table)
    if not schema_options:
        return

    date_aggregation = st.selectbox(
        "Select Date Aggregation (if applicable):",
        ["None", "Weekly", "Monthly", "Quarterly"]
    )

    # Handle dynamic date aggregation
    if date_aggregation != "None":
        if "date" not in schema_options:
            st.error(f"Selected table '{selected_table}' does not have a 'date' column.")
            return
        df = pd.read_parquet(f"{selected_table}.parquet")
        df = dynamic_date_aggregation(df)
        aggregation_column = (
            "week" if date_aggregation == "Weekly" else
            "month" if date_aggregation == "Monthly" else
            "quarter"
        )
        df = df.groupby(aggregation_column).sum().reset_index()
        st.dataframe(df)
        render_visualizations(df, st.selectbox("Select Visualization Type:", ["Bar Chart", "Line Chart"]))
    else:
        query = st.text_area("Write your SQL Query:")
        if st.button("Run Query"):
            try:
                result = conn.execute(query).fetchdf()
                st.dataframe(result)
            except Exception as e:
                st.error(f"Query failed: {e}")

    if st.checkbox("Enable Comparison"):
        compare_type = st.selectbox("Compare By:", ["Weekly", "Monthly", "Quarterly"])
        st.info(f"Comparison mode enabled: {compare_type}")
        # Add dropdowns to select periods for comparison
        if compare_type in ["Weekly", "Monthly", "Quarterly"]:
            options = sorted(df[compare_type.lower()].unique())
            start_period = st.selectbox("Select Start Period:", options)
            end_period = st.selectbox("Select End Period:", options)
            comparison_result = df.loc[
                (df[compare_type.lower()] >= start_period) & (df[compare_type.lower()] <= end_period)
            ]
            st.dataframe(comparison_result)

if __name__ == "__main__":
    main()
