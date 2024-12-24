import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Helper function to clean table names for SQLite
def clean_table_name(name):
    return name.strip().replace(" ", "_").lower()

# Preprocess data for aggregations
def preprocess_data(df):
    df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

# Create aggregations
def create_aggregations(df, table_name, conn):
    if "date" in df.columns:
        # Add month, quarter, and week columns
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        df["week"] = df["date"].dt.to_period("W").astype(str)
        
        # Save original table
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        
        # Save aggregated tables
        for period, agg_name in [("week", f"{table_name}_weekly"),
                                 ("month", f"{table_name}_monthly"),
                                 ("quarter", f"{table_name}_quarterly")]:
            agg_df = df.groupby(period).sum(numeric_only=True).reset_index()
            agg_df.to_sql(agg_name, conn, index=False, if_exists="replace")
    else:
        df.to_sql(table_name, conn, index=False, if_exists="replace")

# Main Streamlit App
def main():
    st.title("Data Autobot - Analyze Your Data")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["xlsx", "csv"])
    
    if uploaded_file:
        try:
            conn = sqlite3.connect(":memory:")  # In-memory SQLite database
            table_names = []

            if uploaded_file.name.endswith(".xlsx"):
                excel_data = pd.ExcelFile(uploaded_file)
                for sheet in excel_data.sheet_names:
                    df = excel_data.parse(sheet)
                    df = preprocess_data(df)
                    table_name = clean_table_name(sheet)
                    create_aggregations(df, table_name, conn)
                    table_names.append(table_name)
            elif uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
                df = preprocess_data(df)
                table_name = clean_table_name(uploaded_file.name.replace(".csv", ""))
                create_aggregations(df, table_name, conn)
                table_names.append(table_name)
            else:
                st.error("Unsupported file format. Please upload an Excel or CSV file.")
                return
            
            st.success("File successfully processed and saved to the database!")

            # Dropdown for table selection
            selected_table = st.selectbox("Select a Table for Analysis", table_names)

            if selected_table:
                # Check if the selected table has a date column
                try:
                    columns_info = pd.read_sql_query(f"PRAGMA table_info({selected_table})", conn)
                    available_columns = columns_info["name"].tolist()
                except Exception as e:
                    st.error(f"Error fetching schema for table '{selected_table}': {e}")
                    return

                if "date" in available_columns:
                    st.write("### Aggregation Options")
                    period = st.selectbox("Select Aggregation Period", ["Original", "Weekly", "Monthly", "Quarterly"])
                    if period != "Original":
                        selected_table = f"{selected_table}_{period.lower()}"

                # Allow user to select columns and filters
                st.write("### Query Builder")
                if available_columns:
                    selected_columns = st.multiselect("Select Columns to Display", available_columns, default=available_columns)
                    if selected_columns:
                        limit = st.number_input("Number of Records to Display", min_value=1, max_value=100, value=10)
                        sql_query = f"SELECT {', '.join(selected_columns)} FROM {selected_table} LIMIT {limit}"
                        
                        st.write("Generated Query:", sql_query)
                        query_result = pd.read_sql_query(sql_query, conn)
                        st.dataframe(query_result)
                    else:
                        st.warning("Please select at least one column to display.")
                else:
                    st.warning("No columns available for selection. Please check the uploaded file.")

        except Exception as e:
            st.error(f"Error loading file: {e}")
    else:
        st.info("Please upload a file to begin analysis.")

if __name__ == "__main__":
    main()
