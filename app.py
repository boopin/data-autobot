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

def quote_column_name(column_name):
    """Properly quote column names for SQLite."""
    return f'"{column_name}"'

def generate_combined_visualization(df, bar_metric, line_metric, x_column, title):
    """Generate combined bar and line visualization."""
    try:
        fig = px.bar(
            df, x=x_column, y=bar_metric, title=title, labels={x_column: "Time Period"}
        )
        if line_metric:
            fig.add_scatter(
                x=df[x_column], y=df[line_metric], mode="lines+markers", name=line_metric
            )
        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error generating combined visualization: {e}")

def generate_extended_visualization(table, bar_metric, line_metric, period_type):
    """Generate extended visualization for predefined time periods."""
    try:
        query = f"SELECT {period_type}, SUM({bar_metric}) AS {bar_metric}"
        if line_metric:
            query += f", SUM({line_metric}) AS {line_metric}"
        query += f" FROM {quote_table_name(table)} GROUP BY {period_type} ORDER BY {period_type}"
        df = pd.read_sql_query(query, conn)

        generate_combined_visualization(
            df,
            bar_metric,
            line_metric,
            period_type,
            f"{bar_metric} (Bar){' and ' + line_metric + ' (Line)' if line_metric else ''} Over {period_type.capitalize()}",
        )
    except Exception as e:
        st.error(f"Error generating extended visualization: {e}")

def process_uploaded_file(uploaded_file):
    """Process uploaded file and store it in the database."""
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, encoding="utf-8", engine="python", on_bad_lines="skip")
        else:
            df = pd.read_excel(uploaded_file, sheet_name=None)
        
        if isinstance(df, dict):
            for sheet_name, sheet_df in df.items():
                process_and_store(sheet_df, sheet_name)
        else:
            process_and_store(df, uploaded_file.name.split('.')[0])

        st.success("File successfully processed and saved to the database!")
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

def save_aggregated_view(df, table_name, period_col, suffix):
    """Save aggregated views by period."""
    try:
        if period_col in df.columns:
            agg_df = df.groupby(period_col).sum(numeric_only=True).reset_index()
            agg_table_name = f"{table_name}_{suffix}"
            agg_df.to_sql(agg_table_name, conn, if_exists="replace", index=False)
    except Exception as e:
        st.warning(f"Could not create aggregated table for '{suffix}': {e}")

def generate_analysis_ui():
    """Generate UI for data analysis."""
    st.header("Data Analysis")
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()
    selected_table = st.selectbox("Select table to analyze:", tables, key="table_select")
    
    if selected_table:
        columns_query = f"PRAGMA table_info({quote_table_name(selected_table)});"
        schema = pd.read_sql_query(columns_query, conn)
        columns = schema["name"].tolist()
        
        numeric_columns = [col for col in columns if col not in ["date", "week", "month", "quarter"]]
        
        st.subheader("Metric Selection")
        col1, col2 = st.columns(2)
        with col1:
            selected_metric = st.selectbox(
                "Primary metric for analysis:", 
                numeric_columns,
                key="primary_metric"
            )
        with col2:
            additional_columns = st.multiselect(
                "Additional columns for analysis:", 
                [col for col in columns if col != selected_metric],
                key="additional_cols"
            )
            
        if st.button("Run Analysis", key="run_analysis"):
            st.subheader("Analysis Results")
            run_analysis(selected_table, selected_metric, additional_columns)
            
        with st.expander("Generate Extended Time Period Visualization"):
            st.subheader("Time Period Analysis")
            bar_metric = st.selectbox(
                "Bar chart metric (required):", 
                numeric_columns,
                key="extended_bar_metric"
            )
            
            show_line_metric = st.checkbox("Add line metric?", key="show_extended_line_metric")
            line_metric = None
            if show_line_metric:
                line_metric = st.selectbox(
                    "Line chart metric:", 
                    numeric_columns,
                    key="extended_line_metric"
                )
                
            period_type = st.selectbox(
                "Time period:", 
                ["week", "month", "quarter"],
                key="extended_period_type"
            )
            
            if st.button("Generate Extended Visualization", key="generate_extended"):
                st.subheader("Time Period Visualization")
                generate_extended_visualization(selected_table, bar_metric, line_metric, period_type)
                
        with st.expander("Enable Comparison"):
            enable_comparison(selected_table, numeric_columns)

