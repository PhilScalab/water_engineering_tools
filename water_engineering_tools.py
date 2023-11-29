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
import shutil
import zipfile
from datetime import datetime, timedelta
import math
import requests

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
    
def download_ndbc_full_history(station_id, start_year, end_year):
    """
    Download full historical wave data for a given station across a range of years.

    Parameters:
    - station_id (str): The ID of the NDBC station.
    - start_year (int): The starting year for the data.
    - end_year (int): The ending year for the data.

    Returns:
    - DataFrame: A pandas DataFrame containing the downloaded data.
    """

    all_data = []

    for year in range(start_year, end_year + 1):
        # Base URL for historical data
        base_url = f"https://www.ndbc.noaa.gov/view_text_file.php?filename={station_id}h{year}.txt.gz&dir=data/historical/stdmet/"

        # Download the data
        response = requests.get(base_url)
        if response.status_code == 200:
            # Parse the data
            content = response.content.decode('utf-8')
            data = [line.split() for line in content.split('\n') if line and not line.startswith('#')]
            all_data.extend(data)
        else:
            st.write(f"Data not found for station {station_id} in year {year}.")

    # Create a DataFrame
    df = pd.DataFrame(all_data, columns=["YY", "MM", "DD", "hh", "mm", "WDIR", "WSPD", "GST", "WVHT", "DPD", "APD", "MWD", "PRES", "ATMP", "WTMP", "DEWP", "VIS", "TIDE"])
    
    return df
    
# def plot_wave_height(df, station_id):
#     """
#     Plot the Wave Height (WVHT) from the DataFrame.

#     Parameters:
#     - df (DataFrame): The DataFrame containing the wave data.
#     - station_id (str): The ID of the NDBC station.
#     """
#     plt.figure(figsize=(10, 6))
#     plt.plot(df['WVHT'], label='Wave Height (WVHT)')
#     plt.title(f'Wave Height (WVHT) at Station {station_id}')
#     plt.xlabel('Record Number')
#     plt.ylabel('Wave Height (meters)')
#     plt.legend()
#     st.pyplot(plt)
def plot_wave_height(df, title):
    """
    Plot the Wave Height (WVHT) from the DataFrame.

    Parameters:
    - df (DataFrame): The DataFrame containing the wave data.
    - title (str): The title for the plot.
    """
    plt.figure(figsize=(10, 6))
    plt.plot(df['WVHT'], label='Wave Height (WVHT)')
    plt.title(title)
    plt.xlabel('Date')
    plt.ylabel('Wave Height (meters)')
    plt.legend()
    st.pyplot(plt)

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
    
# Function to process the uploaded file
def process_file(uploaded_file):
    df = pd.read_csv(uploaded_file)

    # Check if the Year, Month, Day columns are present
    if {'Year', 'Month', 'Day'}.issubset(df.columns):
        # Construct the Date column from Year, Month, Day
        df['Date'] = pd.to_datetime(df[['Year', 'Month', 'Day']])
        return df
    else:
        st.error("Required columns 'Year', 'Month', and 'Day' are not present in the CSV file.")
        return None
#Plot normal distribution
def create_plot_normal(data):
    mu, std = stats.norm.fit(data)

    def create_plots_normal():
        fig, axs = plt.subplots(2, 2, figsize=(10, 8))

        # Histogram and theoretical density
        x = np.linspace(min(data), max(data), 100)
        axs[0, 0].hist(data, bins=30, density=True, alpha=0.5)
        axs[0, 0].plot(x, stats.norm.pdf(x, mu, std), 'k', linewidth=2)
        axs[0, 0].set_title('Histogram and Theoretical Density')

        # Q-Q plot
        stats.probplot(data, dist="norm", plot=axs[0, 1])
        axs[0, 1].set_title('Q-Q Plot')

        # CDF
        sorted_data = np.sort(data)
        empirical_cdf = np.arange(1, len(sorted_data)+1) / len(sorted_data)
        axs[1, 0].plot(sorted_data, empirical_cdf, marker='.', linestyle='none')
        axs[1, 0].plot(x, stats.norm.cdf(x, mu, std), 'k', linewidth=2)
        axs[1, 0].set_title('Empirical and Theoretical CDF')

        # P-P plot
        theoretical_cdf = stats.norm.cdf(sorted_data, mu, std)
        axs[1, 1].plot(empirical_cdf, theoretical_cdf, marker='.', linestyle='none')
        axs[1, 1].plot([0, 1], [0, 1], 'k--')
        axs[1, 1].set_title('P-P Plot')

        plt.tight_layout()
        plt.show()
# Function to calculate AIC and BIC for a given distribution and data
def calculate_aic_bic(data, distribution, *params):
    # Calculate the log likelihood
    log_likelihood = np.sum(distribution.logpdf(data, *params))
    
    # Calculate the number of parameters (including the location and scale parameters)
    k = len(params) + 2  # adding 2 for loc and scale
    
    # Calculate AIC and BIC
    aic = 2 * k - 2 * log_likelihood
    bic = k * np.log(len(data)) - 2 * log_likelihood
    
    return aic, bic

