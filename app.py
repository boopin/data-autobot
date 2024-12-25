# App Version: 1.3.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Initialize SQLite connection
conn = sqlite3.connect(":memory:")

def preprocess_column_names(df):
    """Preprocess column names for database compatibility."""
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_") for col in df.columns]
    return df

def quote_table_name(table_name):
    """Safely quote table names to handle special characters or spaces."""
    return f'"{table_name}"'

def load_file(file):
    """Load and preprocess the uploaded file into the database."""
    try:
        if file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(file)
            for sheet_name in excel_data.sheet_names:
                df = pd.read_excel(excel_data, sheet_name=sheet_name)
                df = preprocess_column_names(df)
                df.to_sql(sheet_name.lower().replace(" ", "_"), conn, index=False, if_exists="replace")
        elif file.name.endswith(".csv"):
            df = pd.read_csv(file)
            df = preprocess_column_names(df)
            table_name = file.name.replace(".csv", "").lower().replace(" ", "_")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
        st.success("File successfully processed and loaded into the database!")
    except Exception as e:
        st.error(f"Error loading file: {e}")

def get_table_schema(table_name):
    """Retrieve the schema of a table from the database."""
    try:
        quoted_table_name = quote_table_name(table_name)
        schema_query = f"PRAGMA table_info({quoted_table_name})"
        schema_info = pd.read_sql_query(schema_query, conn)
        return schema_info["name"].tolist()
    except Exception as e:
        st.error(f"Error retrieving schema for table '{table_name}': {e}")
        return []

def get_numeric_columns(table_name):
    """Retrieve numeric columns from the table schema."""
    try:
        quoted_table_name = quote_table_name(table_name)
        schema_query = f"PRAGMA table_info({quoted_table_name})"
        schema_info = pd.read_sql_query(schema_query, conn)
        numeric_columns = schema_info[schema_info["type"].str.contains("INT|REAL|FLOAT|NUMERIC", case=False, na=False)]["name"].tolist()
        return numeric_columns
    except Exception as e:
        st.error(f"Error retrieving numeric columns for table '{table_name}': {e}")
        return []

def generate_comparison_query(table_name, metric, compare_type, period1, period2):
    """Generate SQL query for comparison between two periods."""
    quoted_table_name = quote_table_name(table_name)
    query = f"""
    SELECT
        '{period1}' AS period, SUM({metric}) AS total
    FROM
        {quoted_table_name}_{compare_type.lower()}
    WHERE
        {compare_type.lower()} = '{period1}'
    UNION ALL
    SELECT
        '{period2}' AS period, SUM({metric}) AS total
    FROM
        {quoted_table_name}_{compare_type.lower()}
    WHERE
        {compare_type.lower()} = '{period2}'
    """
    return query

def main():
    st.title("Data Autobot: Analyze and Compare Data")
    uploaded_file = st.file_uploader("Upload your file (CSV or Excel)", type=["csv", "xlsx"])

    if uploaded_file:
        load_file(uploaded_file)

        # Retrieve available tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        available_tables = [row[0] for row in cursor.fetchall()]

        selected_table = st.selectbox("Select table to analyze:", available_tables)

        if selected_table:
            schema_columns = get_table_schema(selected_table)

            if schema_columns:
                # Dynamic Dropdown for Metrics
                numeric_columns = get_numeric_columns(selected_table)
                selected_metric = st.selectbox("Select metric to analyze:", numeric_columns if numeric_columns else ["No numeric columns available"])
                
                # Optional Columns to Display
                extra_columns = st.multiselect(
                    "Select additional columns to display:",
                    [col for col in schema_columns if col not in numeric_columns]
                )

                # Sort Options
                sort_order = st.radio("Sort order:", ["Highest", "Lowest"])
                sort_column = selected_metric if selected_metric != "No numeric columns available" else None

                # Number of Rows to Display
                num_rows = st.selectbox("Number of rows to display:", [5, 10, 25, 50])

                # Comparison Options
                enable_comparison = st.checkbox("Enable Comparison")
                if enable_comparison:
                    compare_type = st.selectbox("Select comparison type:", ["Weekly", "Monthly", "Quarterly", "Custom"])
                    if compare_type != "Custom":
                        periods = st.multiselect(f"Select two {compare_type.lower()} periods:", ["Period 1", "Period 2"])
                        if len(periods) == 2:
                            query = generate_comparison_query(selected_table, selected_metric, compare_type, periods[0], periods[1])
                            try:
                                comparison_result = pd.read_sql_query(query, conn)
                                comparison_result["Percentage Change (%)"] = (
                                    (comparison_result.iloc[1]["total"] - comparison_result.iloc[0]["total"]) / comparison_result.iloc[0]["total"]
                                ) * 100
                                st.write("### Comparison Results")
                                st.dataframe(comparison_result)

                                if st.checkbox("Generate Comparison Chart"):
                                    fig = px.bar(comparison_result, x="period", y="total", title="Comparison Chart")
                                    st.plotly_chart(fig)
                            except Exception as e:
                                st.error(f"Error executing comparison query: {e}")
                    else:
                        st.warning("Custom comparison is not fully implemented yet.")

                # Generate SQL Query
                if selected_metric and selected_metric != "No numeric columns available":
                    sql_query = f"""
                        SELECT {', '.join([selected_metric] + extra_columns)}
                        FROM {selected_table}
                        ORDER BY {selected_metric} {'DESC' if sort_order == 'Highest' else 'ASC'}
                        LIMIT {num_rows}
                    """
                    try:
                        result_df = pd.read_sql_query(sql_query, conn)
                        st.write("### Query Results")
                        st.dataframe(result_df)

                        # Optional Visualization
                        if st.checkbox("Generate Visualization"):
                            chart_type = st.selectbox("Select chart type:", ["Bar Chart", "Line Chart", "Scatter Plot"])
                            if chart_type == "Bar Chart":
                                fig = px.bar(result_df, x=extra_columns[0] if extra_columns else selected_metric, y=selected_metric, title="Bar Chart")
                                st.plotly_chart(fig)
                            elif chart_type == "Line Chart":
                                fig = px.line(result_df, x=extra_columns[0] if extra_columns else selected_metric, y=selected_metric, title="Line Chart")
                                st.plotly_chart(fig)
                            elif chart_type == "Scatter Plot":
                                fig = px.scatter(result_df, x=extra_columns[0] if extra_columns else selected_metric, y=selected_metric, title="Scatter Plot")
                                st.plotly_chart(fig)
                    except Exception as e:
                        st.error(f"Error executing query: {e}")
                else:
                    st.warning("Please select a valid metric to analyze.")

if __name__ == "__main__":
    main()

