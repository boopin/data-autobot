import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# Function to preprocess data
def preprocess_data(df):
    df.columns = [col.lower().replace(" ", "_") for col in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["week"] = df["date"].dt.strftime("%U")
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    return df

# Function to create aggregations
def create_aggregations(df, table_name, conn):
    if "date" in df.columns:
        df_weekly = df.groupby(["week"]).sum().reset_index()
        df_monthly = df.groupby(["month"]).sum().reset_index()
        df_quarterly = df.groupby(["quarter"]).sum().reset_index()
        df_weekly.to_sql(f"{table_name}_weekly", conn, if_exists="replace", index=False)
        df_monthly.to_sql(f"{table_name}_monthly", conn, if_exists="replace", index=False)
        df_quarterly.to_sql(f"{table_name}_quarterly", conn, if_exists="replace", index=False)

# Function for comparison query
def comparison_query(selected_table, granularity, first_period, second_period, conn):
    try:
        table_name = f"{selected_table}_{granularity.lower()}"
        query = f"""
            SELECT SUM(impressions_total) AS total, '{first_period}' AS period FROM {table_name} WHERE {granularity.lower()} = '{first_period}'
            UNION ALL
            SELECT SUM(impressions_total) AS total, '{second_period}' AS period FROM {table_name} WHERE {granularity.lower()} = '{second_period}'
        """
        st.info(f"Generated Query: {query}")
        df_result = pd.read_sql_query(query, conn)
        st.write("### Comparison Results")
        st.dataframe(df_result)
    except Exception as e:
        st.error(f"Error: {e}")

# Main function
def main():
    st.title("Data Analysis with Comparisons")

    uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "csv"])
    if not uploaded_file:
        st.info("Please upload a file.")
        return

    try:
        conn = sqlite3.connect(":memory:")

        if uploaded_file.name.endswith(".xlsx"):
            xl = pd.ExcelFile(uploaded_file)
            for sheet_name in xl.sheet_names:
                df = xl.parse(sheet_name)
                df = preprocess_data(df)
                df.to_sql(sheet_name.lower(), conn, if_exists="replace", index=False)
                create_aggregations(df, sheet_name.lower(), conn)

        elif uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            df = preprocess_data(df)
            table_name = uploaded_file.name.split(".")[0].lower()
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            create_aggregations(df, table_name, conn)

        st.success("Data successfully processed and saved to the database!")

        # Table selection
        table_names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")]
        selected_table = st.selectbox("Select Table for Analysis", table_names)

        # Analysis Options
        analysis_mode = st.radio("Select Analysis Mode", ["Query", "Comparison"])
        
        if analysis_mode == "Query":
            # Allow user to write queries
            st.write("Write your SQL query below:")
            user_query = st.text_area("SQL Query")
            if st.button("Run Query"):
                try:
                    result = pd.read_sql_query(user_query, conn)
                    st.dataframe(result)
                except Exception as e:
                    st.error(f"Error: {e}")
        
        elif analysis_mode == "Comparison":
            granularity = st.selectbox("Select Granularity", ["Weekly", "Monthly", "Quarterly"])
            first_period = st.text_input(f"Select First {granularity}")
            second_period = st.text_input(f"Select Second {granularity}")
            if st.button("Run Comparison"):
                comparison_query(selected_table, granularity, first_period, second_period, conn)

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
