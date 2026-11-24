"""Model dropdown with visible, individually disabled options."""
from pathlib import Path

import streamlit as st

model_picker = st.components.v2.component(
    "impactmap_model_picker",
    html='<select aria-label="Model"></select>',
    css="""
        select { width: 100%; min-height: 38px; padding: 0.4rem 0.6rem;
            border: 1px solid var(--st-border-color, #888); border-radius: 8px;
            background: var(--st-secondary-background-color, #f0f2f6);
            color: var(--st-text-color, #31333f); font: inherit; }
        option:disabled { color: #888; }
        select:disabled { opacity: 0.5; }
    """,
    js=Path(__file__).with_name("model_picker.js").read_text(),
)
