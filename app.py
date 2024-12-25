# App Version: 3.0.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

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

def main():
    # Display App Header
    st.title("Data Autobot")
    st.write("**Empowering Decisions, One Insight at a Time**")
    st.write("**Version: 3.0.0**")

    # File Upload
    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file, sheet_name=None)
            
            # Process all sheets or a single DataFrame
            if isinstance(df, dict):
                st.write("Detected multiple sheets in the uploaded file.")
                for sheet_name, sheet_df in df.items():
                    process_and_store(sheet_df, sheet_name)
            else:
                process_and_store(df, uploaded_file.name.split('.')[0])

            st.success("File successfully processed and saved to the database!")
            generate_analysis_ui()
        except Exception as e:
            st.error(f"Error loading file: {e}")

def process_and_store(df, table_name):
    """Process the DataFrame and store it in the SQLite database with aggregations."""
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].notnull()]  # Remove rows with invalid dates

        # Add derived time periods
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
    """Save aggregated views by period (weekly, monthly, quarterly)."""
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
    # Get available tables
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)

    if selected_table:
        # Get table schema
        columns_query = f"PRAGMA table_info({quote_table_name(selected_table)});"
        schema = pd.read_sql_query(columns_query, conn)
        columns = schema["name"].tolist()

        st.write(f"Schema for '{selected_table}': {columns}")

        # UI Layout
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_metric = st.selectbox("Select metric to analyze:", [col for col in columns if col not in ["date", "week", "month", "quarter"]])
        with col2:
            additional_columns = st.multiselect("Select additional columns:", [col for col in columns if col != selected_metric])
        with col3:
            sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
            row_limit = st.slider("Rows to display:", 5, 50, 10)

        # Comparison UI
        with st.expander("Enable Comparison", expanded=False):
            st.write("Compare two custom date ranges.")
            col_comp1, col_comp2 = st.columns(2)
            with col_comp1:
                period_start = st.date_input("Start Date:")
            with col_comp2:
                period_end = st.date_input("End Date:")

            if st.button("Run Comparison") and period_start and period_end:
                run_comparison(selected_table, selected_metric, period_start, period_end)

        # Run Analysis Button
        if st.button("Run Analysis"):
            if selected_metric:
                run_analysis(selected_table, selected_metric, additional_columns, sort_order, row_limit)
            else:
                st.warning("Please select a metric to analyze.")

def run_analysis(table, metric, additional_columns, sort_order, row_limit):
    """Run the analysis and generate output."""
    try:
        select_columns = [metric] + additional_columns
        sort_clause = "DESC" if sort_order == "Highest" else "ASC"
        query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} ORDER BY {metric} {sort_clause} LIMIT {row_limit}"
        results = pd.read_sql_query(query, conn)
        st.write("Query Results:")
        st.dataframe(results)
        if st.checkbox("Generate Visualization"):
            generate_visualization(results, metric)
    except Exception as e:
        st.error(f"Error executing query: {e}")

def run_comparison(table, metric, start_date, end_date):
    """Run a comparison analysis."""
    try:
        query = f"""
        SELECT date, SUM({metric}) AS total
        FROM {quote_table_name(table)}
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY date
        """
        results = pd.read_sql_query(query, conn)
        st.write("Comparison Results:")
        st.dataframe(results)
        if st.checkbox("Generate Visualization for Comparison"):
            generate_visualization(results, "total")
    except Exception as e:
        st.error(f"Error executing comparison query: {e}")

if __name__ == "__main__":
    main()
