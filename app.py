# App Version: 1.3.2
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
                create_aggregated_tables(df, sheet_name.lower().replace(" ", "_"))
        elif file.name.endswith(".csv"):
            df = pd.read_csv(file)
            df = preprocess_column_names(df)
            table_name = file.name.replace(".csv", "").lower().replace(" ", "_")
            create_aggregated_tables(df, table_name)
        st.success("File successfully processed and loaded into the database!")
    except Exception as e:
        st.error(f"Error loading file: {e}")

def create_aggregated_tables(df, table_name):
    """Create weekly, monthly, and quarterly aggregated tables."""
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        # Identify numeric columns for aggregation
        numeric_columns = df.select_dtypes(include=["number"]).columns

        # Add period columns back after filtering
        if numeric_columns.any():
            df_weekly = df.groupby("week")[numeric_columns].sum().reset_index()
            df_monthly = df.groupby("month")[numeric_columns].sum().reset_index()
            df_quarterly = df.groupby("quarter")[numeric_columns].sum().reset_index()

            # Save tables to SQLite
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            df_weekly.to_sql(f"{table_name}_weekly", conn, index=False, if_exists="replace")
            df_monthly.to_sql(f"{table_name}_monthly", conn, index=False, if_exists="replace")
            df_quarterly.to_sql(f"{table_name}_quarterly", conn, index=False, if_exists="replace")
        else:
            st.warning(f"No numeric columns found for aggregation in table {table_name}.")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
    else:
        df.to_sql(table_name, conn, index=False, if_exists="replace")

# Rest of the app code remains the same...

if __name__ == "__main__":
    main()
