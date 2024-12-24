import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta


def safe_table_name(table_name):
    """Properly format the table name for SQLite queries."""
    return f'"{table_name.replace("\"", "")}"'  # Properly escape double quotes for valid SQLite quoting


def load_file_to_db(uploaded_file, conn):
    """Load uploaded file into SQLite database."""
    if uploaded_file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(uploaded_file)
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
            create_aggregations(df, sheet_name.lower(), conn)
    elif uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]
        table_name = uploaded_file.name.replace(".csv", "").lower()
        create_aggregations(df, table_name, conn)


def create_aggregations(df, table_name, conn):
    """Create weekly, monthly, and quarterly aggregations for tables with a 'date' column."""
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if df["date"].isnull().all():
            raise ValueError(f"The 'date' column in table '{table_name}' contains no valid date values.")
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        for period, group_col in [("weekly", "week"), ("monthly", "month"), ("quarterly", "quarter")]:
            agg_df = df.groupby(group_col).sum(numeric_only=True).reset_index()
            agg_df.to_sql(safe_table_name(f"{table_name}_{period}"), conn, index=False, if_exists="replace")

    df.to_sql(safe_table_name(table_name), conn, index=False, if_exists="replace")


def display_schema(table_name, conn):
    """Display schema of a table."""
    try:
        query = f"PRAGMA table_info({safe_table_name(table_name)})"
        schema = pd.read_sql(query, conn)
        return schema["name"].tolist()
    except Exception as e:
        raise ValueError(f"Error loading schema for table '{table_name}': {e}")


def generate_query(table_name, date_filter, columns_to_display, comparison=None):
    """Generate SQL query dynamically."""
    if comparison:
        comp_period1, comp_filter1, comp_period2, comp_filter2 = comparison
        query = f"""
        SELECT SUM(impressions_total) as total, '{comp_period1}' as period FROM {safe_table_name(table_name)} WHERE {comp_filter1}
        UNION ALL
        SELECT SUM(impressions_total) as total, '{comp_period2}' as period FROM {safe_table_name(table_name)} WHERE {comp_filter2}
        """
    else:
        where_clause = f"WHERE {date_filter}" if date_filter else ""
        query = f"SELECT {', '.join(columns_to_display)} FROM {safe_table_name(table_name)} {where_clause} ORDER BY {columns_to_display[-1]} DESC LIMIT 10"
    return query


def main():
    st.title("Data Analysis and Comparison Tool")

    uploaded_file = st.file_uploader("Upload your data file (CSV or Excel):", type=["csv", "xlsx"])
    if not uploaded_file:
        st.info("Please upload a file to get started.")
        return

    # SQLite connection
    conn = sqlite3.connect(":memory:")
    try:
        load_file_to_db(uploaded_file, conn)
        st.success("File successfully processed and loaded into the database!")

        # Available tables
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
        table_names = tables["name"].tolist()
        selected_table = st.selectbox("Select a table for analysis:", table_names)

        # Show table schema
        schema_columns = display_schema(selected_table, conn)
        st.write(f"Schema for {selected_table}: {schema_columns}")

        # Check for 'date' column dynamically
        has_date_column = "date" in schema_columns

        # Filters and options based on schema
        if has_date_column:
            period_type = st.selectbox("Select a date range for analysis:", ["Daily", "Weekly", "Monthly", "Quarterly", "Custom"])
            if period_type == "Custom":
                start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
                end_date = st.date_input("End Date", value=datetime.today())
                date_filter = f"date BETWEEN '{start_date}' AND '{end_date}'"
            else:
                date_filter = None

            # Comparison mode
            comparison_mode = st.checkbox("Enable Comparison")
            if comparison_mode:
                if period_type in ["Quarterly", "Monthly", "Weekly"]:
                    comp_period1 = st.selectbox(f"Select first {period_type}:", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"] if period_type == "Quarterly" else ["2024-01", "2024-02", "2024-03"] if period_type == "Monthly" else ["2024-W01", "2024-W02", "2024-W03"])
                    comp_period2 = st.selectbox(f"Select second {period_type}:", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"] if period_type == "Quarterly" else ["2024-01", "2024-02", "2024-03"] if period_type == "Monthly" else ["2024-W01", "2024-W02", "2024-W03"])
                    comparison = (comp_period1, f"{period_type.lower()} = '{comp_period1}'", comp_period2, f"{period_type.lower()} = '{comp_period2}'")
                else:
                    st.warning("Comparison mode is only available for Weekly, Monthly, or Quarterly selections.")
                    comparison = None
            else:
                comparison = None
        else:
            st.info("This table does not contain a 'date' column. Aggregation options are disabled.")
            period_type = None
            date_filter = None
            comparison = None

        # Column selection
        columns_to_display = st.multiselect("Select columns to display:", schema_columns, default=schema_columns[:3])

        # Generate and execute query
        query = generate_query(selected_table, date_filter, columns_to_display, comparison)
        st.info(f"Generated Query:\n{query}")

        try:
            data = pd.read_sql(query, conn)
            st.write("### Query Results")
            st.dataframe(data)

            # Option to visualize
            if st.checkbox("Show Visualization"):
                column_to_visualize = st.selectbox("Select column for visualization:", columns_to_display)
                fig = px.bar(data, x="period" if comparison else "date", y=column_to_visualize, title="Visualization")
                st.plotly_chart(fig)
        except Exception as e:
            st.error(f"Error executing query: {e}")
    except Exception as e:
        st.error(f"Error loading file: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
