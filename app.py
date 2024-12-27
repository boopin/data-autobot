import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import plotly.express as px

def main():
    # App branding and title
    st.set_page_config(page_title="Data Autobot (dBot)", layout="wide")
    st.title("Data Autobot (dBot)")
    st.write("Version 2.6.0 - Your intelligent data analysis assistant")

    # SQLite setup
    conn = sqlite3.connect(":memory:")

    def process_file(uploaded_file):
        """Process the uploaded file and create a SQLite table."""
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xls', '.xlsx')):
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_name = st.selectbox("Select a sheet to analyze:", excel_file.sheet_names)
            df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return None

        # Normalize column names
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]

        # Validate required columns
        if 'date' not in df.columns or 'impressions_total' not in df.columns:
            st.error("The dataset must contain 'date' and 'impressions_total' columns.")
            return None

        # Convert date column to datetime
        try:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            if df['date'].isnull().all():
                st.error("The 'date' column contains no valid datetime values. Please ensure the column can be converted to a valid date.")
                return None
        except Exception as e:
            st.error(f"Error processing the 'date' column: {e}")
            return None

        # Add derived columns
        try:
            df['year'] = df['date'].dt.year.astype(str)
            df['year_month'] = df['date'].dt.to_period("M").astype(str)
            df['quarter'] = "Q" + df['date'].dt.quarter.astype(str) + " " + df['date'].dt.year.astype(str)
            df['week'] = df['date'].dt.to_period("W-SUN").astype(str)
        except Exception as e:
            st.error(f"Error adding derived columns: {e}")
            return None

        # Save to SQLite
        df.to_sql("metrics", conn, index=False, if_exists="replace")
        return df

    # File upload
    uploaded_file = st.file_uploader("Upload your dataset (CSV or Excel)", type=["csv", "xls", "xlsx"])
    if uploaded_file:
        st.write("Processing file...")
        df = process_file(uploaded_file)
        if df is not None:
            st.success("File uploaded and processed successfully!")
            st.write("Preview of the dataset:")
            st.dataframe(df.head())

            # Debugging: Display schema
            st.write("### Debugging Information")
            st.write("Columns in the dataset:", df.columns.tolist())

            # Feature: Custom Period Comparison
            st.write("### Compare Custom Periods")
            col1, col2 = st.columns(2)
            with col1:
                period1_name = st.text_input("Custom Name for Period 1", "Period 1")
                period1_filter = st.date_input("Start and End Date for Period 1", [])
            with col2:
                period2_name = st.text_input("Custom Name for Period 2", "Period 2")
                period2_filter = st.date_input("Start and End Date for Period 2", [])

            # Generate comparison data
            if len(period1_filter) == 2 and len(period2_filter) == 2:
                period1_data = df[(df['date'] >= pd.Timestamp(period1_filter[0])) & (df['date'] <= pd.Timestamp(period1_filter[1]))]
                period2_data = df[(df['date'] >= pd.Timestamp(period2_filter[0])) & (df['date'] <= pd.Timestamp(period2_filter[1]))]

                comparison_result = pd.DataFrame({
                    "Metric": ["Total Impressions"],
                    period1_name: [period1_data['impressions_total'].sum()],
                    period2_name: [period2_data['impressions_total'].sum()],
                    "% Change": [(period2_data['impressions_total'].sum() - period1_data['impressions_total'].sum()) / period1_data['impressions_total'].sum() * 100]
                })
                st.write("Comparison Results")
                st.dataframe(comparison_result)
                st.download_button("Download Comparison Data", comparison_result.to_csv(index=False).encode('utf-8'), "comparison_data.csv")

                # Visualization of comparison
                fig = go.Figure()
                fig.add_trace(go.Bar(x=[period1_name, period2_name], y=comparison_result.iloc[0, 1:3], name="Total Impressions"))
                fig.add_trace(go.Scatter(x=[period1_name, period2_name], y=comparison_result["% Change"], mode="lines+markers", name="% Change", yaxis="y2"))
                fig.update_layout(
                    title="Custom Period Comparison",
                    xaxis_title="Periods",
                    yaxis_title="Total Impressions",
                    yaxis2=dict(title="% Change", overlaying="y", side="right"),
                    hovermode="x unified"
                )
                st.plotly_chart(fig, use_container_width=True)

            # Timeframe selection dropdown
            timeframe = st.selectbox("Select a timeframe to visualize:", ["Yearly", "Quarterly", "Monthly", "Weekly"])

            # Query and visualization logic based on the selected timeframe
            if timeframe == "Yearly":
                yearly_query = """
                    SELECT year, SUM(impressions_total) AS total_impressions
                    FROM metrics
                    GROUP BY year;
                """
                yearly_result = pd.read_sql_query(yearly_query, conn)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=yearly_result["year"], y=yearly_result["total_impressions"], name="Yearly Total Impressions"))
                fig.update_layout(title="Yearly Total Impressions", xaxis_title="Year", yaxis_title="Total Impressions", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

            elif timeframe == "Quarterly":
                quarterly_query = """
                    SELECT quarter, SUM(impressions_total) AS total_impressions
                    FROM metrics
                    GROUP BY quarter;
                """
                quarterly_result = pd.read_sql_query(quarterly_query, conn)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=quarterly_result["quarter"], y=quarterly_result["total_impressions"], name="Quarterly Total Impressions"))
                fig.update_layout(title="Quarterly Total Impressions", xaxis_title="Quarter", yaxis_title="Total Impressions", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

            elif timeframe == "Monthly":
                monthly_query = """
                    SELECT year_month, SUM(impressions_total) AS total_impressions
                    FROM metrics
                    GROUP BY year_month;
                """
                monthly_result = pd.read_sql_query(monthly_query, conn)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=monthly_result["year_month"], y=monthly_result["total_impressions"], name="Monthly Total Impressions"))
                fig.update_layout(title="Monthly Total Impressions", xaxis_title="Month (YYYY-MM)", yaxis_title="Total Impressions", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

            elif timeframe == "Weekly":
                weekly_query = """
                    SELECT week, SUM(impressions_total) AS total_impressions
                    FROM metrics
                    GROUP BY week;
                """
                weekly_result = pd.read_sql_query(weekly_query, conn)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=weekly_result["week"], y=weekly_result["total_impressions"], name="Weekly Total Impressions"))
                fig.update_layout(title="Weekly Total Impressions", xaxis_title="Week (YYYY-WXX)", yaxis_title="Total Impressions", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

            st.write("Visualization updates dynamically based on your selection.")

if __name__ == "__main__":
    main()
