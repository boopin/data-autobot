# App Version: 2.2.0
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
    st.write("Version: 2.2.0")

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

        # Additional columns for output
        additional_columns = st.multiselect(
            "Select additional columns to include in the output:",
            [col for col in columns if col != selected_metric]
        )

        # Date aggregation options
        date_columns = [col for col in ["date", "week", "month", "quarter"] if col in columns]
        aggregation_type = st.selectbox("Select aggregation type (if applicable):", ["None"] + date_columns)

        # Custom Time Periods
        if aggregation_type != "None":
            st.write(f"Custom {aggregation_type} Range")
            start_period = st.selectbox(f"Start {aggregation_type}:", get_distinct_periods(selected_table, aggregation_type))
            end_period = st.selectbox(f"End {aggregation_type}:", get_distinct_periods(selected_table, aggregation_type))

        # Sorting and row limit
        sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
        row_limit = st.slider("Number of rows to display:", 5, 50, 10)

        # Run Analysis Button
        if st.button("Run Analysis"):
            if selected_metric:
                run_analysis(selected_table, columns, selected_metric, additional_columns, aggregation_type, sort_order, row_limit, start_period, end_period)
            else:
                st.warning("Please select a metric to analyze.")

def get_distinct_periods(table, period_type):
    """Get distinct values for a specific period type."""
    query = f"SELECT DISTINCT {period_type} FROM {quote_table_name(table)} ORDER BY {period_type}"
    try:
        return pd.read_sql_query(query, conn)[period_type].tolist()
    except Exception as e:
        st.error(f"Error retrieving periods: {e}")
        return []

def run_analysis(table, columns, metric, additional_columns, aggregation_type, sort_order, row_limit, start_period, end_period):
    """Run the analysis and generate output."""
    try:
        # Include date/aggregation columns and additional columns
        select_columns = [metric] + additional_columns
        if aggregation_type != "None":
            select_columns.insert(0, aggregation_type)

        where_clause = ""
        if aggregation_type != "None" and start_period and end_period:
            where_clause = f"WHERE {aggregation_type} BETWEEN '{start_period}' AND '{end_period}'"

        sort_clause = "DESC" if sort_order == "Highest" else "ASC"
        query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} {where_clause} ORDER BY {metric} {sort_clause} LIMIT {row_limit}"
        
        st.write("Generated Query:")
        st.code(query)

        # Execute query
        results = pd.read_sql_query(query, conn)
        st.write("Query Results:")
        st.dataframe(results)

        # Generate visualization
        if st.checkbox("Generate Visualization"):
            fig = px.bar(results, x=results.columns[0], y=metric, title="Visualization")
            st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error executing query: {e}")

if __name__ == "__main__":
    main()
