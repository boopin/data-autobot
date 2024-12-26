# App Version: 2.6.1
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

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
            df, x=x_column, y=bar_metric, 
            title=title, 
            labels={x_column: "Time Period"}
        )
        
        # Add line trace with markers and dashed line
        fig.add_scatter(
            x=df[x_column], 
            y=df[line_metric], 
            mode="lines+markers",
            name=line_metric,
            line=dict(dash='dash')
        )
        
        # Update layout for better readability
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error generating combined visualization: {e}")

def generate_extended_visualization(table, bar_metric, line_metric, period_type):
    """Generate extended visualization for predefined time periods."""
    try:
        query = f"""
            SELECT {period_type}, 
                   SUM({bar_metric}) AS {bar_metric}, 
                   SUM({line_metric}) AS {line_metric} 
            FROM {quote_table_name(table)} 
            GROUP BY {period_type} 
            ORDER BY {period_type}
        """
        df = pd.read_sql_query(query, conn)

        generate_combined_visualization(
            df,
            bar_metric,
            line_metric,
            period_type,
            f"{bar_metric} (Bar) and {line_metric} (Line) Over {period_type.capitalize()}",
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
    # Clean column names
    df.columns = [col.lower().strip().replace(" ", "_").replace("(", "").replace(")", "") 
                 for col in df.columns]

    # Process date column if it exists
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].notnull()]
        df["week"] = df["date"].dt.to_period("W").astype(str)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        
        # Create aggregated views
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
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)

    if selected_table:
        columns_query = f"PRAGMA table_info({quote_table_name(selected_table)});"
        schema = pd.read_sql_query(columns_query, conn)
        columns = schema["name"].tolist()

        col1, col2 = st.columns(2)
        with col1:
            selected_metric = st.selectbox(
                "Select metric to analyze:", 
                [col for col in columns if col not in ["date", "week", "month", "quarter"]]
            )
        with col2:
            additional_columns = st.multiselect(
                "Select additional columns:", 
                [col for col in columns if col != selected_metric]
            )

        if st.button("Run Analysis"):
            run_analysis(selected_table, selected_metric, additional_columns)

        with st.expander("Generate Extended Time Period Visualization"):
            bar_metric = st.selectbox(
                "Select metric for bar chart:", 
                [col for col in columns if col not in ["date", "week", "month", "quarter"]]
            )
            line_metric = st.selectbox(
                "Select metric for line chart:", 
                [col for col in columns if col not in ["date", "week", "month", "quarter"]]
            )
            period_type = st.selectbox("Select time period:", ["week", "month", "quarter"])

            if st.button("Generate Extended Visualization"):
                generate_extended_visualization(selected_table, bar_metric, line_metric, period_type)

        with st.expander("Enable Comparison"):
            enable_comparison(selected_table)

def run_analysis(table, metric, additional_columns):
    """Run analysis and generate results."""
    try:
        select_columns = [metric] + additional_columns
        query = f"""
            SELECT {', '.join(quote_column_name(col) for col in select_columns)} 
            FROM {quote_table_name(table)} 
            ORDER BY {quote_column_name(metric)} DESC 
            LIMIT 10
        """
        results = pd.read_sql_query(query, conn)
        st.dataframe(results)
    except Exception as e:
        st.error(f"Error running analysis: {e}")

def enable_comparison(table_name):
    """Enable comparison with custom names for periods."""
    # Get columns from the table
    columns_query = f"PRAGMA table_info({quote_table_name(table_name)});"
    schema = pd.read_sql_query(columns_query, conn)
    numeric_columns = [col for col in schema["name"].tolist() 
                      if col not in ["date", "week", "month", "quarter"]]
    
    col1, col2 = st.columns(2)
    with col1:
        start_date_1 = st.date_input("Start Date for Period 1")
        end_date_1 = st.date_input("End Date for Period 1")
        period_1_name = st.text_input("Custom Name for Period 1", "Period 1")
    with col2:
        start_date_2 = st.date_input("Start Date for Period 2")
        end_date_2 = st.date_input("End Date for Period 2")
        period_2_name = st.text_input("Custom Name for Period 2", "Period 2")

    bar_metric = st.selectbox("Select metric for bar chart:", numeric_columns)
    line_metric = st.selectbox("Select metric for line chart:", numeric_columns)
    
    if st.button("Generate Combined Visualization"):
        try:
            # Create queries for both periods
            query1 = f"""
                SELECT date, {quote_column_name(bar_metric)}, {quote_column_name(line_metric)} 
                FROM {quote_table_name(table_name)}
                WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
            """
            query2 = f"""
                SELECT date, {quote_column_name(bar_metric)}, {quote_column_name(line_metric)}
                FROM {quote_table_name(table_name)}
                WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}'
            """
            
            df1 = pd.read_sql_query(query1, conn)
            df2 = pd.read_sql_query(query2, conn)
            
            # Combine the data and add period labels
            df1['period'] = period_1_name
            df2['period'] = period_2_name
            combined_df = pd.concat([df1, df2])
            
            # Create the visualization
            fig = px.bar(
                combined_df,
                x='date',
                y=bar_metric,
                color='period',
                title=f"Comparison of {bar_metric} and {line_metric}",
                barmode='group'
            )
            
            # Add line traces for both periods
            for period in [period_1_name, period_2_name]:
                period_data = combined_df[combined_df['period'] == period]
                fig.add_scatter(
                    x=period_data['date'],
                    y=period_data[line_metric],
                    mode='lines+markers',
                    name=f"{period} ({line_metric})",
                    line=dict(dash='dash')
                )
            
            # Update layout for better readability
            fig.update_layout(
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis_title="Date",
                yaxis_title="Value"
            )
            
            st.plotly_chart(fig)
            
        except Exception as e:
            st.error(f"Error generating comparison visualization: {e}")

def main():
    st.title("Data Autobot")
    st.write("Version 2.6.1")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    if uploaded_file:
        process_uploaded_file(uploaded_file)
        generate_analysis_ui()

if __name__ == "__main__":
    main()
