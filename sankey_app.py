import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---- Streamlit page config ----
st.set_page_config(page_title="Dynamic Tier Sankey", layout="wide")

# ---- Custom styles ----
st.markdown("""
<style>
.block-container {padding-top: 2rem;}
.stDataFrame, .stDataEditor {border:1px solid #e0e0e0; border-radius:8px; background:#fff;}
.stButton>button, .stDownloadButton>button {margin-top:1rem;}
</style>
""", unsafe_allow_html=True)

st.title("Sankey Diagram Generator")

# ---- Diagram title and units above the table ----
col_title, col_units = st.columns(2)
with col_title:
    diagram_title = st.text_input("Diagram Title", "Sankey Diagram")
with col_units:
    units = st.text_input("Units", "kWh")

# ---- Example data ----
default_data = {
    "source": ["Steam","Natural Gas","Steam","Process","Process","Process","Process","Process","Process","Process","Natural Gas"],
    "target": ["Distribution Losses","Efficiency Losses","Process","Sterlisers","Tray Wash","Wash Tub","Viscera Table","Hoses","Apron Wash","Amenities","Steam"],
    "value": [151291,86533,3654678,1254675,627337,165515,627337,493088,341368,145358,3805969]
}
df = st.data_editor(pd.DataFrame(default_data), num_rows="dynamic", width='stretch')
df = df.dropna(subset=["source","target","value"]).reset_index(drop=True)

# ---- Appearance options ----
st.markdown("### Appearance Options")
colA, colB, colC = st.columns([2,1,2])

with colA:
    font_family = st.selectbox(
        "Font Family",
        ["Paralucent", "Arial", "Courier New", "Times New Roman", "Verdana", "Tahoma"],
        index=0
    )
with colB:
    font_size = st.slider("Font Size", 10, 20, 14)
with colC:
    palette_options = {
        "Default": ["#41484f", "#015651", "#49dd5b", "#48bfaf", "#4c2d83"],
        "High Contrast": ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33", "#a65628", "#f781bf"],
        "Earthy": ["#b58900", "#cb4b16", "#268bd2", "#2aa198", "#859900", "#6c71c4", "#d33682","#073642", "#fdf6e3"],
    }
    palette_name = st.selectbox("Color Palette", list(palette_options.keys()), index=0)
    color_palette = palette_options[palette_name]

# ---- Node display options ----
st.markdown("### Node Display Options")
col1, col2 = st.columns([2,2])
with col1:
    display_mode = st.radio("Show on nodes", ["Values", "Percentages"], horizontal=True)
with col2:
    if display_mode == "Values":
        round_factor = st.selectbox("Round to nearest", [10000, 1000, 100, 10, 1], index=3)
    else:
        percent_format = st.selectbox("Decimal places", [0,1,2,3], index=0)

st.markdown("**Note:** Preview may appear blurry due to Streamlit rendering limitations. Downloaded HTML is fully interactive and clear.")

# ---- Function to generate Sankey ----
def create_sankey(df, font_family, font_size, color_palette, display_mode, round_factor=None, percent_format=None):
    if df.empty:
        return None

    labels = pd.unique(df[["source","target"]].values.ravel())
    label_idx = {lbl: i for i, lbl in enumerate(labels)}

    # ---- Assign tiers dynamically ----
    tiers = {lbl: None for lbl in labels}
    def assign_tier(lbl, current_tier):
        if tiers[lbl] is None or current_tier > tiers[lbl]:
            tiers[lbl] = current_tier
            for child in df[df['source']==lbl]['target']:
                assign_tier(child, current_tier + 1)
    roots = [lbl for lbl in labels if lbl not in df['target'].values]
    for root in roots:
        assign_tier(root, 0)
    max_tier = max(tiers.values())

    # ---- Node positions ----
    x = [tiers[lbl]/max_tier if max_tier > 0 else 0.5 for lbl in labels]
    tier_groups = {}
    for i, lbl in enumerate(labels):
        tier_groups.setdefault(tiers[lbl], []).append(i)
    y = [0]*len(labels)
    for tier, indices in tier_groups.items():
        count = len(indices)
        tier_top = 1 - tier / (max_tier + 1)
        tier_bottom = 1 - (tier + 1) / (max_tier + 1)
        if count == 1:
            y[indices[0]] = (tier_top + tier_bottom)/2
        else:
            margin = 0.05 * (tier_top - tier_bottom)
            step = ((tier_top - tier_bottom) - 2*margin) / (count - 1)
            for j, idx in enumerate(indices):
                y[idx] = tier_bottom + margin + j*step

    # ---- Node labels with values underneath ----
    tier0_nodes = [lbl for lbl, t in tiers.items() if t == 0]
    tier0_sum = df[df['source'].isin(tier0_nodes)]['value'].sum()
    node_labels = []
    for lbl in labels:
        val = df[df["target"]==lbl]["value"].sum() or df[df["source"]==lbl]["value"].sum()
        if display_mode == "Values":
            val_text = f"{round(val/round_factor)*round_factor:,} {units}"
        else:
            val_text = f"{val/tier0_sum*100:.{percent_format}f}%"
        node_labels.append(f"{lbl}\n({val_text})")

    # ---- Node colors ----
    node_color_list = [color_palette[i % len(color_palette)] for i in range(len(labels))]

    # ---- Link colors ----
    def hex_to_rgba(hex_color, alpha=0.3):
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2],16), int(hex_color[2:4],16), int(hex_color[4:6],16)
        return f"rgba({r},{g},{b},{alpha})"
    link_colors = [hex_to_rgba(node_color_list[label_idx[s]]) for s in df["source"]]

    # ---- Plotly Sankey ----
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=30, thickness=20, line=dict(color="#41484f", width=0),
            label=node_labels, x=x, y=y, color=node_color_list,
            hovertemplate='%{label}<extra></extra>'
        ),
        link=dict(
            source=[label_idx[s] for s in df["source"]],
            target=[label_idx[t] for t in df["target"]],
            value=df["value"],
            color=link_colors,
            hovertemplate='<b>%{source.label} → %{target.label}</b><br>Value: %{value:,} ' + units + '<extra></extra>',
        )
    ))

    fig.update_layout(
        title_text=diagram_title,
        title_font=dict(size=18, family=font_family),
        font=dict(size=font_size, family=font_family, color="#41484f"),
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=30, r=30, t=80, b=80),
        height=700
    )

    return fig

# ---- Generate Sankey live ----
fig = create_sankey(
    df, font_family, font_size, color_palette, display_mode,
    round_factor=round_factor if display_mode=="Values" else None,
    percent_format=percent_format if display_mode=="Percentages" else None
)

if fig:
    st.plotly_chart(fig, width="stretch", height=700)
    st.download_button(
        "Download Sankey as HTML",
        fig.to_html(include_plotlyjs='cdn'),
        "sankey.html",
        "text/html"
    )
