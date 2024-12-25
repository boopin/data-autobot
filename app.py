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
        numeric_columns = [col for col in columns if col not in ["date", "week", "month", "quarter"]]
        selected_metric = st.selectbox("Select metric to analyze:", numeric_columns, disabled=not numeric_columns)

        # Additional columns for output
        if selected_table == "all_posts" or not any(col in columns for col in ["date", "week", "month", "quarter"]):
            additional_columns = st.multiselect(
                "Select additional columns to include in the output:",
                [col for col in columns if col != selected_metric]
            )
        else:
            additional_columns = []

        # Date aggregation options
        date_columns = [col for col in ["date", "week", "month", "quarter"] if col in columns]
        aggregation_type = st.selectbox("Select aggregation type (if applicable):", ["None"] + date_columns)

        # Sorting and row limit
        sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
        row_limit = st.slider("Number of rows to display:", 5, 50, 10)

        # Comparison Section
        enable_comparison = st.checkbox("Enable Comparison")
        if enable_comparison:
            comparison_type = st.radio("Select Comparison Type:", ["Weekly", "Monthly", "Quarterly", "Custom"])
            period_1 = st.selectbox("Select Period 1", [])
            period_2 = st.selectbox("Select Period 2", [])

        # Run Analysis Button
        if st.button("Run Analysis"):
            if selected_metric:
                run_analysis(selected_table, columns, selected_metric, additional_columns, aggregation_type, sort_order, row_limit)
            else:
                st.warning("Please select a metric to analyze.")

        # Generate Visualization
        if st.button("Generate Visualization"):
            if 'query_result' in locals() and not query_result.empty:
                chart = create_visualization(query_result)
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.warning("No data to visualize. Please run a query first.")

def run_analysis(table, columns, metric, additional_columns, aggregation_type, sort_order, row_limit):
    """Run the analysis and generate output."""
    try:
        # Include date/aggregation columns and additional columns
        select_columns = [metric] + additional_columns
        if aggregation_type != "None":
            select_columns.insert(0, aggregation_type)

        sort_clause = "DESC" if sort_order == "Highest" else "ASC"
        query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} ORDER BY {metric} {sort_clause} LIMIT {row_limit}"
        
        st.write("Generated Query:")
        st.code(query)

        # Execute query
        results = pd.read_sql_query(query, conn)
        st.write("Query Results:")
        st.dataframe(results)

        # Visualization toggle
        if st.checkbox("Generate Visualization"):
            fig = px.bar(results, x=results.columns[0], y=metric, title="Visualization")
            st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error executing query: {e}")

if __name__ == "__main__":
    main()