# Function to fit distribution and calculate AIC and BIC
def fit_and_calculate_criteria(data, distribution, name, is_log_transformed=False):
    if is_log_transformed:
        # For log-transformed distributions, transform the data before fitting
        data_to_fit = np.log(data)
    else:
        data_to_fit = data

    # Fit the distribution to the data
    params = distribution.fit(data_to_fit)

    # Calculate AIC and BIC
    aic, bic = calculate_aic_bic(data_to_fit, distribution, *params)
    
    return {
        "Distribution": name,
        "AIC": aic,
        "BIC": bic,
        "Parameters": params
    }

    create_plots_normal()

# Page configuration
st.set_page_config(page_title="Water Engineering Tools", layout="wide")

# Main menu
menu = ["Home", "Hydrograph Producer", "Peak Flow Comparison",
        "Camera Viewer", "Frequency Analysis","EC Daily Data Analysis","Water level CEHQ","NDBC Historical Data Download","Frequency Analysis v2"]
choice = st.sidebar.selectbox("Menu", menu)

#NDBC historical data"
if choice == "NDBC Historical Data Download":
    # Streamlit user interface to input parameters
    st.title("NDBC Historical Data Downloader")
    
    station_id = st.text_input("Enter Station ID", value="44086")
    start_year = st.number_input("Enter Start Year", min_value=1900, max_value=2023, value=2015)
    end_year = st.number_input("Enter End Year", min_value=1900, max_value=2023, value=2020)

    
    df_full_history = download_ndbc_full_history(station_id, start_year, end_year)

    if not df_full_history.empty:
        # Convert date columns to datetime and create a 'Date' column
        df_full_history['Date'] = pd.to_datetime(df_full_history[['YY', 'MM', 'DD']].astype(str).agg('-'.join, axis=1))

        # Select date range for plotting, if 'Date' column is present
        if 'Date' in df_full_history.columns:
            plot_start_date, plot_end_date = st.select_slider(
                "Select Date Range for Plotting",
                options=pd.to_datetime(df_full_history['Date']).sort_values(),
                value=(df_full_history['Date'].min(), df_full_history['Date'].max())
            )
            
            filtered_df = df_full_history[(df_full_history['Date'] >= plot_start_date) & (df_full_history['Date'] <= plot_end_date)]
            
            st.write(filtered_df)
            plot_wave_height(filtered_df, f'Wave Height (WVHT) at Station {station_id} ({plot_start_date.date()} to {plot_end_date.date()})')
        else:
            st.write("Date column not found in the DataFrame.")
    else:
        st.write("No data available for the specified range.")
    
    # if st.button("Download Data"):
    #     df_full_history = download_ndbc_full_history(station_id, start_year, end_year)
    
    #     # Display the DataFrame in the Streamlit app
    #     if not df_full_history.empty:
    #         st.write(df_full_history)
    #         # Select date range for plotting
    #         plot_start_date, plot_end_date = st.select_slider(
    #             "Select Date Range for Plotting",
    #             options=pd.to_datetime(df_full_history['Date']).sort_values(),
    #             value=(df_full_history['Date'].min(), df_full_history['Date'].max())
    #         )
            
    #         filtered_df = df_full_history[(df_full_history['Date'] >= plot_start_date) & (df_full_history['Date'] <= plot_end_date)]
            
    #         st.write(filtered_df)
    #         plot_wave_height(filtered_df, f'Wave Height (WVHT) at Station {station_id} ({plot_start_date.date()} to {plot_end_date.date()})')
    #         #plot_wave_height(df_full_history, station_id)
    #     else:
    #         st.write("No data available for the specified range.")
            
