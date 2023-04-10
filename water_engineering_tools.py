import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO

# Page configuration
st.set_page_config(page_title="Water Engineering Tools", layout="wide")

# Main menu
menu = ["Home", "Hydrograph Producer", "Peak Flow Comparison", "Camera Viewer"]
choice = st.sidebar.selectbox("Menu", menu)

# Home page
if choice == "Home":
    st.title("Water Engineering Tools")
    st.markdown("""
    Welcome to the Water Engineering Tools web app, developed by a junior engineer. This app consists of three tools:
    
    1. **Hydrograph Producer**: Import a CSV file containing daily flow data time series and plot the hydrograph for each year, displaying max, min, and the number of missing values.
    
    2. **Peak Flow Comparison**: Compare two time series. The first time series is the daily flow data of a river, and the second is the flow data every 15 minutes of the same river. The tool compares the maximum value for every year of both time series and returns a table with the ratio for every specific year, with the mean of the ratios in the last row.

    3. **Camera Viewer**: Input images and display them on the webpage.
    """)

# Hydrograph Producer page
elif choice == "Hydrograph Producer":
    st.title("Hydrograph Producer")

    # File upload
    csv_file = st.file_uploader(
        "Upload your daily flow data CSV file", type=["csv"])

    if csv_file:
        data = pd.read_csv(csv_file)
        st.write(data.head())

        # Extract year list
        years = list(data['Year'].unique())

        # Plot hydrograph for each year
        for year in years:
            yearly_data = data[data['Year'] == year]
            plt.plot(yearly_data['Date'], yearly_data['Flow'])
            plt.title(f"Hydrograph for {year}")
            plt.xlabel("Date")
            plt.ylabel("Flow")
            st.pyplot(plt)
            plt.clf()

        # Display max, min and number of missing values
        st.write("Max value: ", data['Flow'].max())
        st.write("Min value: ", data['Flow'].min())
        st.write("Number of missing values: ", data['Flow'].isna().sum())

# Peak Flow Comparison page
elif choice == "Peak Flow Comparison":
    st.title("Peak Flow Comparison")

    # File uploads
    daily_csv = st.file_uploader(
        "Upload your daily flow data CSV file", type=["csv"])
    minute_csv = st.file_uploader(
        "Upload your 15-minute flow data CSV file", type=["csv"])

    if daily_csv and minute_csv:
        daily_data = pd.read_csv(daily_csv)
        minute_data = pd.read_csv(minute_csv)

        daily_max = daily_data.groupby("Year")["Flow"].max()
        minute_max = minute_data.groupby("Year")["Flow"].max()

        comparison = pd.concat([daily_max, minute_max], axis=1).dropna()
        comparison.columns = ["Daily Max", "15-Min Max"]
        comparison["Ratio"] = comparison["15-Min Max"] / \
            comparison["Daily Max"]

        comparison.loc["Mean"] = comparison.mean()
        st.write(comparison)

# Camera Viewer page
elif choice == "Camera Viewer":
    st.title("Camera Viewer")

    # File upload
    image_file = st.file_uploader(
        "Upload your image file", type=["png", "jpg", "jpeg"])

    if image_file:
        st.image(image_file, caption="Uploaded Image", use_column_width=True)
