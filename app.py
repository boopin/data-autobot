# App Version: 1.4.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Initialize SQLite connection
conn = sqlite3.connect(":memory:")

APP_VERSION = "1.4.0"

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

def main():
    # Display version number in the app
    st.sidebar.title(f"Data Autobot v{APP_VERSION}")
    st.title(f"Data Autobot v{APP_VERSION}")
    st.write("Welcome to Data Autobot! Upload your data file to begin analysis.")

    # File upload
    uploaded_file = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx"])
    if uploaded_file:
        load_file(uploaded_file)

        # Display available tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        selected_table = st.selectbox("Select a table to analyze:", tables)

        if selected_table:
            st.write(f"Schema for table `{selected_table}`:")
            schema_query = f"PRAGMA table_info({quote_table_name(selected_table)})"
            schema = pd.read_sql_query(schema_query, conn)
            st.dataframe(schema)

            # Metrics selection
            st.write("Select metric to analyze:")
            columns_query = f"PRAGMA table_info({quote_table_name(selected_table)})"
            columns = pd.read_sql_query(columns_query, conn)["name"].tolist()
            selected_metric = st.selectbox("Metric:", columns)

            # Sort order
            sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
            sort_clause = "DESC" if sort_order == "Highest" else "ASC"

            # Number of rows
            row_limit = st.slider("Number of rows to display:", 5, 50, 10)

            # Option to generate visualizations
            generate_chart = st.checkbox("Generate Visualization")

            if st.button("Run Analysis"):
                if selected_metric:
                    query = f"SELECT * FROM {quote_table_name(selected_table)} ORDER BY {selected_metric} {sort_clause} LIMIT {row_limit}"
                    st.write("Generated Query:")
                    st.code(query)
                    try:
                        results = pd.read_sql_query(query, conn)
                        st.write("Query Results:")
                        st.dataframe(results)

                        # Generate visualization if selected
                        if generate_chart:
                            fig = px.bar(results, x=results.columns[0], y=selected_metric, title="Visualization")
                            st.plotly_chart(fig)
                    except Exception as e:
                        st.error(f"Error executing query: {e}")
                else:
                    st.warning("Please select a metric to analyze.")
    else:
        st.info("Upload a file to get started.")

if __name__ == "__main__":
    main()
