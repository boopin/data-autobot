import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
from datetime import datetime

# Helper function to check if a column exists in a table
def check_date_column(table_schema):
    return 'date' in table_schema

# Helper function for visualizations
def visualize_data(df, x_column, y_column, title="Visualization"):
    """Generates a Plotly bar chart."""
    fig = px.bar(df, x=x_column, y=y_column, title=title)
    st.plotly_chart(fig)

# Main function
def main():
    st.title("Data Analysis App with DuckDB and Plotly")

    # File upload
    uploaded_file = st.file_uploader("Upload your file (CSV or Excel)", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to proceed.")
        return

    conn = duckdb.connect(database=':memory:', read_only=False)
    table_names = []

    try:
        # Load data into DuckDB
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            table_name = uploaded_file.name.split('.')[0]
            conn.register(table_name, df)
            table_names.append(table_name)
        elif uploaded_file.name.endswith(".xlsx"):
            excel_data = pd.ExcelFile(uploaded_file)
            for sheet in excel_data.sheet_names:
                df = excel_data.parse(sheet)
                conn.register(sheet.lower().replace(" ", "_"), df)
                table_names.append(sheet.lower().replace(" ", "_"))
        
        st.success("Data successfully loaded into DuckDB!")

        # Select table
        selected_table = st.selectbox("Select a table to analyze:", table_names)

        # Get table schema
        query = f"PRAGMA table_info({selected_table})"
        schema_df = conn.execute(query).fetchdf()
        column_names = schema_df['name'].tolist()

        # Check for a date column
        has_date_column = check_date_column(column_names)

        # Dropdowns for dynamic menus
        if has_date_column:
            date_granularity = st.selectbox("Select date granularity:", ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"])
            st.info(f"Selected Date Granularity: {date_granularity}")
        else:
            st.warning(f"Table '{selected_table}' does not have a 'date' column. Date-based options are hidden.")

        # Query customization
        selected_columns = st.multiselect("Select columns to display:", column_names, default=column_names[:5])
        if not selected_columns:
            st.error("Please select at least one column.")
            return

        top_n = st.selectbox("Select number of rows to display:", [5, 10, 25, 50], index=1)

        # Custom query generation
        query = f"SELECT {', '.join(selected_columns)} FROM {selected_table} LIMIT {top_n}"
        st.info(f"Generated Query: {query}")

        # Execute query
        try:
            query_result = conn.execute(query).fetchdf()
            st.write("### Query Results")
            st.dataframe(query_result)

            # Visualization toggle
            if st.checkbox("Show as chart"):
                x_column = st.selectbox("Select X-axis column:", selected_columns)
                y_column = st.selectbox("Select Y-axis column:", selected_columns)
                visualize_data(query_result, x_column=x_column, y_column=y_column)

        except Exception as e:
            st.error(f"Query Error: {e}")

    except Exception as e:
        st.error(f"Error loading file: {e}")

if __name__ == "__main__":
    main()

