# App Version: 2.6.0
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
    st.write("Version: 2.6.0")

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
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].notnull()]

        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        save_aggregated_view(df, table_name, "week", "weekly")
        save_aggregated_view(df, table_name, "month", "monthly")
        save_aggregated_view(df, table_name, "quarter", "quarterly")

    df.to_sql(table_name, conn, if_exists="replace", index=False)
    st.write(f"Table '{table_name}' created in the database.")

def save_aggregated_view(df, table_name, period_col, suffix):
    """Save aggregated views by period."""
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
    st.write("**Version: 2.6.0**")

    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)

    if selected_table:
        columns_query = f"PRAGMA table_info({quote_table_name(selected_table)});"
        schema = pd.read_sql_query(columns_query, conn)
        columns = schema["name"].tolist()

        numerical_columns = [col for col in columns if pd.api.types.is_numeric_dtype(schema[schema["name"] == col].iloc[0])]
        non_numerical_columns = [col for col in columns if col not in numerical_columns]

        col1, col2, col3 = st.columns(3)

        with col1:
            selected_metric = st.selectbox("Select metric to analyze:", numerical_columns)

        with col2:
            additional_columns = st.multiselect("Additional columns to display:", non_numerical_columns)

        with col3:
            sort_order = st.selectbox("Sort by:", ["Highest", "Lowest"])
            row_limit = st.slider("Rows to display:", 5, 50, 10)

        with st.expander("Enable Comparison", expanded=False):
            compare_type = st.selectbox("Comparison Type:", ["Weekly", "Monthly", "Quarterly"])
            if compare_type:
                agg_table_name = f"{selected_table}_{compare_type.lower()}"
                periods_query = f"SELECT DISTINCT {compare_type.lower()} FROM {quote_table_name(agg_table_name)} ORDER BY {compare_type.lower()}"
                try:
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
                except Exception as e:
                    st.error(f"Error retrieving periods: {e}")

        if st.button("Run Analysis"):
            run_analysis(selected_table, selected_metric, additional_columns, sort_order, row_limit)

def run_analysis(table, metric, additional_columns, sort_order, row_limit):
    """Run the analysis and generate output."""
    select_columns = [metric] + additional_columns
    sort_clause = "DESC" if sort_order == "Highest" else "ASC"
    query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} ORDER BY {metric} {sort_clause} LIMIT {row_limit}"
    try:
        results = pd.read_sql_query(query, conn)
        st.dataframe(results)
    except Exception as e:
        st.error(f"Error executing query: {e}")

if __name__ == "__main__":
    main()
