import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.drawing.image import Image
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from io import StringIO
import base64
import docx
import matplotlib.dates as mdates
from scipy.stats import norm, lognorm, pearson3, gamma, gumbel_r, genextreme
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.drawing.image import Image
import tempfile
import os

# Functions for Frequency Analysis


def log_pearson3(x, loc, scale, skew):
    return pearson3.pdf(x, skew, loc, scale)


def fit_distribution(distr, data):
    params = distr.fit(data)
    log_likelihood = np.sum(np.log(distr.pdf(data, *params)))
    k = len(params)
    n = len(data)

    aic = 2 * k - 2 * log_likelihood
    bic = k * np.log(n) - 2 * log_likelihood

    return aic, bic, params


distributions = {
    'Normal': norm,
    'Lognormal': lognorm,
    'Pearson Type 3': pearson3,
    'Gamma': gamma,
    'Gumbel': gumbel_r,
    'GEV': genextreme,
}


def generate_word_document(max_flow, aic_bic_params, best_aic_distr, best_bic_distr):
    # Create a Word document
    doc = docx.Document()
    doc.add_heading('Frequency Analysis of Maximum Flow in Rivers', 0)

    doc.add_heading('Best Distribution based on AIC and BIC:', level=1)
    doc.add_paragraph(
        f"Best distribution based on AIC: {best_aic_distr} (AIC: {aic_bic_params[best_aic_distr]['AIC']})")
    doc.add_paragraph(
        f"Best distribution based on BIC: {best_bic_distr} (BIC: {aic_bic_params[best_bic_distr]['BIC']})")

    doc.add_heading('AIC and BIC for each distribution:', level=1)
    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Distribution'
    hdr_cells[1].text = 'AIC'
    hdr_cells[2].text = 'BIC'

    for name, info in aic_bic_params.items():
        row_cells = table.add_row().cells
        row_cells[0].text = name
        row_cells[1].text = str(info['AIC'])
        row_cells[2].text = str(info['BIC'])

    doc.add_heading('Individual Distribution Plots:', level=1)
    for name in aic_bic_params.keys():
        doc.add_picture(f'{name}_distribution.png',
                        width=docx.shared.Inches(6))

    return doc


def download_link(document, filename):
    with io.BytesIO() as buffer:
        document.save(buffer)
        buffer.seek(0)
        file = base64.b64encode(buffer.read()).decode('utf-8')
    return f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{file}" download="{filename}">Download Word document</a>'

# Function to create a download link for the generated Excel file


def download_excel_link(excel_file, filename):
    with io.BytesIO() as buffer:
        excel_file.save(buffer)
        buffer.seek(0)
        file = base64.b64encode(buffer.read()).decode('utf-8')
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{file}" download="{filename}">Download Excel file</a>'