#"Water level CEHQ"
if choice == "Water level CEHQ":
    # Streamlit app layout
    st.title("Hydrometric Station Data Processor")
    
    # User input for station number
    station_number = st.text_input("Enter the Station Number", "030240_N")
    
    # URL construction based on station number
    url = f"https://www.cehq.gouv.qc.ca/depot/historique_donnees/fichier/{station_number}.txt"
    
     # Function to fetch and process data
    def fetch_and_process_data(url):
        response = requests.get(url)
        lines = response.text.split('\n')
    
        # Extracting station description
        description = lines[:21]
        
        # Processing the data
        data = [line.split() for line in lines[22:] if line.strip()]  # Assuming data starts from line 22
        df = pd.DataFrame(data)

        df.columns = ['Station', 'Date', 'Water Level', 'Info']

        # Splitting 'Column2' into 'year', 'month', and 'day'
        df[['year', 'month', 'day']] = df['Date'].str.split('/', expand=True)
        df['Water Level'] = pd.to_numeric(df['Water Level'], errors='coerce')

        
        # Convert year, month, and day to integers
        df['year'] = df['year'].astype(int)
        df['month'] = df['month'].astype(int)
        df['day'] = df['day'].astype(int)

        # Group by year and calculate statistics
        grouped = df.groupby('year')['Water Level']
        max_indices = grouped.idxmax()
        min_indices = grouped.idxmin()
        max_values = grouped.max()
        min_values = grouped.min()
        none_counts = grouped.apply(lambda x: x.isna().sum())

        # Extracting dates for max and min values
        #max_dates = df.loc[max_indices, 'Date']
        #min_dates = df.loc[min_indices, 'Date']
        
        # Combining results
        annual_stats = pd.DataFrame({
            'None Count': none_counts,
            'Max Value':grouped.max(),
            #'Date of Max Value': df.loc[grouped.idxmax(), 'Date'],
            'Min Value': grouped.min(),
            #'Date of Min Value':  df.loc[grouped.idxmin(), 'Date']
        })
        date_stats = pd.DataFrame({
            'Date of Max Value': df.loc[grouped.idxmax(), 'Date'],
            'Date of Min Value':  df.loc[grouped.idxmin(), 'Date']
         })
        
        # # Calculating annual statistics
        # none_counts = df.groupby('year')['Water Level'].apply(lambda x: x.isna().sum())  
        # max_values = df.groupby('year')['Water Level'].max()
        # min_values = df.groupby('year')['Water Level'].min()
        
        # annual_stats = pd.DataFrame({
        #     'None Count': none_counts,
        #     'Max Value': max_values,
        #     'Min Value': min_values
        # })

        
        # if len(df.columns) == 4:
        #     df.columns = ['Column1', 'Column2', 'Column3', 'Column4']  # Replace with actual column names
        # else:
        #     st.error(f"Unexpected number of columns. Found: {len(df.columns)}")
        #     return None, None, None
    
        # # Handling the date column
        # df['Date'] = pd.to_datetime(df['Date'], errors='coerce')  # Convert Date column to datetime
        
        ## Convert data columns to numeric as needed
        #df['Column2'] = pd.to_numeric(df['Column2'], errors='coerce')  # Example for numeric conversion
    
        # Calculating annual min, max, and missing values
        #annual_stats = df.agg({'Column2': ['min', 'max'], 'Column3': ['count']})
        
        return description, df, annual_stats,date_stats
        
        #return description, df
    
    # Display the results
    if st.button("Fetch Data"):
        #description, df = fetch_and_process_data(url)
        description, df, annual_stats, date_stats = fetch_and_process_data(url)
        st.write("Station Description:")
        st.write(description)
        st.write("Dataframe:")
        st.dataframe(df)
        st.write("Annual Statistics:")
        st.dataframe(annual_stats)

        # Set the style for nicer plots
        plt.style.use('seaborn-darkgrid')
        
        # Creating a figure and axis
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Width of a bar 
        width = 0.25       
        
        # Setting the positions of the bars
        ind = annual_stats.index.astype(str)  # Assuming the index of annual_stats is the year
        ind = range(len(ind))  # Convert to numeric index for plotting
        
        # Plotting
        ax.bar(ind, annual_stats['Max Value'], width, label='Max Value')
        ax.bar([i + width for i in ind], annual_stats['Min Value'], width, label='Min Value')
        ax.bar([i + width*2 for i in ind], annual_stats['None Count'], width, label='None Count')
        
        # Adding labels and title
        ax.set_xlabel('Year')
        ax.set_ylabel('Values')
        ax.set_title('Annual Water Level Statistics')
        ax.set_xticks([i + width for i in ind])
        ax.set_xticklabels(annual_stats.index.astype(str))
        
        # Adding a legend
        ax.legend()
        
        # Show the plot
        st.pyplot(fig)

        st.dataframe(date_stats)
    
        # # Plotting
        # fig, ax = plt.subplots()
        # ax.plot(df['Column1'], df['Column2'])  # Replace 'Column1' and 'Column2' with actual columns
        # ax.set_title("Annual Min and Max")
        # st.pyplot(fig)
    
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
        # df = daily_flow_data
        # df["Date"] = pd.to_datetime(df["Date"])
        # years = df["Year"].unique()
        st.subheader("Hydrographs")
        years = daily_flow_data["Year"].unique()
        for year in years:
            df_year = daily_flow_data[daily_flow_data["Year"] == year]
            #df_year.set_index("Date", inplace=True)
            # Calculate the rolling sum of flow for spring and fall periods
            df_year["Rolling_Spring"] = df_year.loc[:pd.Timestamp(
                year, sep_month, sep_day), "Flow"].rolling(window=spring_volume_period).sum()
            df_year["Rolling_Fall"] = df_year.loc[pd.Timestamp(
                year, sep_month, sep_day):, "Flow"].rolling(window=fall_volume_period).sum()

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

            # Maximum and minimum values for spring and fall periods
            spring_max = df_year.loc[:pd.Timestamp(
                year, sep_month, sep_day), "Flow"].max()
            spring_min = df_year.loc[:pd.Timestamp(
                year, sep_month, sep_day), "Flow"].min()
            fall_max = df_year.loc[pd.Timestamp(
                year, sep_month, sep_day):, "Flow"].max()
            fall_min = df_year.loc[pd.Timestamp(
                year, sep_month, sep_day):, "Flow"].min()

            # Add red and green dots for maximum and minimum values of spring and fall periods
            spring_max_date = df_year.loc[:pd.Timestamp(
                year, sep_month, sep_day), "Flow"].idxmax()
            spring_min_date = df_year.loc[:pd.Timestamp(
                year, sep_month, sep_day), "Flow"].idxmin()
            fall_max_date = df_year.loc[pd.Timestamp(
                year, sep_month, sep_day):, "Flow"].idxmax()
            fall_min_date = df_year.loc[pd.Timestamp(
                year, sep_month, sep_day):, "Flow"].idxmin()

            ax.plot(spring_max_date, spring_max, "ro")
            ax.plot(spring_min_date, spring_min, "go")
            ax.plot(fall_max_date, fall_max, "ro")
            ax.plot(fall_min_date, fall_min, "go")

            ax.set_title(f"Hydrograph for {year}")
            ax.set_ylabel("Flow")
            ax.legend(loc="best")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

            st.pyplot(fig)

            st.write(
                f"Spring Volume Period: {spring_start_date.strftime('%d-%m')} to {spring_end_date.strftime('%d-%m')}")
            st.write(
                f"Fall Volume Period: {fall_start_date.strftime('%d-%m')} to {fall_end_date.strftime('%d-%m')}")
            st.write(
                f"Max and Min for Spring: {spring_max} ({spring_max_date.strftime('%d-%m')}), {spring_min} ({spring_min_date.strftime('%d-%m')})")
            st.write(
                f"Max and Min for Fall: {fall_max} ({fall_max_date.strftime('%d-%m')}), {fall_min} ({fall_min_date.strftime('%d-%m')})")
    else:
        st.info("Please upload a CSV file.")

