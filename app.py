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
                if period_type == "Quarterly":
                    comp_period1 = st.selectbox("Select first quarter:", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"])
                    comp_period2 = st.selectbox("Select second quarter:", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"])
                    comparison = (comp_period1, f"quarter = '{comp_period1}'", comp_period2, f"quarter = '{comp_period2}'")
                elif period_type == "Monthly":
                    comp_period1 = st.selectbox("Select first month:", ["2024-01", "2024-02", "2024-03", "2024-04"])
                    comp_period2 = st.selectbox("Select second month:", ["2024-01", "2024-02", "2024-03", "2024-04"])
                    comparison = (comp_period1, f"month = '{comp_period1}'", comp_period2, f"month = '{comp_period2}'")
                else:
                    st.warning("Comparison mode is only available for Quarterly or Monthly selections.")
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