def generate_hydrographs_and_tables(daily_flow_data, sep_day, sep_month, spring_volume_period, fall_volume_period):
    unique_years = daily_flow_data.index.year.unique()

    # Create a new Excel workbook
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Hydrographs"

    max_spring_df = pd.DataFrame(
        columns=["Year", "Max Flow Spring", "Max Flow Date"])
    min_spring_df = pd.DataFrame(
        columns=["Year", "Min Flow Spring", "Min Flow Date"])
    max_fall_df = pd.DataFrame(
        columns=["Year", "Max Flow Fall", "Max Flow Date"])
    min_fall_df = pd.DataFrame(
        columns=["Year", "Min Flow Fall", "Min Flow Date"])
    period_df = pd.DataFrame(columns=["Year", "Spring Period", "Fall Period"])

    for year in unique_years:
        yearly_data = daily_flow_data[daily_flow_data.index.year == year]

        # Spring and Fall data
        spring_data = yearly_data.loc[yearly_data.index < yearly_data.index[0].replace(
            month=sep_month, day=sep_day)]
        fall_data = yearly_data.loc[yearly_data.index >= yearly_data.index[0].replace(
            month=sep_month, day=sep_day)]

        # Compute statistics
        spring_max_flow = spring_data['Flow'].max()
        spring_min_flow = spring_data['Flow'].min()
        fall_max_flow = fall_data['Flow'].max()
        fall_min_flow = fall_data['Flow'].min()
        spring_max_date = spring_data['Flow'].idxmax(
        ) if not spring_data.empty else None
        spring_min_date = spring_data['Flow'].idxmin(
        ) if not spring_data.empty else None
        fall_max_date = fall_data['Flow'].idxmax(
        ) if not fall_data.empty else None
        fall_min_date = fall_data['Flow'].idxmin(
        ) if not fall_data.empty else None

        # Add data to summary tables
        max_spring_df = max_spring_df.append(
            {"Year": year, "Max Flow Spring": spring_max_flow, "Max Flow Date": spring_max_date.strftime('%d-%m') if spring_max_date is not None else None}, ignore_index=True)
        min_spring_df = min_spring_df.append(
            {"Year": year, "Min Flow Spring": spring_min_flow, "Min Flow Date": spring_min_date.strftime('%d-%m')if spring_min_date is not None else None}, ignore_index=True)
        max_fall_df = max_fall_df.append({"Year": year, "Max Flow Fall": fall_max_flow,
                                          "Max Flow Date": fall_max_date.strftime('%d-%m')if fall_max_date is not None else None}, ignore_index=True)
        min_fall_df = min_fall_df.append({"Year": year, "Min Flow Fall": fall_min_flow,
                                          "Min Flow Date": fall_min_date.strftime('%d-%m')if fall_min_date is not None else None}, ignore_index=True)

        # Plot hydrograph
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(yearly_data.index, yearly_data['Flow'], label="Flow")

        # Add max and min points
        if spring_max_date is not None and spring_max_flow is not None:
            ax.plot(spring_max_date, spring_max_flow,
                    'ro', label="Max (Spring)")
        if spring_min_date is not None and spring_min_flow is not None:
            ax.plot(spring_min_date, spring_min_flow,
                    'go', label="Min (Spring)")
        if fall_max_date is not None and fall_max_flow is not None:
            ax.plot(fall_max_date, fall_max_flow, 'ro', label="Max (Fall)")
        if fall_min_date is not None and fall_min_flow is not None:
            ax.plot(fall_min_date, fall_min_flow, 'go', label="Min (Fall)")

        # Add separation date and spring/fall volume periods
        separation_date = yearly_data.index[0].replace(
            month=sep_month, day=sep_day)
        ax.axvline(separation_date, linestyle='--',
                   color='k', label="Separation Date")

        spring_rolling_sum = spring_data['Flow'].rolling(
            spring_volume_period).sum()
        if not spring_rolling_sum.empty:
            spring_volume_start = spring_rolling_sum.idxmax(
            ) - pd.Timedelta(days=spring_volume_period - 1)
            spring_volume_end = spring_rolling_sum.idxmax()
        else:
            spring_volume_start = None
            spring_volume_end = None
        ax.axvspan(spring_volume_start, spring_volume_end,
                   color='r', alpha=0.3, label="Spring Volume Period")

        fall_rolling_sum = fall_data['Flow'].rolling(fall_volume_period).sum()
        if not fall_rolling_sum.empty:
            fall_volume_start = fall_rolling_sum.idxmax(
            ) - pd.Timedelta(days=fall_volume_period - 1)
            fall_volume_end = fall_rolling_sum.idxmax()
        else:
            fall_volume_start = None
            fall_volume_end = None
        ax.axvspan(fall_volume_start, fall_volume_end, color='g',
                   alpha=0.3, label="Fall Volume Period")

        ax.set_title(f"Hydrograph {year}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Flow")
        ax.legend(loc="best")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

        # Save the figure to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        fig.savefig(temp_file.name, format="png", dpi=300, bbox_inches="tight")
        plt.close(fig)

        # Add the image to the Excel workbook
        img = Image(temp_file.name)
        img.width = img.width // 4
        img.height = img.height // 4
        ws1.column_dimensions["A"].width = img.width // 6
        ws1.row_dimensions[year - unique_years.min()].height = img.height
        ws1.add_image(img, f"A{year - unique_years.min() + 1}")

        # Delete the temporary file
        # os.unlink(temp_file.name)

        # Add data to periods table
        period_df = period_df.append({"Year": year, "Spring Period": f"{spring_volume_start.strftime('%d-%m') if spring_volume_start is not None else None} - {spring_volume_end.strftime('%d-%m') if spring_volume_end is not None else None}",
                                      "Fall Period": f"{fall_volume_start.strftime('%d-%m') if fall_volume_start is not None else None} - {fall_volume_end.strftime('%d-%m') if fall_volume_end is not None else None}"}, ignore_index=True)

    # Create remaining sheets in the Excel workbook
    for sheet_name, df in zip(["Max Spring", "Min Spring", "Max Fall", "Min Fall", "Periods"], [max_spring_df, min_spring_df, max_fall_df, min_fall_df, period_df]):
        ws = wb.create_sheet(sheet_name)
        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)

    # # Delete temporary image files
    # for year in range(min_year, max_year + 1):
    #     try:
    #         os.remove(f"temp_image_{year}.png")
    #     except FileNotFoundError:
    #         pass
    return wb


