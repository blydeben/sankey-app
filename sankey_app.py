import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Dynamic Tier Sankey Generator", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem;}
.stDataFrame, .stDataEditor {border:1px solid #e0e0e0; border-radius:8px; background:#fff;}
.stButton>button, .stDownloadButton>button {margin-top:1rem;}
</style>
""", unsafe_allow_html=True)

st.title("Sankey Diagram Generator")

# ---- User inputs ----
col1, col2, col3, col4 = st.columns([2,2,2,2])

with col1:
    diagram_title = st.text_input("Diagram title", "Sankey Diagram")

with col2:
    units = st.text_input("Units", "kWh")

with col3:
    display_mode = st.radio("Show on nodes", ["Values","Percentages"], horizontal=True)

with col4:
    if display_mode == "Values":
        round_factor = st.selectbox("Round to nearest", [10000,1000,100,10,1], index=3)
    else:
        percent_format = st.selectbox("Number of decimal places", [0,1,2,3], index=0)

# ---- Example data ----
default_data = {
    "source": ["Steam","Natural Gas","Steam","Process","Process","Process","Process","Process","Process","Process","Natural Gas"],
    "target": ["Distribution Losses","Efficiency Losses","Process","Sterlisers","Tray Wash","Wash Tub","Viscera Table","Hoses","Apron Wash","Amenities","Steam"],
    "value": [151291,86533,3654678,1254675,627337,165515,627337,493088,341368,145358,3805969]
}
df = st.data_editor(pd.DataFrame(default_data), num_rows="dynamic", width='stretch')
df = df.dropna(subset=["source","target","value"]).reset_index(drop=True)

# ---- Generate Sankey ----
if st.button("Generate Sankey"):

    # ---- Heading above plot ----
    if display_mode == "Values":
        rounding_text = f"Nearest {round_factor}"
    else:
        rounding_text = f"{percent_format} decimal place(s)"

    st.markdown(f"**{diagram_title}** | Units: {units} | Rounding: {rounding_text} | Display Mode: {display_mode}")

    if df.empty:
        st.warning("⚠️ No valid data to plot.")
    else:
        labels = pd.unique(df[["source","target"]].values.ravel())
        label_idx = {label:i for i,label in enumerate(labels)}

        # ---- Assign dynamic tiers ----
        tiers = {lbl: None for lbl in labels}
        def assign_tier(lbl, current_tier):
            if tiers[lbl] is None or current_tier > tiers[lbl]:
                tiers[lbl] = current_tier
                for child in df[df['source']==lbl]['target']:
                    assign_tier(child, current_tier+1)
        sources = [lbl for lbl in labels if lbl not in df['target'].values]
        for src in sources:
            assign_tier(src, 0)

        # ---- Normalize x positions ----
        max_tier = max(tiers.values())
        x = [tiers[lbl]/max_tier if max_tier>0 else 0.5 for lbl in labels]

        # ---- y positions (tier-based spacing) ----
        tier_groups = {}
        for i,lbl in enumerate(labels):
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

        # ---- Node labels ----
        tier0_nodes = [lbl for lbl, t in tiers.items() if t == 0]
        tier0_sum = df[df['source'].isin(tier0_nodes)]['value'].sum()

        node_labels = []
        for lbl in labels:
            val = df[df["target"]==lbl]["value"].sum() or df[df["source"]==lbl]["value"].sum()
            if display_mode == "Values":
                val_text = f"{round(val/round_factor)*round_factor:,} {units}"
            else:
                val_text = f"{val/tier0_sum*100:.{percent_format}f}%"
            node_labels.append(f"{lbl}<br><span style='font-size:12px'>{val_text}</span>")

        # ---- Colour palette (without #f3f8ec) ----
        palette = ["#41484f", "#015651", "#49dd5b", "#48bfaf", "#4c2d83"]

        # Assign colours to nodes
        node_colors = {}
        for i, lbl in enumerate(labels):
            node_colors[lbl] = palette[i % len(palette)]
        node_color_list = [node_colors[lbl] for lbl in labels]

        # Assign semi-transparent link colours based on source node
        def hex_to_rgba(hex_color, alpha=0.3):
            hex_color = hex_color.lstrip("#")
            r, g, b = int(hex_color[0:2],16), int(hex_color[2:4],16), int(hex_color[4:6],16)
            return f"rgba({r},{g},{b},{alpha})"

        link_colors = [hex_to_rgba(node_colors[s], alpha=0.3) for s in df["source"]]

        # ---- Plotly Sankey ----
        fig = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                pad=30, thickness=18, line=dict(color="#41484f", width=0),
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
            title_font=dict(size=18, color="#41484f", family="Paralucent"),
            font_size=16, font_family="Paralucent",
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=30,r=30,t=80,b=80), height=700
        )

        # ---- Use width="stretch" instead of deprecated use_container_width ----
        st.plotly_chart(fig, width="stretch", height=700)

        import plotly.io as pio
        
