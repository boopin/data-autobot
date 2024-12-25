# App Version: 2.3.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'

def main():
    st.title("Data Autobot")
    st.write("Version: 2.3.0")

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
    """Process the DataFrame and store it in the SQLite database."""
    # Clean column names
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]

    # Handle date column
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    
    # Save to database
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    st.write(f"Table '{table_name}' created in the database.")

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

        # Metric selection
        selected_metric = st.selectbox("Select metric to analyze:", [col for col in columns if col not in ["date", "week", "month", "quarter"]])

        # Comparison Option
        if st.checkbox("Enable Comparison"):
            enable_comparison_ui(selected_table, selected_metric)

        # Additional columns for output
        additional_columns = st.multiselect(
            "Select additional columns to include in the output:",
            [col for col in columns if col != selected_metric]
        )

        # Date aggregation options
        date_columns = [col for col in ["date", "week", "month", "quarter"] if col in columns]
        aggregation_type = st.selectbox("Select aggregation type (if applicable):", ["None"] + date_columns)

        # Sorting and row limit
        sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
        row_limit = st.slider("Number of rows to display:", 5, 50, 10)

        # Run Analysis Button
        if st.button("Run Analysis"):
            if selected_metric:
                run_analysis(selected_table, columns, selected_metric, additional_columns, aggregation_type, sort_order, row_limit)
            else:
                st.warning("Please select a metric to analyze.")

def enable_comparison_ui(selected_table, selected_metric):
    """Generate UI for comparison between two periods."""
    compare_type = st.selectbox("Select comparison type:", ["Weekly", "Monthly", "Quarterly"])
    periods = get_distinct_periods(selected_table, compare_type.lower())

    if periods:
        period1 = st.selectbox(f"Select Period 1 ({compare_type}):", periods)
        period2 = st.selectbox(f"Select Period 2 ({compare_type}):", periods)

        if st.button("Compare Periods"):
            run_comparison(selected_table, selected_metric, compare_type.lower(), period1, period2)
    else:
        st.warning("No periods available for comparison.")

def get_distinct_periods(table, period_type):
    """Get distinct values for a specific period type."""
    query = f"SELECT DISTINCT {period_type} FROM {quote_table_name(table)} ORDER BY {period_type}"
    try:
        return pd.read_sql_query(query, conn)[period_type].tolist()
    except Exception as e:
        st.error(f"Error retrieving periods: {e}")
        return []

def run_analysis(table, columns, metric, additional_columns, aggregation_type, sort_order, row_limit):
    """Run the analysis and generate output."""
    try:
        select_columns = [metric] + additional_columns
        if aggregation_type != "None":
            select_columns.insert(0, aggregation_type)

        sort_clause = "DESC" if sort_order == "Highest" else "ASC"
        query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} ORDER BY {metric} {sort_clause} LIMIT {row_limit}"
        
        st.write("Generated Query:")
        st.code(query)

        results = pd.read_sql_query(query, conn)
        st.write("Query Results:")
        st.dataframe(results)

        # Generate visualization
        if st.checkbox("Generate Visualization"):
            fig = px.bar(results, x=results.columns[0], y=metric, title="Visualization")
            st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error executing query: {e}")

def run_comparison(table, metric, compare_type, period1, period2):
    """Run comparison between two periods."""
    try:
        query = f"""
        SELECT '{period1}' AS period, SUM({metric}) AS total FROM {quote_table_name(table)}
        WHERE {compare_type} = '{period1}'
        UNION ALL
        SELECT '{period2}' AS period, SUM({metric}) AS total FROM {quote_table_name(table)}
        WHERE {compare_type} = '{period2}'
        """
        
        st.write("Generated Comparison Query:")
        st.code(query)

        results = pd.read_sql_query(query, conn)
        results["% Change"] = results["total"].pct_change().fillna(0) * 100

        st.write("Comparison Results:")
        st.dataframe(results)

        # Generate visualization
        if st.checkbox("Generate Comparison Visualization"):
            fig = px.bar(results, x="period", y="total", title=f"Comparison: {period1} vs {period2}")
            st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error executing comparison query: {e}")

if __name__ == "__main__":
    main()