def download_link(workbook, filename):
    with io.BytesIO() as buffer:
        workbook.save(buffer)
        buffer.seek(0)
        file = base64.b64encode(buffer.read()).decode('utf-8')
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{file}" download="{filename}">Download Excel file</a>'


# Page configuration
st.set_page_config(page_title="Water Engineering Tools", layout="wide")

# Main menu
menu = ["Home", "Hydrograph Producer", "Peak Flow Comparison",
        "Camera Viewer", "Frequency Analysis"]
choice = st.sidebar.selectbox("Menu", menu)

# Home page
if choice == "Home":
    st.title("Water Engineering Tools")
    st.write(
        """
        Welcome to the Water Engineering Tools web app created by a junior engineer.
        This web app includes the following tools:

        1. Hydrograph Producer: This tool allows you to import a CSV file containing daily flow data time series and plots the hydrograph for each year. It also provides the maximum, minimum, and number of missing values.

        2. Peak Flow Comparison: This tool compares two time series. The first time series contains the daily flow data of a river, while the second contains flow data for every 15 minutes of the same river. The tool compares the maximum value for each year of both time series and returns a table with all the ratios for each specific year. The last row displays the mean of these ratios.

        3. Camera Viewer: This tool allows you to input images and displays the image on the webpage.

        4. Frequency Analysis: This tool performs frequency analysis on the maximum flow data using various probability distributions and generates a Word document with the analysis results.
        """
    )