def run_analysis(table, metric, additional_columns):
    """Run analysis and generate results."""
    try:
        select_columns = [metric] + additional_columns
        query = f"SELECT {', '.join(select_columns)} FROM {quote_table_name(table)} ORDER BY {metric} DESC LIMIT 10"
        results = pd.read_sql_query(query, conn)
        st.dataframe(results)
        
        st.download_button(
            "Download Analysis Results",
            results.to_csv(index=False).encode('utf-8'),
            "analysis_results.csv",
            "text/csv"
        )
    except Exception as e:
        st.error(f"Error running analysis: {e}")

def enable_comparison(table_name, numeric_columns):
    """Enable comparison with custom names for periods."""
    st.header("Period Selection")
    col1, col2 = st.columns(2)
    with col1:
        start_date_1 = st.date_input("Start Date for Period 1")
        end_date_1 = st.date_input("End Date for Period 1")
        period_1_name = st.text_input("Custom Name for Period 1", "Period 1")
    with col2:
        start_date_2 = st.date_input("Start Date for Period 2")
        end_date_2 = st.date_input("End Date for Period 2")
        period_2_name = st.text_input("Custom Name for Period 2", "Period 2")

    st.header("Metric Selection")
    bar_metric = st.selectbox(
        "Bar chart metric (required):", 
        numeric_columns,
        key="comparison_bar_metric"
    )
    
    show_line_metric = st.checkbox("Add line metric?", key="show_comparison_line_metric")
    line_metric = None
    if show_line_metric:
        line_metric = st.selectbox(
            "Line chart metric:", 
            numeric_columns,
            key="comparison_line_metric"
        )
    
    if st.button("Generate Comparison", key="generate_comparison"):
        try:
            # Query data for both periods
            period1_query = f"""
                SELECT date, {bar_metric}
                {', ' + line_metric if line_metric else ''}
                FROM {quote_table_name(table_name)}
                WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
            """
            period2_query = f"""
                SELECT date, {bar_metric}
                {', ' + line_metric if line_metric else ''}
                FROM {quote_table_name(table_name)}
                WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}'
            """
            
            df1 = pd.read_sql_query(period1_query, conn)
            df2 = pd.read_sql_query(period2_query, conn)
            
            # Calculate aggregates
            agg1 = df1.agg({bar_metric: ['sum', 'mean', 'min', 'max']})
            agg2 = df2.agg({bar_metric: ['sum', 'mean', 'min', 'max']})
            if line_metric:
                agg1[line_metric] = df1[line_metric].agg(['sum', 'mean', 'min', 'max'])
                agg2[line_metric] = df2[line_metric].agg(['sum', 'mean', 'min', 'max'])
            
            # Display comparison tables
            st.header("Comparison Tables")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(period_1_name)
                st.dataframe(agg1)
                st.download_button(
                    "Download Period 1 Data",
                    df1.to_csv(index=False).encode('utf-8'),
                    f"{period_1_name.lower().replace(' ', '_')}_data.csv",
                    "text/csv"
                )
            with col2:
                st.subheader(period_2_name)
                st.dataframe(agg2)
                st.download_button(
                    "Download Period 2 Data",
                    df2.to_csv(index=False).encode('utf-8'),
                    f"{period_2_name.lower().replace(' ', '_')}_data.csv",
                    "text/csv"
                )
            
            # Create comparison visualization
            st.header("Comparison Visualization")
            fig = px.bar(
                pd.DataFrame({
                    'Period': [period_1_name, period_2_name],
                    bar_metric: [agg1[bar_metric]['sum'], agg2[bar_metric]['sum']]
                }),
                x='Period',
                y=bar_metric,
                title=f"Comparison of {bar_metric}"
            )
            
            if line_metric:
                fig.add_scatter(
                    x=['Period 1', 'Period 2'],
                    y=[agg1[line_metric]['sum'], agg2[line_metric]['sum']],
                    mode='lines+markers',
                    name=line_metric
                )
            
            st.plotly_chart(fig)
            
            # Display daily trends
            st.header("Daily Trends")
            df1['Period'] = period_1_name
            df2['Period'] = period_2_name
            combined_df = pd.concat([df1, df2])
            
            trend_fig = px.line(
                combined_df,
                x='date',
                y=bar_metric,
                color='Period',
                title=f"Daily Trends - {bar_metric}"
            )
            st.plotly_chart(trend_fig)
            
        except Exception as e:
            st.error(f"Error generating comparison: {e}")

def main():
    st.title("Data Autobot")
    st.write("Version 2.6.0")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    if uploaded_file:
        process_uploaded_file(uploaded_file)
        generate_analysis_ui()

if __name__ == "__main__":
    main()
