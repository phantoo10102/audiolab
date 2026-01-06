import streamlit as st


def init_styles():
    st.markdown(
        """
        <style>
            header[data-testid="stHeader"] { visibility: hidden; height: 0; }
            [data-testid="stAppViewContainer"] { background: #0e1117; }
            .block-container { padding-top: 1.0rem !important; padding-bottom: 2.5rem !important; max-width: 1600px; }
            h1, h2, h3, h4, h5, h6, p, span, div { color: #fafafa; }
            .stCaption { color: #9ca3af !important; font-size: 13px !important; }
            button[kind="secondary"] { border: 1px solid #41444e; color: #e5e7eb; background-color: #262730; }
            button[kind="primary"] {
                background: #22d3ee !important; border: none !important; color: #000 !important; font-weight: 800 !important;
                transition: all 0.2s ease;
            }
            button[kind="primary"]:hover {
                filter: brightness(1.07); box-shadow: 0 0 18px rgba(34, 211, 238, 0.18); transform: translateY(-1px);
            }
            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-color: rgba(65, 68, 78, 0.9) !important; background: #1c1e24;
            }
            .streamlit-expanderHeader {
                font-weight: 700; color: #fafafa; background-color: #1c1e24; border-radius: 10px; border: 1px solid rgba(65, 68, 78, 0.9);
            }
            button[data-baseweb="tab"] { color: #9ca3af !important; font-weight: 650 !important; }
            button[data-baseweb="tab"][aria-selected="true"] { color: #fafafa !important; }
            div[data-baseweb="tab-border"] { background-color: rgba(65,68,78,0.5) !important; }
            div[data-baseweb="tab-highlight"] { background-color: #22d3ee !important; }
            div[data-testid="stNumberInput"] label { display: none; }
            div[data-testid="stNumberInput"] { margin-top: -8px !important; }
            label[data-testid="stCheckbox"] { color: #4facfe !important; font-weight: 700; }
        </style>
    """,
        unsafe_allow_html=True,
    )


def render_header(active: str = "Editor"):
    """Render header UI"""
    st.markdown(
        f"""
        <div style="position: sticky; top: 0; z-index: 999; background: #0e1117;">
          <div style="color:#9ca3af; font-size: 13px;">{active}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