if choice == "Hydrograph Producer":
    st.header("Hydrograph Producer")

    uploaded_file = st.file_uploader(
        "Upload a CSV file with daily flow data (Date, Flow, Year):", type="csv")
    if uploaded_file is not None:
        daily_flow_data = pd.read_csv(uploaded_file)
        daily_flow_data['Date'] = pd.to_datetime(daily_flow_data['Date'])
        daily_flow_data.set_index('Date', inplace=True)

        sep_day = st.number_input(
            "Separation Day (default: 1):", min_value=1, max_value=31, value=1)
        sep_month = st.number_input(
            "Separation Month (default: 7):", min_value=1, max_value=12, value=7)
        spring_volume_period = st.number_input(
            "Spring Volume Period (default: 30):", min_value=1, max_value=365, value=30)
        fall_volume_period = st.number_input(
            "Fall Volume Period (default: 10):", min_value=1, max_value=365, value=10)

        if st.button("Generate Hydrographs and Tables"):
            wb = generate_hydrographs_and_tables(
                daily_flow_data, sep_day, sep_month, spring_volume_period, fall_volume_period)
            st.markdown(download_link(
                wb, "hydrograph_analysis.xlsx"), unsafe_allow_html=True)

        # Convert the "Date" column to a datetime object
        df = daily_flow_data
        df["Date"] = pd.to_datetime(df["Date"])
        years = df["Year"].unique()
        st.subheader("Hydrographs")
        for year in years:
            df_year = df[df["Year"] == year]
            df_year.set_index("Date", inplace=True)

            # Calculate the rolling sum of flow for spring and fall periods
            df_year["Rolling_Spring"] = df_year["Flow"].rolling(
                window=spring_volume_period).sum()
            df_year["Rolling_Fall"] = df_year["Flow"].rolling(
                window=fall_volume_period).sum()

            # Find the maximum rolling sum periods for spring and fall
            spring_start_date = df_year["Rolling_Spring"].idxmax(
            ) - pd.Timedelta(days=spring_volume_period - 1)
            spring_end_date = df_year["Rolling_Spring"].idxmax()
            fall_start_date = df_year["Rolling_Fall"].idxmax(
            ) - pd.Timedelta(days=fall_volume_period - 1)
            fall_end_date = df_year["Rolling_Fall"].idxmax()

            fig, ax = plt.subplots(figsize=(15, 6))
            ax.plot(df_year.index, df_year["Flow"])
            ax.axvline(pd.Timestamp(year, sep_month, sep_day),
                       color="black", linestyle="--", label="Separation Date")

            # Highlight the spring and fall volume periods in red and green, respectively
            ax.axvspan(spring_start_date, spring_end_date, alpha=0.3,
                       color="red", label="Spring Volume Period")
            ax.axvspan(fall_start_date, fall_end_date, alpha=0.3,
                       color="green", label="Fall Volume Period")

            ax.set_title(f"Hydrograph for {year}")

            # Format the x-axis to display the month of the year
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

            ax.set_xlabel("Month")
            ax.set_ylabel("Flow")
            ax.legend(loc='best')
            st.pyplot(fig)

            st.write(
                f"Spring Volume Period: {spring_start_date.strftime('%d-%m')} to {spring_end_date.strftime('%d-%m')}")
            st.write(
                f"Fall Volume Period: {fall_start_date.strftime('%d-%m')} to {fall_end_date.strftime('%d-%m')}")


# # # Hydrograph Producer page
# # elif choice == "Hydrograph Producer":
# #     # (The previous code for input and displaying hydrographs remains the same)

# #     if uploaded_file is not None:
# #         # (The previous code for input and displaying hydrographs remains the same)

# #         # Create an Excel file
# #         wb = openpyxl.Workbook()

# #         # Sheet 1: Hydrograph images
# #         ws1 = wb.active
# #         ws1.title = "Hydrograph"
# #         img_height = 150

# #         for idx, year in enumerate(years, start=1):
# #             img_path = f"hydrograph_{year}.png"
# #             img = Image(img_path)
# #             img.width = int(img.width * img_height / img.height)
# #             img.height = img_height
# #             ws1.column_dimensions[get_column_letter(
# #                 idx)].width = img.width // 6
# #             ws1.row_dimensions[1].height = img.height
# #             ws1.add_image(img, f"{get_column_letter(idx)}1")

# #         # Sheets 2 to 5: Max/Min Spring/Fall
# #         max_spring_df = pd.DataFrame(
# #             columns=["Year", "Max Flow Spring", "Max Flow Date"])
# #         min_spring_df = pd.DataFrame(
# #             columns=["Year", "Min Flow Spring", "Min Flow Date"])
# #         max_fall_df = pd.DataFrame(
# #             columns=["Year", "Max Flow Fall", "Max Flow Date"])
# #         min_fall_df = pd.DataFrame(
# #             columns=["Year", "Min Flow Fall", "Min Flow Date"])
# #         period_df = pd.DataFrame(
# #             columns=["Year", "Spring Period", "Fall Period"])

