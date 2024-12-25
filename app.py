# App Version: 2.5.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'

def generate_visualization(results, x_col, y_col):
    """Generate visualization for results."""
    if not results.empty:
        fig = px.bar(results, x=x_col, y=y_col, title=f"Visualization of {y_col}")
        st.plotly_chart(fig)
    else:
        st.warning("No data available to generate visualization.")

def main():
    st.title("Data Autobot")
    st.write("Version: 2.5.0")

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
    """Process the DataFrame and store it in the SQLite database with aggregations."""
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].notnull()]  # Remove rows with invalid dates

        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        save_aggregated_view(df, table_name, "week", "weekly")
        save_aggregated_view(df, table_name, "month", "monthly")
        save_aggregated_view(df, table_name, "quarter", "quarterly")

    df = df.drop_duplicates()
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    st.write(f"Table '{table_name}' created in the database.")

def save_aggregated_view(df, table_name, period_col, suffix):
    """Save aggregated views by period (weekly, monthly, quarterly)."""
    try:
        if period_col in df.columns:
            agg_df = df.groupby(period_col).sum(numeric_only=True).reset_index()
            agg_table_name = f"{table_name}_{suffix}"
            agg_df.to_sql(agg_table_name, conn, if_exists="replace", index=False)
            st.write(f"Aggregated table '{agg_table_name}' created successfully.")
    except Exception as e:
        st.warning(f"Could not create aggregated table for '{suffix}': {e}")

def generate_analysis_ui():
    """Generate UI for data analysis."""
    st.write("**Version: 2.5.0**")

    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)

    if selected_table:
        columns_query = f"PRAGMA table_info({quote_table_name(selected_table)});"
        schema = pd.read_sql_query(columns_query, conn)
        columns = schema["name"].tolist()

        st.write(f"Schema for '{selected_table}': {columns}")

        col1, col2 = st.columns(2)

        with col1:
            selected_metric = st.selectbox("Select metric to analyze:", [col for col in columns if col not in ["date", "week", "month", "quarter"]])

        with col2:
            sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
            row_limit = st.slider("Rows to display:", 5, 50, 10)

        with st.expander("Enable Comparison", expanded=False):
            compare_type = st.selectbox("Comparison Type:", ["Weekly", "Monthly", "Quarterly"])
            if compare_type:
                agg_table_name = f"{selected_table}_{compare_type.lower()}"
                try:
                    periods_query = f"SELECT DISTINCT {compare_type.lower()} FROM {quote_table_name(agg_table_name)} ORDER BY {compare_type.lower()}"
                    periods = pd.read_sql_query(periods_query, conn)[compare_type.lower()].tolist()

                    period_1 = st.selectbox("Select Period 1:", periods)
                    period_2 = st.selectbox("Select Period 2:", periods)

                    if period_1 and period_2:
                        compare_query = f"""
                        SELECT '{period_1}' AS period, SUM({selected_metric}) AS total
                        FROM {quote_table_name(agg_table_name)} WHERE {compare_type.lower()} = '{period_1}'
                        UNION ALL
                        SELECT '{period_2}' AS period, SUM({selected_metric}) AS total
                        FROM {quote_table_name(agg_table_name)} WHERE {compare_type.lower()} = '{period_2}'
                        """
                        comparison_results = pd.read_sql_query(compare_query, conn)
                        comparison_results["% Change"] = (
                            comparison_results["total"].pct_change().fillna(0) * 100
                        ).round(2)
                        st.write("Comparison Results:")
                        st.dataframe(comparison_results)

                        if st.checkbox("Generate Visualization for Comparison"):
                            generate_visualization(comparison_results, "period", "total")
                except Exception as e:
                    st.error(f"Error retrieving periods: {e}")

        if st.button("Run Analysis"):
            if selected_metric:
                run_analysis(selected_table, selected_metric, sort_order, row_limit)
            else:
                st.warning("Please select a metric to analyze.")

def run_analysis(table, metric, sort_order, row_limit):
    """Run the analysis and generate output."""
    try:
        sort_clause = "DESC" if sort_order == "Highest" else "ASC"
        query = f"SELECT * FROM {quote_table_name(table)} ORDER BY {metric} {sort_clause} LIMIT {row_limit}"
        
        st.write("Generated Query:")
        st.code(query)

        results = pd.read_sql_query(query, conn)
        st.write("Query Results:")
        st.dataframe(results)

        if st.checkbox("Generate Visualization"):
            generate_visualization(results, results.columns[0], metric)
    except Exception as e:
        st.error(f"Error executing query: {e}")

if __name__ == "__main__":
    main()