# Peak Flow Comparison page
elif choice == "Peak Flow Comparison":
    st.title("Peak Flow Comparison")
    st.write("Make sure these csv files contain matching years.")

    uploaded_file1 = st.file_uploader(
        "Choose the first CSV file (daily flow data)", type="csv")
    uploaded_file2 = st.file_uploader(
        "Choose the second CSV file (flow data every 15 minutes)", type="csv")

    if uploaded_file1 is not None and uploaded_file2 is not None:
        df1 = pd.read_csv(uploaded_file1)
        df2 = pd.read_csv(uploaded_file2)
    
        max_df1 = df1.groupby("Year")["Flow"].max().reset_index().rename(columns={"Flow": "max_Daily"})
        max_df2 = df2.groupby("Year")["Flow"].max().reset_index().rename(columns={"Flow": "max_Instant"})
    
        merged_df = pd.merge(max_df1, max_df2, on="Year", how="inner")
        merged_df["Ratio"] = merged_df["max_Instant"] / merged_df["max_Daily"]
        mean_ratio = merged_df["Ratio"].mean()
    
        st.write("Details for each year:")
        st.write(merged_df)
    
        st.write(f"Mean of ratios: {mean_ratio}")

# # EC Canada Daily Data
elif choice == "EC Daily Data Analysis":
    # Set the style for the plots
    plt.style.use('seaborn-whitegrid')
    
    st.title('Climate Data Analysis')

    # File uploader
    uploaded_file = st.file_uploader("Upload a CSV file with climate data:", type="csv")
    
    # Only proceed with the rest of the app if a file is uploaded
    if uploaded_file is not None:
        df = process_file(uploaded_file)
        if df is not None:
             # Text input for start date
            start_date = st.text_input('Enter start date (YYYY-MM-DD):')
            # Text input for end date
            end_date = st.text_input('Enter end date (YYYY-MM-DD):')
    
            # Check if the dates are entered and valid
            if start_date and end_date:
                try:
                    start_date = pd.to_datetime(start_date)
                    end_date = pd.to_datetime(end_date)
                    
                    # Filter the DataFrame based on the input dates
                    filtered_df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]

                    st.subheader('Temperature Analysis')
                    fig, ax = plt.subplots(figsize=(10, 5))
                    
                    # Remove grid and add black contour
                    ax.grid(True, linestyle='--')
                    ax.spines['top'].set_color('black')
                    ax.spines['bottom'].set_color('black')
                    ax.spines['left'].set_color('black')
                    ax.spines['right'].set_color('black')

                    # Setting the ticks
                    ax.tick_params(axis='x', which='both', bottom=True, top=True, labelbottom=True)
                    ax.tick_params(axis='y', which='both', left=True, right=True, labelleft=True)

                    # Plotting the line plots for temperature
                    ax.plot(filtered_df['Date'], filtered_df['Max Temp (°C)'], label='Max Temp', color='darkred')
                    ax.plot(filtered_df['Date'], filtered_df['Min Temp (°C)'], label='Min Temp', color='red')
                    ax.plot(filtered_df['Date'], filtered_df['Mean Temp (°C)'], label='Mean Temp', color='salmon')
                    
                    # Calculate the monthly average temperatures
                    monthly_avg_temps = filtered_df.resample('M', on='Date')['Mean Temp (°C)'].mean()
                    month_names = monthly_avg_temps.index.strftime('%B')

                    # Creating a table at the top of the graph
                    col_labels = ['Month', 'Avg Temp (°C)']
                    table_vals = list(zip(month_names, monthly_avg_temps.round(1)))
                    table = ax.table(cellText=table_vals, colLabels=col_labels, loc='top', cellLoc='center')
                    table.auto_set_font_size(False)
                    table.set_fontsize(9)
                    table.scale(1, 1.5)

                    # Overlay a bar chart for monthly average temperatures
                    ax.bar(monthly_avg_temps.index, monthly_avg_temps, width=20, color='pink', label='Monthly Avg Temp', alpha=0.5, align='center')
                    
                    #ax.set_xlabel('Date')
                    ax.set_ylabel('Temperature (°C)')
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Automatic tick locator
                    fig.autofmt_xdate()

                    # Adjusting the legend
                    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='small', frameon=True)

                    # Adjust layout to make room for the table and legend
                    plt.subplots_adjust(left=0.2, bottom=0.2, top=0.8, right=0.8)
                    st.pyplot(fig)

                    
                    # fig, ax = plt.subplots(figsize=(10, 5))
                    
                    # # Calculate the monthly average temperatures
                    # monthly_avg_temps = filtered_df.resample('M', on='Date')['Mean Temp (°C)'].mean()
                    # month_names = monthly_avg_temps.index.strftime('%B')

                    # # Creating a table at the top of the graph
                    # col_labels = ['Month', 'Avg Temp (°C)']
                    # table_vals = list(zip(month_names, monthly_avg_temps.round(1)))
                    # table = ax.table(cellText=table_vals, colLabels=col_labels, loc='top', cellLoc='center')
                    # table.auto_set_font_size(False)
                    # table.set_fontsize(9)
                    # table.scale(1, 1.5)

                    # # Plotting the line plots for temperature
                    # ax.plot(filtered_df['Date'], filtered_df['Max Temp (°C)'], label='Max Temp', color='darkred')
                    # ax.plot(filtered_df['Date'], filtered_df['Min Temp (°C)'], label='Min Temp', color='red')
                    # ax.plot(filtered_df['Date'], filtered_df['Mean Temp (°C)'], label='Mean Temp', color='salmon')
                    
                    # # Overlay a bar chart for monthly average temperatures
                    # ax.bar(monthly_avg_temps.index, monthly_avg_temps, width=20, color='pink', label='Monthly Avg Temp', alpha=0.5, align='center')
                    
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Temperature (°C)')
                    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    # ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Automatic tick locator
                    # fig.autofmt_xdate()
                    # ax.legend()

                    # # Adjust layout to make room for the table
                    # plt.subplots_adjust(left=0.2, bottom=0.2, top=0.8)
                    # st.pyplot(fig)

    
                    # st.subheader('Temperature Analysis')
                    # fig, ax = plt.subplots(figsize=(10, 5))
                    
                    # # Plotting the line plots for temperature
                    # ax.plot(filtered_df['Date'], filtered_df['Max Temp (°C)'], label='Max Temp', color='darkred')
                    # ax.plot(filtered_df['Date'], filtered_df['Min Temp (°C)'], label='Min Temp', color='red')
                    # ax.plot(filtered_df['Date'], filtered_df['Mean Temp (°C)'], label='Mean Temp', color='salmon')
                    
                    # # Calculate the monthly average temperatures
                    # monthly_avg_temps = filtered_df.resample('M', on='Date')['Mean Temp (°C)'].mean()
                    
                    # # Overlay a bar chart for monthly average temperatures
                    # ax.bar(monthly_avg_temps.index, monthly_avg_temps, width=20, color='pink', label='Monthly Avg Temp', alpha=0.5, align='center')
                    
                    # # Annotate the bars with values
                    # for idx, value in enumerate(monthly_avg_temps):
                    #     ax.annotate(f'{value:.1f}', 
                    #                 (monthly_avg_temps.index[idx], value), 
                    #                 textcoords="offset points", 
                    #                 xytext=(0,10), 
                    #                 ha='center')
                    
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Temperature (°C)')
                    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    # ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Automatic tick locator
                    # fig.autofmt_xdate()
                    # ax.legend()
                    # st.pyplot(fig)
                    
                    # fig, ax = plt.subplots(figsize=(8, 4))
                    # ax.plot(filtered_df['Date'], filtered_df['Max Temp (°C)'], label='Max Temp', color='tomato')
                    # ax.plot(filtered_df['Date'], filtered_df['Min Temp (°C)'], label='Min Temp', color='dodgerblue')
                    # ax.plot(filtered_df['Date'], filtered_df['Mean Temp (°C)'], label='Mean Temp', color='green')
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Temperature (°C)')
                    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    # fig.autofmt_xdate()
                    # ax.legend()
                    # st.pyplot(fig)

                    # Precipitation Analysis
                    st.subheader('Precipitation Analysis')
                    fig, ax = plt.subplots(figsize=(10, 5))

                    # Remove grid and add black contour
                    ax.grid(True, linestyle='--')
                    ax.spines['top'].set_color('black')
                    ax.spines['bottom'].set_color('black')
                    ax.spines['left'].set_color('black')
                    ax.spines['right'].set_color('black')


                    # Calculate the monthly precipitation stats
                    monthly_precip = filtered_df.resample('M', on='Date')['Total Precip (mm)']
                    monthly_stats = pd.DataFrame({
                        'Min Rain (mm)': monthly_precip.min(),
                        'Max Rain (mm)': monthly_precip.max(),
                        'Total Rain (mm)': monthly_precip.sum()
                    }).round(1)
                    month_names = monthly_stats.index.strftime('%B')

                    # Creating a table at the top of the graph
                    table_vals = [month_names] + [monthly_stats[col].values for col in monthly_stats.columns]
                    table = ax.table(cellText=table_vals, rowLabels=['Month', 'Min Rain', 'Max Rain', 'Total Rain'], loc='top', cellLoc='center')
                    table.auto_set_font_size(False)
                    table.set_fontsize(6)  # Adjusted font size
                    table.scale(1, 1.5)

                    # Plotting the bar chart for precipitation
                    ax.bar(filtered_df['Date'], filtered_df['Total Precip (mm)'], color='deepskyblue', width=1.0)  # Adjusted color and width
                    ax.set_xlabel('Date')
                    ax.set_ylabel('Precipitation (mm)')
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Automatic tick locator
                    fig.autofmt_xdate()

                    # Adjust layout to make room for the table
                    plt.subplots_adjust(left=0.2, bottom=0.2, top=0.8)
                    st.pyplot(fig)

                    
                    # fig, ax = plt.subplots(figsize=(10, 5))

                    # # Calculate the monthly precipitation stats
                    # monthly_precip = filtered_df.resample('M', on='Date')['Total Precip (mm)']
                    # monthly_stats = pd.DataFrame({
                    #     'Min Rain (mm)': monthly_precip.min(),
                    #     'Max Rain (mm)': monthly_precip.max(),
                    #     'Total Rain (mm)': monthly_precip.sum()
                    # }).round(1)
                    # month_names = monthly_stats.index.strftime('%B')

                    # # Creating a table at the top of the graph
                    # table_vals = [month_names] + [monthly_stats[col].values for col in monthly_stats.columns]
                    # table = ax.table(cellText=table_vals, rowLabels=['Month', 'Min Rain', 'Max Rain', 'Total Rain'], loc='top', cellLoc='center')
                    # table.auto_set_font_size(False)
                    # table.set_fontsize(9)
                    # table.scale(1, 1.5)

                    # # Plotting the bar chart for precipitation
                    # ax.bar(filtered_df['Date'], filtered_df['Total Precip (mm)'], color='lightblue')
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Precipitation (mm)')
                    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    # ax.xaxis.set_major_locator(mdates.AutoDateLocator())  # Automatic tick locator
                    # fig.autofmt_xdate()

                    # # Adjust layout to make room for the table
                    # plt.subplots_adjust(left=0.2, bottom=0.2, top=0.8)
                    # st.pyplot(fig)
                    
                    # fig, ax = plt.subplots(figsize=(8, 4))
                    # ax.bar(filtered_df['Date'], filtered_df['Total Precip (mm)'], color='lightblue')
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Precipitation (mm)')
                    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    # fig.autofmt_xdate()
                    # st.pyplot(fig)

                    # Snow Analysis
                    st.subheader('Snow Analysis')
                    fig, ax = plt.subplots(figsize=(8, 4))
                    ax.plot(filtered_df['Date'], filtered_df['Snow on Grnd (cm)'], color='lightgrey')
                    ax.set_xlabel('Date')
                    ax.set_ylabel('Snow on Ground (cm)')
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    fig.autofmt_xdate()
                    st.pyplot(fig)

                    ##For now, not added
                    # # Wind Gust Analysis
                    # st.subheader('Wind Gust Analysis')
                    # fig, ax = plt.subplots(figsize=(8, 4))
                    # ax.plot(filtered_df['Date'], filtered_df['Spd of Max Gust (km/h)'], color='purple')
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Speed of Max Gust (km/h)')
                    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    # fig.autofmt_xdate()
                    # st.pyplot(fig)

                    
                    # Temperature analysis
                    # st.subheader('Temperature Analysis')
                    # fig, ax = plt.subplots()
                    # ax.plot(filtered_df['Date/Time'], filtered_df['Max Temp (°C)'], label='Max Temp')
                    # ax.plot(filtered_df['Date/Time'], filtered_df['Min Temp (°C)'], label='Min Temp')
                    # ax.plot(filtered_df['Date/Time'], filtered_df['Mean Temp (°C)'], label='Mean Temp')
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Temperature (°C)')
                    # ax.legend()
                    # st.pyplot(fig)
                
                    # Precipitation analysis
                    # st.subheader('Precipitation Analysis')
                    # fig, ax = plt.subplots()
                    # ax.bar(filtered_df['Date/Time'], filtered_df['Total Precip (mm)'])
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Precipitation (mm)')
                    # st.pyplot(fig)
                
                    # Snow analysis
                    # st.subheader('Snow Analysis')
                    # fig, ax = plt.subplots()
                    # ax.plot(filtered_df['Date/Time'], filtered_df['Snow on Grnd (cm)'])
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Snow on Ground (cm)')
                    # st.pyplot(fig)
                
                    # Wind Gust analysis
                    # st.subheader('Wind Gust Analysis')
                    # fig, ax = plt.subplots()
                    # ax.plot(filtered_df['Date/Time'], filtered_df['Spd of Max Gust (km/h)'])
                    # ax.set_xlabel('Date')
                    # ax.set_ylabel('Speed of Max Gust (km/h)')
                    # st.pyplot(fig)
                except ValueError as e:
                        st.error("The dates entered are invalid. Please enter valid dates in the format YYYY-MM-DD.")
    