# #         for year in years:
# #             df_year = df[df["Year"] == year]
# #             df_year.set_index("Date", inplace=True)

# #             # (The previous code for calculating rolling sums, max/min values, and periods remains the same)

# #             max_spring_df = max_spring_df.append(
# #                 {"Year": year, "Max Flow Spring": spring_max, "Max Flow Date": spring_max_date.strftime('%d-%m')}, ignore_index=True)
# #             min_spring_df = min_spring_df.append(
# #                 {"Year": year, "Min Flow Spring": spring_min, "Min Flow Date": spring_min_date.strftime('%d-%m')}, ignore_index=True)
# #             max_fall_df = max_fall_df.append(
# #                 {"Year": year, "Max Flow Fall": fall_max, "Max Flow Date": fall_max_date.strftime('%d-%m')}, ignore_index=True)
# #             min_fall_df = min_fall_df.append(
# #                 {"Year": year, "Min Flow Fall": fall_min, "Min Flow Date": fall_min_date.strftime('%d-%m')}, ignore_index=True)
# #             period_df = period_df.append({"Year": year, "Spring Period": f"{spring_start_date.strftime('%d-%m')} to {spring_end_date.strftime('%d-%m')}",
# #                                           "Fall Period": f"{fall_start_date.strftime('%d-%m')} to {fall_end_date.strftime('%d-%m')}"}, ignore_index=True)

# #     for sheet_name, data_df in zip(["Max Spring", "Min Spring", "Max Fall", "Min Fall"], [max_spring_df, min_spring_df, max_fall_df, min_fall_df]):
# #         ws = wb.create_sheet(title=sheet_name)
# #         for r_idx, row in enumerate(dataframe_to_rows(data_df, index=False, header=True)):
# #             for c_idx, value in enumerate(row):
# #                 ws.cell(row=r_idx + 1, column=c_idx + 1, value=value)

# #     # Sheet 6: Periods
# #     ws6 = wb.create_sheet(title="Periods")
# #     ws6.cell(row=1, column=1, value="Separation Date")
# #     ws6.cell(row=1, column=2, value=f"{sep_month}-{sep_day}")
# #     ws6.cell(row=2, column=1, value="Spring Volume Period")
# #     ws6.cell(row=2, column=2, value=spring_volume_period)
# #     ws6.cell(row=3, column=1, value="Fall Volume Period")
# #     ws6.cell(row=3, column=2, value=fall_volume_period)

# #     for r_idx, row in enumerate(dataframe_to_rows(period_df, index=False, header=True), start=5):
# #         for c_idx, value in enumerate(row):
# #             ws6.cell(row=r_idx, column=c_idx + 1, value=value)

# #     # Add download link for the Excel file
# #     st.markdown(download_excel_link(
# #         wb, 'Hydrograph_Data.xlsx'), unsafe_allow_html=True)

# # else:
# #     st.info("Please upload a CSV file.")

# # # Hydrograph Producer page
# # elif choice == "Hydrograph Producer":
# #     st.title("Hydrograph Producer")

# #     uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

# #     if uploaded_file is not None:
# #         df = pd.read_csv(uploaded_file)
# #         st.write(df)

# #         # Convert the "Date" column to a datetime object
# #         df["Date"] = pd.to_datetime(df["Date"])

# #         sep_day = st.number_input(
# #             "Separation day (default: 1)", min_value=1, max_value=31, value=1)
# #         sep_month = st.number_input(
# #             "Separation month (default: 7)", min_value=1, max_value=12, value=7)
# #         spring_volume_period = st.number_input(
# #             "Spring volume period (default: 30)", min_value=1, value=30)
# #         fall_volume_period = st.number_input(
# #             "Fall volume period (default: 10)", min_value=1, value=10)

# #         years = df["Year"].unique()
# #         st.subheader("Hydrographs")
# #         for year in years:
# #             df_year = df[df["Year"] == year]
# #             df_year.set_index("Date", inplace=True)

