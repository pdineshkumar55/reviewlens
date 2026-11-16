"""Charts and table helpers for the Streamlit app."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from reviewlens.aggregate import Aggregates
from ui import copy

# Sentiment is a polarity scale: blue <-> red with a gray midpoint.
SENTIMENT_COLOURS = {"positive": "#2a78d6", "neutral": "#a3a29b", "negative": "#e34948"}
SINGLE_SERIES = "#2a78d6"
SURFACE_GAP = dict(color="rgba(252,252,251,1)", width=2)
FONT = dict(size=13)


def _layout(fig: go.Figure, height: int = 320, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=16, t=8, b=8),
        font=FONT,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="", traceorder="normal"),
        bargap=0.35,
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, zeroline=False)
    fig.update_yaxes(showgrid=False)
    return fig


def sentiment_chart(agg: Aggregates) -> go.Figure:
    fig = go.Figure()
    for key in ["positive", "neutral", "negative"]:
        count = agg.sentiment_counts[key]
        pct = agg.sentiment_pct[key]
        fig.add_bar(
            y=[""],
            x=[count],
            name=copy.SENTIMENT_LABELS[key],
            orientation="h",
            marker=dict(color=SENTIMENT_COLOURS[key], line=SURFACE_GAP),
            text=[f"{copy.SENTIMENT_LABELS[key]} {pct}%"] if pct >= 8 else None,
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white"),
            hovertemplate=f"{copy.SENTIMENT_LABELS[key]}: %{{x}} ({pct}%)<extra></extra>",
        )
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title_text=copy.AXIS_REVIEWS)
    return _layout(fig, height=170, legend=True)


def category_chart(agg: Aggregates) -> go.Figure:
    table = agg.category_table.sort_values("total")
    labels = [copy.CATEGORY_LABELS[c] for c in table.index]
    fig = go.Figure()
    for key in ["positive", "neutral", "negative"]:
        fig.add_bar(
            y=labels,
            x=table[key],
            name=copy.SENTIMENT_LABELS[key],
            orientation="h",
            marker=dict(color=SENTIMENT_COLOURS[key], line=SURFACE_GAP),
            hovertemplate=f"%{{y}}<br>{copy.SENTIMENT_LABELS[key]}: %{{x}}<extra></extra>",
        )
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title_text=copy.AXIS_REVIEWS)
    return _layout(fig, height=320, legend=True)


def platform_chart(agg: Aggregates) -> go.Figure:
    table = agg.platform_table.sort_values("total")
    fig = go.Figure(
        go.Bar(
            y=list(table.index),
            x=table["total"],
            orientation="h",
            marker=dict(color=SINGLE_SERIES, line=SURFACE_GAP),
            text=table["total"],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x}<extra></extra>",
        )
    )
    fig.update_xaxes(title_text=copy.AXIS_REVIEWS)
    return _layout(fig, height=320)


def display_table(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Readable labels for the on-screen table (export keeps raw values)."""
    out = df[columns].copy()
    if "sentiment" in out:
        out["sentiment"] = out["sentiment"].map(lambda v: copy.SENTIMENT_LABELS.get(v, copy.URGENCY_LABELS.get(v, v)))
    if "category" in out:
        out["category"] = out["category"].map(lambda v: copy.CATEGORY_LABELS.get(v, copy.URGENCY_LABELS.get(v, v)))
    if "urgency" in out:
        out["urgency"] = out["urgency"].map(lambda v: copy.URGENCY_LABELS.get(v, v))
    if "status" in out:
        out["status"] = out["status"].map(lambda v: copy.STATUS_LABELS.get(v, v))
    return out.rename(columns=copy.COLUMNS)