# # Camera Viewer page

elif choice == "Camera Viewer":
    st.title("Camera Viewer")

    # Step 1: Add a file uploader for the zip file
    uploaded_file = st.file_uploader("Choose a zip file", type="zip")

    if uploaded_file is not None:
        # Step 2: Extract the zip file and read its contents
        with zipfile.ZipFile(uploaded_file, "r") as zfile:
            zfile.extractall("temp_folder")

        # Step 3: Process the image files and the CSV files
        image_files = []
        hydrograph_df = None
        rain_df = None
        temperature_df = None

        for root, _, files in os.walk("temp_folder"):
            for file in files:
                if file.lower().endswith(".jpg"):
                    image_files.append(os.path.join(root, file))
                elif file == "Hydrograph.csv":
                    hydrograph_df = pd.read_csv(os.path.join(
                        root, file), parse_dates=[["Date", "Time"]])
                elif file == "Rain.csv":
                    rain_df = pd.read_csv(os.path.join(
                        root, file), parse_dates=[["Date", "Time"]])
                elif file == "Temperature.csv":
                    temperature_df = pd.read_csv(os.path.join(
                        root, file), parse_dates=[["Date", "Time"]])

        st.write(f"Uploaded file: {uploaded_file}")
        st.write(f"Number of image files: {len(image_files)}")
        st.write(f"Hydrograph dataframe: {hydrograph_df.head()}")
        st.write(f"Rain dataframe: {rain_df.head()}")
        st.write(f"Temperature dataframe: {temperature_df.head()}")

        # Step 4: For each image file, display the image and plot the graphs
        for img_file in image_files:
            # Extract the time from the image filename
            # Remove ".jpg" from the filename
            img_time_str = os.path.basename(img_file)[:-4]
            img_time = datetime.strptime(img_time_str, "%m%d%Y%H%M")

            st.image(
                img_file, caption=f"Image taken at {img_time.strftime('%Y-%m-%d %H:%M')}")

            fig, ax = plt.subplots(3, 1, figsize=(10, 15), sharex=True)

            for idx, (df, title, ylabel) in enumerate(zip([hydrograph_df, rain_df, temperature_df], ["Flow", "Rain", "Temperature"], ["Flow", "Rain", "Temperature"])):
                # Filter the data within 3 days before and after the image time
                mask = (df["Date_Time"] >= img_time - timedelta(days=3)
                        ) & (df["Date_Time"] <= img_time + timedelta(days=3))
                data = df[mask]

                # Plot the graph
                ax[idx].plot(data["Date_Time"], data[title], label=title)
                ax[idx].set_ylabel(ylabel)

                if not data.empty:  # Add this condition before finding the closest time
                    # Add a red dot at the image time
                    min_index = (data["Date_Time"] - img_time).abs().idxmin()
                    if min_index in data.index:
                        closest_time = data.loc[min_index, "Date_Time"]
                    else:
                        closest_time = img_time
                    ax[idx].plot(closest_time, data.loc[data["Date_Time"] ==
                                                        closest_time, title].values[0], "ro", label="Image time")

                    # Adjust y-axis label to 6 increments
                    min_value, max_value = ax[idx].get_ylim()
                    ax[idx].yaxis.set_ticks(
                        np.linspace(min_value, max_value, 6))

                ax[idx].legend()
            # for idx, (df, title, ylabel) in enumerate(zip([hydrograph_df, rain_df, temperature_df], ["Flow", "Rain", "Temperature"], ["Flow", "Rain", "Temperature"])):
            #     # Filter the data within 15 days before and after the image time
            #     mask = (df["Date_Time"] >= img_time - timedelta(days=15)
            #             ) & (df["Date_Time"] <= img_time + timedelta(days=15))
            #     data = df[mask]

            #     # Plot the graph
            #     ax[idx].plot(data["Date_Time"], data[title], label=title)
            #     ax[idx].set_ylabel(ylabel)

            #     if not data.empty:  # Add this condition before finding the closest time
            #         # Add a red dot at the image time
            #         min_index = (data["Date_Time"] - img_time).abs().idxmin()
            #         if min_index in data.index:
            #             closest_time = data.loc[min_index, "Date_Time"]
            #         else:
            #             closest_time = img_time
            #         ax[idx].plot(closest_time, data.loc[data["Date_Time"] ==
            #                                             closest_time, title].values[0], "ro", label="Image time")

            #     ax[idx].legend()

            plt.xlabel("Date")
            plt.xticks(rotation=45)
            st.pyplot(fig)
        shutil.rmtree("temp_folder")