# #             # Calculate the rolling sum of flow for spring and fall periods
# #             df_year["Rolling_Spring"] = df_year.loc[:pd.Timestamp(
# #                 year, sep_month, sep_day), "Flow"].rolling(window=spring_volume_period).sum()
# #             df_year["Rolling_Fall"] = df_year.loc[pd.Timestamp(
# #                 year, sep_month, sep_day):, "Flow"].rolling(window=fall_volume_period).sum()

# #             # Find the maximum rolling sum periods for spring and fall
# #             spring_start_date = df_year["Rolling_Spring"].idxmax(
# #             ) - pd.Timedelta(days=spring_volume_period - 1)
# #             spring_end_date = df_year["Rolling_Spring"].idxmax()
# #             fall_start_date = df_year["Rolling_Fall"].idxmax(
# #             ) - pd.Timedelta(days=fall_volume_period - 1)
# #             fall_end_date = df_year["Rolling_Fall"].idxmax()

# #             fig, ax = plt.subplots(figsize=(15, 6))
# #             ax.plot(df_year.index, df_year["Flow"])
# #             ax.axvline(pd.Timestamp(year, sep_month, sep_day),
# #                        color="black", linestyle="--", label="Separation Date")

# #             # Highlight the spring and fall volume periods in red and green, respectively
# #             ax.axvspan(spring_start_date, spring_end_date, alpha=0.3,
# #                        color="red", label="Spring Volume Period")
# #             ax.axvspan(fall_start_date, fall_end_date, alpha=0.3,
# #                        color="green", label="Fall Volume Period")

# #             # Maximum and minimum values for spring and fall periods
# #             spring_max = df_year.loc[:pd.Timestamp(
# #                 year, sep_month, sep_day), "Flow"].max()
# #             spring_min = df_year.loc[:pd.Timestamp(
# #                 year, sep_month, sep_day), "Flow"].min()
# #             fall_max = df_year.loc[pd.Timestamp(
# #                 year, sep_month, sep_day):, "Flow"].max()
# #             fall_min = df_year.loc[pd.Timestamp(
# #                 year, sep_month, sep_day):, "Flow"].min()

# #             # Add red and green dots for maximum and minimum values of spring and fall periods
# #             spring_max_date = df_year.loc[:pd.Timestamp(
# #                 year, sep_month, sep_day), "Flow"].idxmax()
# #             spring_min_date = df_year.loc[:pd.Timestamp(
# #                 year, sep_month, sep_day), "Flow"].idxmin()
# #             fall_max_date = df_year.loc[pd.Timestamp(
# #                 year, sep_month, sep_day):, "Flow"].idxmax()
# #             fall_min_date = df_year.loc[pd.Timestamp(
# #                 year, sep_month, sep_day):, "Flow"].idxmin()

# #             ax.plot(spring_max_date, spring_max, "ro")
# #             ax.plot(spring_min_date, spring_min, "go")
#             ax.plot(fall_max_date, fall_max, "ro")
#             ax.plot(fall_min_date, fall_min, "go")

#             ax.set_title(f"Hydrograph for {year}")
#             ax.set_ylabel("Flow")
#             ax.legend(loc="best")
#             ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

#             st.pyplot(fig)

#             st.write(
#                 f"Spring Volume Period: {spring_start_date.strftime('%d-%m')} to {spring_end_date.strftime('%d-%m')}")
#             st.write(
#                 f"Fall Volume Period: {fall_start_date.strftime('%d-%m')} to {fall_end_date.strftime('%d-%m')}")
#             st.write(
#                 f"Max and Min for Spring: {spring_max} ({spring_max_date.strftime('%d-%m')}), {spring_min} ({spring_min_date.strftime('%d-%m')})")
#             st.write(
#                 f"Max and Min for Fall: {fall_max} ({fall_max_date.strftime('%d-%m')}), {fall_min} ({fall_min_date.strftime('%d-%m')})")
#     else:
#         st.info("Please upload a CSV file.")


