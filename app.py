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
        query += f" FROM {quote_table_name(table)} GROUP BY {period_type} ORDER BY {bar_metric} DESC"
        df = pd.read_sql_query(query, conn)

        # Sorting & Row Selection
        st.markdown("### Sort and Select Rows")
        num_rows = st.slider("Number of rows to display", 5, len(df), 10)
        df = df.head(num_rows)

        st.markdown(f"### {period_type.capitalize()} Breakdown")
        st.dataframe(df)

        st.download_button(
            f"Download {period_type.capitalize()} Data",
            df.to_csv(index=False).encode('utf-8'),
            f"{period_type}_analysis.csv",
            "text/csv"
        )

        st.markdown(f"### Visualization of {bar_metric} (Bar) and {line_metric} (Line)")
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
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)

        table_name = uploaded_file.name.split(".")[0]
        df.to_sql(table_name, conn, index=False, if_exists="replace")

        st.success(f"File '{uploaded_file.name}' successfully processed.")
        return table_name, df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None, None

def generate_analysis_ui():
    """Generate UI for data analysis."""
    st.markdown("# **Data Analysis**")
    tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

    selected_table = st.selectbox("Select table to analyze:", tables)
    if selected_table:
        st.markdown("## **Generate Extended Time Period Visualization**")
        bar_metric = st.selectbox("Bar chart metric:", [])
        line_metric = st.selectbox("Line chart metric:", [])
        period_type = st.selectbox("Select time period:", ["week", "month", "quarter"])

        if st.button("Generate Extended Visualization"):
            generate_extended_visualization(selected_table, bar_metric, line_metric, period_type)

        st.markdown("## **Enable Comparison**")
        st.write("Comparison feature coming soon...")

def main():
    st.title("Data Autobot")
    st.markdown("### Automate your data analysis and visualization tasks!")
    
    uploaded_file = st.file_uploader("Upload your Excel or CSV file", type=["csv", "xlsx"])
    if uploaded_file:
        table_name, _ = process_uploaded_file(uploaded_file)
        if table_name:
            generate_analysis_ui()

if __name__ == "__main__":
    main()