# elif choice == "Camera Viewer":
#     st.title("Camera Viewer")

#     # Step 1: Add a file uploader for the zip file
#     uploaded_file = st.file_uploader("Choose a zip file", type="zip")
#     st.write(f"Uploaded file: {uploaded_file}")
#     if uploaded_file is not None:

#         # Step 2: Extract the zip file and read its contents
#         with zipfile.ZipFile(uploaded_file, "r") as zfile:
#             zfile.extractall("temp_folder")

        # # Step 3: Process the image files and the CSV files
        # image_files = []
        # hydrograph_df = None
        # rain_df = None
        # temperature_df = None

        # for root, _, files in os.walk("temp_folder"):
        #     for file in files:
        #         if file.lower().endswith(".jpg"):
        #             image_files.append(os.path.join(root, file))
        #         elif file == "Hydrograph.csv":
        #             hydrograph_df = pd.read_csv(os.path.join(
        #                 root, file), parse_dates=[["Date", "Time"]])
        #         elif file == "Rain.csv":
        #             rain_df = pd.read_csv(os.path.join(
        #                 root, file), parse_dates=[["Date", "Time"]])
        #         elif file == "Temperature.csv":
        #             temperature_df = pd.read_csv(os.path.join(
        #                 root, file), parse_dates=[["Date", "Time"]])

        # st.write(f"Uploaded file: {uploaded_file}")
        # st.write(f"Number of image files: {len(image_files)}")
        # st.write(f"Hydrograph dataframe: {hydrograph_df.head()}")
        # st.write(f"Rain dataframe: {rain_df.head()}")
        # st.write(f"Temperature dataframe: {temperature_df.head()}")

        # # Step 4: For each image file, display the image and plot the graphs
        # for img_file in image_files:
        #     # Extract the time from the image filename
        #     # Remove "image.jpg" from the filename
        #     img_time_str = os.path.basename(img_file)[:-8]
        #     img_time = datetime.strptime(img_time_str, "%m-%d-%Y-%H-%M")

        #     st.image(
        #         img_file, caption=f"Image taken at {img_time.strftime('%Y-%m-%d %H:%M')}")

        #     fig, ax = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
        #     for idx, (df, title, ylabel) in enumerate(zip([hydrograph_df, rain_df, temperature_df], ["Flow", "Rain", "Temperature"], ["Flow", "Rain", "Temperature"])):
        #         # Filter the data within 15 days before and after the image time
        #         mask = (df["Date_Time"] >= img_time - timedelta(days=15)
        #                 ) & (df["Date_Time"] <= img_time + timedelta(days=15))
        #         data = df[mask]

        #         # Plot the graph
        #         ax[idx].plot(data["Date_Time"], data[title], label=title)
        #         ax[idx].set_ylabel(ylabel)

        #         # Add a red dot at the image time
        #         closest_time = data.iloc[(
        #             data["Date_Time"] - img_time).abs().idxmin()]["Date_Time"]
        #         ax[idx].plot(closest_time, data.loc[data["Date_Time"] ==
        #                                             closest_time, title].values[0], "ro", label="Image time")

        #         ax[idx].legend()

        #     plt.xlabel("Date")
        #     plt.xticks(rotation=45)
        #     st.pyplot(fig)

        # # # Clean up the temporary folder
        # # for root, _, files in os.walk("temp_folder"):
        # #     for file in files:
        # #         os.remove(os.path.join(root, file))
        # # os.rmdir("temp_folder")

        # # Clean up the temporary folder
        # shutil.rmtree("temp_folder")