# Hydrograph Producer page
# elif choice == "Hydrograph Producer":
#     st.title("Hydrograph Producer")

#     uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

#     if uploaded_file is not None:
#         df = pd.read_csv(uploaded_file)
#         st.write(df)

#         # Convert the "Date" column to a datetime object
#         df["Date"] = pd.to_datetime(df["Date"])

#         sep_day = st.number_input(
#             "Separation day (default: 1)", min_value=1, max_value=31, value=1)
#         sep_month = st.number_input(
#             "Separation month (default: 7)", min_value=1, max_value=12, value=7)
#         spring_volume_period = st.number_input(
#             "Spring volume period (default: 30)", min_value=1, value=30)
#         fall_volume_period = st.number_input(
#             "Fall volume period (default: 10)", min_value=1, value=10)

#         years = df["Year"].unique()
#         st.subheader("Hydrographs")
#         for year in years:
#             df_year = df[df["Year"] == year]
#             df_year.set_index("Date", inplace=True)

#             # Calculate the rolling sum of flow for spring and fall periods
#             df_year["Rolling_Spring"] = df_year["Flow"].rolling(
#                 window=spring_volume_period).sum()
#             df_year["Rolling_Fall"] = df_year["Flow"].rolling(
#                 window=fall_volume_period).sum()

#             # Find the maximum rolling sum periods for spring and fall
#             spring_start_date = df_year["Rolling_Spring"].idxmax(
#             ) - pd.Timedelta(days=spring_volume_period - 1)
#             spring_end_date = df_year["Rolling_Spring"].idxmax()
#             fall_start_date = df_year["Rolling_Fall"].idxmax(
#             ) - pd.Timedelta(days=fall_volume_period - 1)
#             fall_end_date = df_year["Rolling_Fall"].idxmax()

#             fig, ax = plt.subplots(figsize=(15, 6))
#             ax.plot(df_year.index, df_year["Flow"])
#             ax.axvline(pd.Timestamp(year, sep_month, sep_day),
#                        color="black", linestyle="--", label="Separation Date")

#             # Highlight the spring and fall volume periods in red and green, respectively
#             ax.axvspan(spring_start_date, spring_end_date, alpha=0.3,
#                        color="red", label="Spring Volume Period")
#             ax.axvspan(fall_start_date, fall_end_date, alpha=0.3,
#                        color="green", label="Fall Volume Period")

#             ax.set_title(f"Hydrograph for {year}")

#             # Format the x-axis to display the month of the year
#             ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

#             ax.set_xlabel("Month")
#             ax.set_ylabel("Flow")
#             ax.legend(loc='best')
#             st.pyplot(fig)

#             st.write(
#                 f"Spring Volume Period: {spring_start_date.strftime('%d-%m')} to {spring_end_date.strftime('%d-%m')}")
#             st.write(
#                 f"Fall Volume Period: {fall_start_date.strftime('%d-%m')} to {fall_end_date.strftime('%d-%m')}")


# Hydrograph Producer page
# elif choice == "Hydrograph Producer":
#     st.title("Hydrograph Producer")

#     uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

#     if uploaded_file is not None:
#         df = pd.read_csv(uploaded_file)
#         st.write(df)

#         # Convert the "Date" column to a datetime object
#         df["Date"] = pd.to_datetime(df["Date"])

#         years = df["Year"].unique()
#         st.subheader("Hydrographs")
#         for year in years:
#             df_year = df[df["Year"] == year]

#             # Find the maximum and minimum values and their dates
#             max_value = df_year["Flow"].max()
#             min_value = df_year["Flow"].min()
#             max_date = df_year[df_year["Flow"] == max_value]["Date"].iloc[0]
#             min_date = df_year[df_year["Flow"] == min_value]["Date"].iloc[0]

