import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO
import io
import base64
import docx
from scipy.stats import norm, lognorm, pearson3, gamma, gumbel_r, genextreme

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

# Hydrograph Producer page
elif choice == "Hydrograph Producer":
    st.title("Hydrograph Producer")

    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.write(df)

        # Convert the "Date" column to a datetime object
        df["Date"] = pd.to_datetime(df["Date"])

        years = df["Year"].unique()
        st.subheader("Hydrographs")
        for year in years:
            df_year = df[df["Year"] == year]

            # Find the maximum and minimum values and their dates
            max_value = df_year["Flow"].max()
            min_value = df_year["Flow"].min()
            max_date = df_year[df_year["Flow"] == max_value]["Date"].iloc[0]
            min_date = df_year[df_year["Flow"] == min_value]["Date"].iloc[0]

            fig, ax = plt.subplots(figsize=(15, 6))
            ax.plot(df_year["Date"], df_year["Flow"])
            ax.scatter([max_date], [max_value], color="red", label="Maximum")
            ax.scatter([min_date], [min_value], color="green", label="Minimum")
            ax.set_title(f"Hydrograph for {year}")

            # Format the x-axis to display the month of the year
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

            ax.set_xlabel("Month")
            ax.set_ylabel("Flow")
            ax.legend(loc='best')
            st.pyplot(fig)

            st.write(
                f"Maximum: {max_value} on {max_date.strftime('%Y-%m-%d')}")
            st.write(
                f"Minimum: {min_value} on {min_date.strftime('%Y-%m-%d')}")


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
        data = pd.read_csv(uploaded_file, header=None, names=['flow'])
        max_flow = data['flow'].to_numpy()

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