# elif choice == "Camera Viewer":
#     st.title("Camera Viewer")

#     # Step 1: Add a file uploader for the zip file
#     uploaded_file = st.file_uploader("Choose a zip file", type="zip")

#     if uploaded_file is not None:
#         # Step 2: Extract the zip file and read its contents
#         with zipfile.ZipFile(uploaded_file, "r") as zfile:
#             zfile.extractall("temp_folder")

#         # Step 3: Process the image files and the CSV files
#         image_files = []
#         hydrograph_df = None
#         rain_df = None
#         temperature_df = None

#         for root, _, files in os.walk("temp_folder"):
#             for file in files:
#                 if file.endswith(".png"):
#                     image_files.append(os.path.join(root, file))
#                 elif file == "Hydrograph.csv":
#                     hydrograph_df = pd.read_csv(os.path.join(
#                         root, file), parse_dates=[["Date", "Time"]])
#                 elif file == "Rain.csv":
#                     rain_df = pd.read_csv(os.path.join(
#                         root, file), parse_dates=[["Date", "Time"]])
#                 elif file == "Temperature.csv":
#                     temperature_df = pd.read_csv(os.path.join(
#                         root, file), parse_dates=[["Date", "Time"]])

#         # Step 4: For each image file, display the image and plot the graphs
#         for img_file in image_files:
#             # Extract the time from the image filename
#             # Remove "image.png" from the filename
#             img_time_str = os.path.basename(img_file)[:-9]
#             img_time = datetime.strptime(img_time_str, "%m%d%Y%H%M")

