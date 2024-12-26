# App Version: 2.8.0
import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go

# Configure SQLite connection
conn = sqlite3.connect(":memory:")

def quote_table_name(table_name):
    """Properly quote table names for SQLite."""
    return f'"{table_name}"'

def quote_column_name(column_name):
    """Properly quote column names for SQLite."""
    return f'"{column_name}"'

def get_table_columns(table_name, exclude=None):
    """Get columns of a table, excluding specified ones."""
    columns_query = f"PRAGMA table_info({quote_table_name(table_name)});"
    schema = pd.read_sql_query(columns_query, conn)
    columns = schema["name"].tolist()
    if exclude:
        columns = [col for col in columns if col not in exclude]
    return columns

def generate_individual_metric_analysis(table_name):
    """Generate UI for individual metrics analysis."""
    st.subheader("Individual Metrics Analysis")
    metric = st.selectbox(
        "Select metric to analyze:",
        get_table_columns(table_name),
        key="individual_metric"
    )
    additional_columns = st.multiselect(
        "Select additional columns to display:",
        get_table_columns(table_name, exclude=[metric]),
        key="additional_columns"
    )
    sort_order = st.radio("Sort order:", ["Highest", "Lowest"], index=0)
    row_limit = st.slider("Rows to display:", min_value=5, max_value=50, value=10)

    if st.button("Run Analysis", key="run_individual_analysis"):
        select_columns = [quote_column_name(metric)] + [quote_column_name(col) for col in additional_columns]
        sort_clause = "DESC" if sort_order == "Highest" else "ASC"
        query = f"""
        SELECT {', '.join(select_columns)}
        FROM {quote_table_name(table_name)}
        ORDER BY {quote_column_name(metric)} {sort_clause}
        LIMIT {row_limit};
        """
        results = pd.read_sql_query(query, conn)
        st.write("Query Results:")
        st.dataframe(results)

        if st.checkbox("Generate Visualization", key="individual_visualization"):
            generate_visualization(results, metric)

def generate_visualization(results, y_metric, optional_metric=None):
    """Generate combined bar and line visualization."""
    try:
        if not results.empty:
            fig = go.Figure()

            # Add bar chart
            fig.add_bar(x=results[results.columns[0]], y=results[y_metric], name=y_metric)

            # Add line chart if optional metric exists
            if optional_metric:
                fig.add_scatter(
                    x=results[results.columns[0]], y=results[optional_metric],
                    name=optional_metric, mode="lines+markers", yaxis="y2"
                )
                # Update layout for dual y-axis
                fig.update_layout(
                    yaxis=dict(title=y_metric),
                    yaxis2=dict(
                        title=optional_metric,
                        overlaying="y",
                        side="right"
                    ),
                    title=f"{y_metric} (Bar) and {optional_metric} (Line)"
                )
            else:
                fig.update_layout(
                    title=f"Visualization of {y_metric}"
                )

            st.plotly_chart(fig)
        else:
            st.warning("No data available for visualization.")
    except Exception as e:
        st.error(f"Error generating visualization: {e}")

def process_uploaded_file(uploaded_file):
    """Process uploaded file and store it in the database."""
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, encoding="utf-8", engine="python", on_bad_lines="skip")
        else:
            df = pd.read_excel(uploaded_file, sheet_name=None)
        
        if isinstance(df, dict):
            st.write("Detected multiple sheets in the uploaded file.")
            for sheet_name, sheet_df in df.items():
                process_and_store(sheet_df, sheet_name)
        else:
            process_and_store(df, uploaded_file.name.split('.')[0])

        st.success("File successfully processed and saved to the database!")
    except UnicodeDecodeError:
        st.error("File encoding not supported. Please ensure the file is UTF-8 encoded.")
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

    df = df.drop_duplicates()
    df.to_sql(table_name, conn, if_exists="replace", index=False)

def generate_extended_visualization_ui(table_name):
    """Generate UI for extended visualization."""
    with st.expander("Extended Visualization", expanded=False):
        metric_bar = st.selectbox(
            "Select metric for bar chart:",
            get_table_columns(table_name, exclude=["date"]),
            key="extended_metric_bar"
        )
        metric_line = st.selectbox(
            "Select metric for line chart (optional):",
            ["None"] + get_table_columns(table_name, exclude=["date"]),
            key="extended_metric_line"
        )
        time_period = st.selectbox("Select time period:", ["week", "month", "quarter"], key="extended_time_period")

        if st.button("Generate Extended Visualization", key="generate_extended_visualization"):
            query = f"""
            SELECT {time_period}, 
                   SUM({quote_column_name(metric_bar)}) AS {metric_bar}
                   {f", SUM({quote_column_name(metric_line)}) AS {metric_line}" if metric_line != "None" else ""}
            FROM {quote_table_name(table_name)}
            GROUP BY {time_period}
            ORDER BY {time_period};
            """
            results = pd.read_sql_query(query, conn)
            st.dataframe(results)
            generate_visualization(results, metric_bar, optional_metric=(metric_line if metric_line != "None" else None))

def generate_comparison_ui(table_name):
    """Generate UI for enabling and running comparisons."""
    with st.expander("Enable Comparison", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            start_date_1 = st.date_input("Start Date for Period 1")
            end_date_1 = st.date_input("End Date for Period 1")
        with col2:
            start_date_2 = st.date_input("Start Date for Period 2")
            end_date_2 = st.date_input("End Date for Period 2")

        custom_name_1 = st.text_input("Custom Name for Period 1", "Period 1")
        custom_name_2 = st.text_input("Custom Name for Period 2", "Period 2")

        col1, col2 = st.columns(2)
        with col1:
            metric_bar = st.selectbox(
                "Select metric for bar chart:",
                get_table_columns(table_name, exclude=["date"]),
                key="comparison_metric_bar"
            )
        with col2:
            metric_line = st.selectbox(
                "Select metric for line chart (optional):",
                ["None"] + get_table_columns(table_name, exclude=["date"]),
                key="comparison_metric_line"
            )

        if st.button("Generate Combined Visualization", key="generate_comparison"):
            query = f"""
            SELECT '{custom_name_1}' AS period, 
                   SUM({quote_column_name(metric_bar)}) AS {metric_bar}
                   {f", SUM({quote_column_name(metric_line)}) AS {metric_line}" if metric_line != "None" else ""}
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_1}' AND '{end_date_1}'
            UNION ALL
            SELECT '{custom_name_2}' AS period, 
                   SUM({quote_column_name(metric_bar)}) AS {metric_bar}
                   {f", SUM({quote_column_name(metric_line)}) AS {metric_line}" if metric_line != "None" else ""}
            FROM {quote_table_name(table_name)}
            WHERE date BETWEEN '{start_date_2}' AND '{end_date_2}';
            """
            results = pd.read_sql_query(query, conn)
            st.dataframe(results)
            generate_visualization(results, metric_bar, optional_metric=(metric_line if metric_line != "None" else None))

def main():
    st.title("Data Autobot")
    st.write("**Tagline:** Unlock insights at the speed of thought!")
    st.write("**Version:** 2.8.0")

    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])

    if uploaded_file:
        process_uploaded_file(uploaded_file)
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql_query(tables_query, conn)["name"].tolist()
        selected_table = st.selectbox("Select table to analyze:", tables, key="table_selector")

        if selected_table:
            generate_individual_metric_analysis(selected_table)
            generate_extended_visualization_ui(selected_table)
            generate_comparison_ui(selected_table)

if __name__ == "__main__":
    main()
