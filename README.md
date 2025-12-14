# **📊 RFM Customer Segmentation Engine**

> **🔴 View Live Demo:** [https://naserr.streamlit.app/](https://naserr.streamlit.app/)

## **🚀 Overview**

**RFM Growth Engine** is a powerful, interactive analytics tool designed to transform raw customer transaction data into actionable marketing insights.

Built with **Python** and **Streamlit**, this application automates the **RFM (Recency, Frequency, Monetary)** analysis process, allowing businesses to segment their customer base dynamically and identify "Champions", "Loyal Customers", and those "At Risk" of churning.

## **🌟 Key Features**

* **Dynamic Weighting Strategy:** Unlike static RFM tools, this engine allows users to adjust the importance of Recency, Frequency, and Monetary value (0-10 scale) to fit specific business models (e.g., High-ticket vs. FMCG).  
* **Smart Data Mapping:** Automatically detects and suggests column mapping for any uploaded Excel file.  
* **Interactive Visualizations:** Features dynamic Treemaps powered by **Plotly** to visualize segment distribution.  
* **Churn & Loyalty Analysis:** Calculates real-time Key Performance Indicators (KPIs) such as **Loyalty Rate**, **Churn Risk**, and **Average CLV**.  
* **Privacy-Preserving:** All data processing happens on-the-fly; extra columns (Emails, Phones) are preserved in the export but not stored.

## **🛠️ Tech Stack**

* **Core:** Python 3.8+  
* **Frontend:** Streamlit  
* **Data Processing:** Pandas  
* **Visualization:** Plotly Express  
* **I/O:** OpenPyXL

## **📦 How to Run Locally**

1. **Clone the repository:** git clone [https://github.com/naserr/rfm-growth-engine.git](https://github.com/naserr/rfm-growth-engine.git)  
   cd rfm-growth-engine

2. **Create a virtual environment (Optional but recommended):** python -m venv .venv  
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

3. **Install dependencies:** pip install -r requirements.txt

4. **Run the app:** streamlit run app.py

## **🤝 Contributing**

Contributions, issues, and feature requests are welcome!

*Built with ❤️ by [Naser Rahmani](https://github.com/naserr) | Technical Growth Engineer*
