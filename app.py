import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Initialize Streamlit app
st.title("Data Analysis Tool")

def preprocess_data(df):
    """Preprocess the DataFrame for SQL operations."""
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_").str.replace("(", "").str.replace(")", "")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def create_aggregations(df, table_name, conn):
    """
    Create aggregated tables (weekly, monthly, quarterly) and save them to the database.
    """
    if "date" not in df.columns:
        return  # Skip if there is no 'date' column
    
    # Ensure the 'date' column is datetime
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isnull().all():
        raise ValueError("The 'date' column contains no valid datetime values.")
    
    periods = {
        "weekly": df["date"].dt.to_period("W").dt.start_time,
        "monthly": df["date"].dt.to_period("M").dt.start_time,
        "quarterly": df["date"].dt.to_period("Q").dt.start_time,
    }
    
    for period, period_values in periods.items():
        agg_df = df.copy()
        agg_df["period"] = period_values
        numeric_columns = agg_df.select_dtypes(include=["number"]).columns
        agg_df = agg_df.groupby("period")[numeric_columns].sum().reset_index()
        table_name_agg = f"{table_name}_{period}"
        agg_df.to_sql(table_name_agg, conn, index=False, if_exists="replace")

def main():
    st.subheader("Upload Data Files")
    uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            conn = sqlite3.connect(":memory:")
            table_names = []

            if uploaded_file.name.endswith(".xlsx"):
                excel_data = pd.ExcelFile(uploaded_file)
                for sheet in excel_data.sheet_names:
                    df = pd.read_excel(excel_data, sheet_name=sheet)
                    df = preprocess_data(df)
                    table_name = sheet.lower().replace(" ", "_")
                    df.to_sql(table_name, conn, index=False, if_exists="replace")
                    create_aggregations(df, table_name, conn)
                    table_names.append(table_name)

            elif uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
                df = preprocess_data(df)
                table_name = uploaded_file.name.replace(".csv", "").lower().replace(" ", "_")
                df.to_sql(table_name, conn, index=False, if_exists="replace")
                create_aggregations(df, table_name, conn)
                table_names.append(table_name)
            
            st.success("File successfully processed and saved to the database!")
            st.write("Available Tables:", table_names)

            selected_table = st.selectbox("Select a table for analysis", table_names)
            if selected_table:
                schema_query = f"PRAGMA table_info({selected_table});"
                schema_info = pd.read_sql_query(schema_query, conn)
                st.write("Schema Information:")
                st.dataframe(schema_info)

                st.subheader("Build Your Query")
                columns = schema_info["name"].tolist()
                date_range = st.selectbox("Select Date Range", ["Weekly", "Monthly", "Quarterly", "Custom"])
                metrics = st.multiselect("Select Metrics", columns)
                top_n = st.selectbox("Select Top N Rows", [5, 10, 25, 50])

                if st.button("Run Query"):
                    period_table = f"{selected_table}_{date_range.lower()}"
                    query = f"SELECT {', '.join(metrics)} FROM {period_table} ORDER BY {metrics[-1]} DESC LIMIT {top_n}"
                    st.write("Generated Query:", query)
                    try:
                        result = pd.read_sql_query(query, conn)
                        st.write("Query Result:")
                        st.dataframe(result)
                    except Exception as e:
                        st.error(f"Query failed: {e}")

        except Exception as e:
            st.error(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
