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
    """Generate combined bar and line visualization with enhanced formatting."""
    try:
        # Create the bar chart base
        fig = px.bar(
            df, x=x_column, y=bar_metric, 
            title=title, 
            labels={x_column: "Time Period"},
            opacity=0.7
        )
        
        if line_metric:
            # Add line chart with enhanced visibility
            fig.add_scatter(
                x=df[x_column], 
                y=df[line_metric], 
                mode="lines+markers", 
                name=line_metric,
                line=dict(
                    width=3,
                    color='rgb(0, 100, 255)'  # Bright blue for better visibility
                ),
                marker=dict(
                    size=10,
                    color='rgb(0, 100, 255)',
                    symbol='diamond'
                ),
                yaxis="y2"
            )
            
            # Update layout for better visibility
            fig.update_layout(
                yaxis2=dict(
                    overlaying="y",
                    side="right",
                    title=line_metric,
                    showgrid=False,  # Remove secondary grid for clarity
                    title_font=dict(color='rgb(0, 100, 255)')  # Match line color
                ),
                yaxis_title=bar_metric,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Ensure the line chart is plotted on top
            fig.data = [fig.data[1], fig.data[0]]
            
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error generating combined visualization: {e}")

def generate_extended_visualization(table, bar_metric, line_metric, period_type, max_rows=None, sort_order="DESC"):
    """Generate extended visualization for predefined time periods."""
    try:
        # Generate combined query for all metrics
        query = f"SELECT {period_type}, SUM({bar_metric}) AS {bar_metric}"
        if line_metric:
            query += f", SUM({line_metric}) AS {line_metric}"
        query += f" FROM {quote_table_name(table)} GROUP BY {period_type} ORDER BY {bar_metric} {sort_order}"
        if max_rows:
            query += f" LIMIT {max_rows}"
        
        df = pd.read_sql_query(query, conn)
        
        # Calculate period-over-period changes
        df[f'{bar_metric}_pct_change'] = df[bar_metric].pct_change() * 100
        if line_metric:
            df[f'{line_metric}_pct_change'] = df[line_metric].pct_change() * 100

        # Calculate additional statistics
        stats_df = pd.DataFrame()
        stats_df[f'{bar_metric}_stats'] = df[bar_metric].agg(['mean', 'min', 'max'])
        if line_metric:
            stats_df[f'{line_metric}_stats'] = df[line_metric].agg(['mean', 'min', 'max'])

        # Display visualizations
        st.header("Time Period Visualization")
        generate_combined_visualization(
            df,
            bar_metric,
            line_metric,
            period_type,
            f"{bar_metric} (Bar){' and ' + line_metric + ' (Line)' if line_metric else ''} Over {period_type.capitalize()}",
        )

        # Display tables with percentage changes
        st.header(f"{period_type.capitalize()} Breakdown")
        st.subheader("Detailed Data")
        
        # Format percentage changes
        display_df = df.copy()
        display_df[f'{bar_metric}_pct_change'] = display_df[f'{bar_metric}_pct_change'].round(2).astype(str) + '%'
        if line_metric:
            display_df[f'{line_metric}_pct_change'] = display_df[f'{line_metric}_pct_change'].round(2).astype(str) + '%'
        
        st.dataframe(display_df)
        st.download_button(
            f"Download {period_type.capitalize()} Data",
            df.to_csv(index=False).encode('utf-8'),
            f"time_period_analysis.csv",
            "text/csv"
        )

        st.subheader("Summary Statistics")
        st.dataframe(stats_df)
        st.download_button(
            f"Download Summary Statistics",
            stats_df.to_csv().encode('utf-8'),
            f"summary_statistics.csv",
            "text/csv"
        )

    except Exception as e:
        st.error(f"Error generating extended visualization: {e}")

def enable_comparison(table, numeric_columns):
    """Enable comparison between different time periods."""
    try:
        st.subheader("Period Comparison Configuration")
        
        # Select metrics for comparison
        metric = st.selectbox(
            "Select metric to compare:", 
            numeric_columns,
            key="comparison_metric"
        )
        
        # Select time periods
        col1, col2 = st.columns(2)
        with col1:
            period_type = st.selectbox(
                "Time period type:",
                ["week", "month", "quarter"],
                key="comparison_period_type"
            )
        with col2:
            num_periods = st.number_input(
                "Number of periods to compare:",
                min_value=2,
                max_value=12,
                value=3,
                key="comparison_num_periods"
            )
            
        if st.button("Generate Comparison", key="generate_comparison"):
            # Generate query for comparison
            query = f"""
                SELECT 
                    {period_type},
                    SUM({metric}) as {metric}
                FROM {quote_table_name(table)}
                GROUP BY {period_type}
                ORDER BY {period_type} DESC
                LIMIT {num_periods}
            """
            
            comparison_df = pd.read_sql_query(query, conn)
            comparison_df = comparison_df.sort_values(period_type)
            
            # Calculate period-over-period changes
            comparison_df['Value_Change'] = comparison_df[metric].diff()
            comparison_df['Percentage_Change'] = comparison_df[metric].pct_change() * 100
            
            # Display results
            st.subheader("Comparison Results")
            
            # Visualization with enhanced formatting
            fig = px.line(
                comparison_df, 
                x=period_type, 
                y=metric,
                title=f"{metric} Trend Over {period_type.capitalize()}s",
                markers=True
            )
            
            # Enhance line chart appearance
            fig.update_traces(
                line=dict(width=3, color='rgb(0, 100, 255)'),
                marker=dict(size=10, symbol='diamond')
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Format the dataframe for display
            display_df = comparison_df.copy()
            display_df['Value_Change'] = display_df['Value_Change'].round(2)
            display_df['Percentage_Change'] = display_df['Percentage_Change'].round(2).astype(str) + '%'
            
            # Detailed results table
            st.subheader("Detailed Comparison")
            st.dataframe(display_df)
            
            # Download option
            st.download_button(
                "Download Comparison Results",
                comparison_df.to_csv(index=False).encode('utf-8'),
                "period_comparison.csv",
                "text/csv"
            )
            
    except Exception as e:
        st.error(f"Error generating comparison: {e}")

def process_uploaded_file(uploaded_file):
    """Process uploaded Excel or CSV file."""
    try:
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
        
        # Create table name from uploaded file
        table_name = uploaded_file.name.split('.')[0].replace(' ', '_')
        
        # Save to SQLite
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        st.success(f"Successfully uploaded and processed {uploaded_file.name}")
        
    except Exception as e:
        st.error(f"Error processing file: {e}")

def run_analysis(table, metric, additional_columns, max_rows=10, sort_order="DESC"):
    """Run analysis and generate results."""
    try:
        select_columns = [metric] + additional_columns
        query = f"""
            SELECT {', '.join(select_columns)} 
            FROM {quote_table_name(table)} 
            ORDER BY {metric} {sort_order}
            LIMIT {max_rows}
        """
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
            
        # Enhanced row selection and sorting options
        col1, col2 = st.columns(2)
        with col1:
            max_rows = st.slider(
                "Number of rows to display", 
                min_value=1, 
                max_value=100, 
                value=10,
                help="Drag to select the number of rows you want to see in the output table"
            )
        with col2:
            sort_order = st.selectbox(
                "Sort order", 
                ["High to Low", "Low to High"], 
                index=0,
                help="Choose how to sort your data"
            )
            
        if st.button("Run Analysis", key="run_analysis"):
            st.subheader("Analysis Results")
            run_analysis(selected_table, selected_metric, additional_columns, max_rows, 
                        "DESC" if sort_order == "High to Low" else "ASC")
            
        st.markdown("---")
        st.markdown("# 📈 Generate Extended Time Period Visualization")
        st.markdown("### Transform your data into powerful time-based insights")
        with st.expander("Configure Time Period Analysis"):
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
            
            col1, col2 = st.columns(2)
            with col1:
                max_period_rows = st.slider(
                    "Number of periods to display", 
                    min_value=1, 
                    max_value=100, 
                    value=50,
                    help="Drag to select the number of time periods to include"
                )
            with col2:
                period_sort_order = st.selectbox(
                    "Sort periods by", 
                    ["High to Low", "Low to High"], 
                    index=0,
                    help="Choose how to sort your time periods"
                )
            
            if st.button("Generate Extended Visualization", key="generate_extended"):
                generate_extended_visualization(
                    selected_table, 
                    bar_metric, 
                    line_metric, 
                    period_type,
                    max_period_rows,
                    "DESC" if period_sort_order == "High to Low" else "ASC"
                )
        
        st.markdown("---")
        st.markdown("# 🔄 Enable Comparison")
        st.markdown("### Discover insights through powerful period-over-period comparisons")
        with st.expander("Configure Period Comparison"):
            enable_comparison(selected_table, numeric_columns)

def main():
    st.title("📊 Data Autobot")
    st.markdown("### Your AI-Powered Data Analytics Suite")
    st.markdown("Unlock the power of your data with intelligent analysis, advanced visualizations, and automated insights.")
    st.write("Version 2.6.0")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    if uploaded_file:
        process_uploaded_file(uploaded_file)
        generate_analysis_ui()

if __name__ == "__main__":
    main()