#             fig, ax = plt.subplots(figsize=(15, 6))
#             ax.plot(df_year["Date"], df_year["Flow"])
#             ax.scatter([max_date], [max_value], color="red", label="Maximum")
#             ax.scatter([min_date], [min_value], color="green", label="Minimum")
#             ax.set_title(f"Hydrograph for {year}")

#             # Format the x-axis to display the month of the year
#             ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

#             ax.set_xlabel("Month")
#             ax.set_ylabel("Flow")
#             ax.legend(loc='best')
#             st.pyplot(fig)

#             st.write(
#                 f"Maximum: {max_value} on {max_date.strftime('%Y-%m-%d')}")
#             st.write(
#                 f"Minimum: {min_value} on {min_date.strftime('%Y-%m-%d')}")


# Peak Flow Comparison page
elif choice == "Peak Flow Comparison":
    st.title("Peak Flow Comparison")

    uploaded_file1 = st.file_uploader(
        "Choose the first CSV file (daily flow data)", type="csv")
    uploaded_file2 = st.file_uploader(
        "Choose the second CSV file (flow data every 15 minutes)", type="csv")

    if uploaded_file1 is not None and uploaded_file2 is not None:
        df1 = pd.read_csv(uploaded_file1)
        df2 = pd.read_csv(uploaded_file2)

        max_values1 = df1.groupby("Year")["Flow"].max().values
        max_values2 = df2.groupby("Year")["Flow"].max().values

        ratio = max_values2 / max_values1
        mean_ratio = ratio.mean()

        st.write("Ratio for each year:")
        st.write(pd.DataFrame({"Year": df1["Year"].unique(), "Ratio": ratio}))

        st.write(f"Mean of ratios: {mean_ratio}")

# Camera Viewer page
elif choice == "Camera Viewer":
    st.title("Camera Viewer")

    # File upload
    image_file = st.file_uploader(
        "Upload your image file", type=["png", "jpg", "jpeg"])

    if image_file:
        st.image(image_file, caption="Uploaded Image", use_column_width=True)

# Frequency Analysis page
elif choice == "Frequency Analysis":
    st.title('Analyse fréquentielle des débits de crues')

    st.text("Cet outil sélectionne la meilleure distribution pour votre échantillon.")

    uploaded_file = st.file_uploader(
        "Importer un fichier CSV d'une seule colonne qui comprend l'ensemble de l'échantillon.", type="csv")

    if uploaded_file is not None:
        data = pd.read_csv(uploaded_file, header=None, names=['Flow'])
        max_flow = data['Flow'].to_numpy()

        aic_bic_params = {}
        for name, distr in distributions.items():
            aic, bic, params = fit_distribution(distr, max_flow)
            aic_bic_params[name] = {'AIC': aic, 'BIC': bic, 'params': params}

        best_aic_distr = min(
            aic_bic_params, key=lambda x: aic_bic_params[x]['AIC'])
        best_bic_distr = min(
            aic_bic_params, key=lambda x: aic_bic_params[x]['BIC'])

        x = np.linspace(min(max_flow), max(max_flow), 1000)
        for name, info in aic_bic_params.items():
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(max_flow, bins='auto', density=True,
                    alpha=0.6, color='g', label='Histogram')

            params = info['params']
            if name == 'Log-Pearson Type 3':
                ax.plot(x, log_pearson3(x, *params), label=name)
            else:
                distr = distributions[name]
                ax.plot(x, distr.pdf(x, *params), label=name)

            ax.set_xlabel('Flow')
            ax.set_ylabel('Density')
            ax.legend(loc='best')
            plt.savefig(f'{name}_distribution.png', bbox_inches='tight')
            plt.close(fig)

        doc = generate_word_document(
            max_flow, aic_bic_params, best_aic_distr, best_bic_distr)
        st.markdown(download_link(doc, 'Frequency_Analysis.docx'),
                    unsafe_allow_html=True)

    else:
        st.info("Importer votre fichier CSV.")