#             st.image(
#                 img_file, caption=f"Image taken at {img_time.strftime('%Y-%m-%d %H:%M')}")

#             fig, ax = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
#             for idx, (df, title, ylabel) in enumerate(zip([hydrograph_df, rain_df, temperature_df], ["Flow", "Rain", "Temperature"], ["Flow", "Rain", "Temperature"])):
#                 # Filter the data within 15 days before and after the image time
#                 mask = (df["Date_Time"] >= img_time - timedelta(days=15)
#                         ) & (df["Date_Time"] <= img_time + timedelta(days=15))
#                 data = df[mask]

#                 # Plot the graph
#                 ax[idx].plot(data["Date_Time"], data[title], label=title)
#                 ax[idx].set_ylabel(ylabel)

#                 # Add a red dot at the image time
#                 closest_time = data.iloc[(
#                     data["Date_Time"] - img_time).abs().idxmin()]["Date_Time"]
#                 ax[idx].plot(closest_time, data.loc[data["Date_Time"] ==
#                                                     closest_time, title].values[0], "ro", label="Image time")

#                 ax[idx].legend()

#             plt.xlabel("Date")
#             plt.xticks(rotation=45)
#             st.pyplot(fig)

#         # Clean up the temporary folder
#         for root, _, files in os.walk("temp_folder"):
#             for file in files:
#                 os.remove(os.path.join(root, file))
#         shutil.rmtree("temp_folder")
#         # os.r

# Frequency Analysis page
elif choice == "Frequency Analysis v2":
    st.title('Statistical Distribution Analysis')
    uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])
    if uploaded_file is not None:
        data = pd.read_csv(uploaded_file, header=None).squeeze()
        if data is not None:
            criteria = []
            criteria.append(fit_and_calculate_criteria(data, stats.norm, 'Normal'))
            # criteria.append(fit_and_calculate_criteria(data, stats.lognorm, 'Log-normal'))
            # criteria.append(fit_and_calculate_criteria(data, stats.genextreme, 'Generalized Extreme Value'))
            # criteria.append(fit_and_calculate_criteria(data, stats.gumbel_r, 'Gumbel'))
            # criteria.append(fit_and_calculate_criteria(data, stats.pearson3, 'Pearson Type 3'))
            st.write(criteria)
            if st.button('Show Normal Plot'):
                create_plot_normal(data)
    else:
        st.stop()
    



    
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
