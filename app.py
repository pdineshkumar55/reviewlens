"""Streamlit entry point. UI only: all processing lives in the reviewlens package."""

from __future__ import annotations

import hmac
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from reviewlens.config import ROOT, get_settings
from reviewlens.export import EXPORT_COLUMNS, to_csv_bytes
from reviewlens.llm import AnalysisServiceError
from reviewlens.pipeline import AnalysisRun, run_analysis
from reviewlens.schema import CATEGORIES, NEEDS_REVIEW, SENTIMENTS, URGENCIES
from reviewlens.usage import DailyCounter, log_run
from reviewlens.validation import REQUIRED_COLUMNS, ValidationError, load_reviews
from ui import components, copy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("reviewlens.app")

SAMPLE_FILE = ROOT / "data" / "reviews_sample_240.csv"
TABLE_COLUMNS = [
    "review_id",
    "date",
    "platform",
    "rating",
    "language",
    "sentiment",
    "category",
    "urgency",
    "summary",
    "suggested_reply",
]

settings = get_settings()
st.set_page_config(page_title=copy.APP_TITLE, page_icon=copy.PAGE_ICON, layout="wide")


# --- access code -------------------------------------------------------------


def access_granted() -> bool:
    if not settings.access_code or st.session_state.get("authorised"):
        return True
    st.title(copy.ACCESS_TITLE)
    with st.form("access"):
        code = st.text_input(copy.ACCESS_LABEL, type="password")
        if st.form_submit_button(copy.ACCESS_BUTTON):
            if hmac.compare_digest(code.encode(), settings.access_code.encode()):
                st.session_state["authorised"] = True
                st.rerun()
            st.error(copy.ACCESS_WRONG)
    return False


# --- sidebar -----------------------------------------------------------------


def sidebar() -> tuple[str, bool]:
    """Draw the sidebar. Returns (business_name, use_cache) if a run was requested."""
    st.sidebar.header(copy.SIDEBAR_HEADER)
    business = st.sidebar.text_input(copy.BUSINESS_LABEL, value=settings.business_name, help=copy.BUSINESS_HELP)

    upload = st.sidebar.file_uploader(copy.UPLOAD_LABEL, type=["csv"], help=copy.UPLOAD_HELP)
    if upload is not None:
        st.session_state["source"] = (upload.name, upload.getvalue())

    if st.sidebar.button(copy.SAMPLE_BUTTON, width="stretch"):
        st.session_state["source"] = (SAMPLE_FILE.name, SAMPLE_FILE.read_bytes())
        st.session_state["requested"] = True
        st.session_state["use_cache"] = True

    source = st.session_state.get("source")
    if source:
        st.sidebar.caption(copy.FILE_READY.format(name=source[0]))

    col1, col2 = st.sidebar.columns(2)
    if col1.button(copy.ANALYSE_BUTTON, type="primary", width="stretch"):
        st.session_state["requested"] = True
        st.session_state["use_cache"] = True
    if col2.button(copy.REANALYSE_BUTTON, help=copy.REANALYSE_HELP, width="stretch"):
        st.session_state["requested"] = True
        st.session_state["use_cache"] = False

    st.sidebar.caption(copy.LIMITS_NOTE.format(mb=settings.max_upload_mb, rows=settings.max_rows))
    return business, st.session_state.get("use_cache", True)


# --- running -----------------------------------------------------------------


def start(business: str, use_cache: bool) -> None:
    st.session_state["requested"] = False
    source = st.session_state.get("source")
    if not source:
        st.warning(copy.NO_FILE)
        return
    name, data = source
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        st.error(copy.FILE_TOO_LARGE.format(mb=settings.max_upload_mb))
        return

    try:
        df, summary = load_reviews(data, max_rows=settings.max_rows)
    except ValidationError as exc:
        st.error(copy.FILE_INVALID.format(reason=str(exc)))
        return
    except Exception:
        log.exception("could not read upload")
        st.error(copy.FILE_INVALID.format(reason=""))
        return
    st.session_state["validation"] = summary
    if df.empty:
        st.error(copy.NO_ROWS)
        return

    runs = st.session_state.get("runs", 0)
    if runs >= settings.max_runs_per_session:
        st.error(copy.SESSION_LIMIT.format(n=settings.max_runs_per_session))
        return
    if not DailyCounter(settings.cache_dir / "usage.sqlite").try_acquire(settings.daily_run_cap):
        log_run(settings.log_dir, {"input_rows": len(df), "outcome": "cap_hit"})
        st.error(copy.DAILY_LIMIT)
        return
    st.session_state["runs"] = runs + 1

    bar = st.progress(0.0, text=copy.PROCESSING.format(done=0, total=len(df)))

    def progress(done: int, total: int) -> None:
        if done >= total:
            bar.progress(1.0, text=copy.BUILDING_REPORT)
        else:
            bar.progress(done / max(total, 1), text=copy.PROCESSING.format(done=done, total=total))

    try:
        result = run_analysis(df, settings, business_name=business, progress=progress, use_cache=use_cache)
    except AnalysisServiceError as exc:
        log.error(
            "Could not reach the analysis service. Check your connection and API key in .env, then retry. (%s)", exc
        )
        bar.empty()
        st.error(copy.SERVICE_UNAVAILABLE)
        return
    except Exception:
        log.exception("run failed")
        bar.empty()
        st.error(copy.UNEXPECTED_ERROR)
        return
    bar.empty()
    st.session_state["result"] = result
    st.session_state["source_name"] = name
    st.toast(copy.RUN_DONE.format(rows=len(result.df), secs=result.duration_s, cached=result.cached))


# --- views -------------------------------------------------------------------


def validation_box() -> None:
    summary = st.session_state.get("validation")
    if not summary:
        return
    with st.expander(copy.VALIDATION_TITLE):
        st.write(copy.VALIDATION_READ.format(n=summary.rows_read))
        st.write(copy.VALIDATION_KEPT.format(n=summary.rows_kept))
        if summary.dropped:
            for reason, n in summary.dropped.items():
                st.write(copy.VALIDATION_DROPPED.format(n=n, reason=reason))
        else:
            st.write(copy.VALIDATION_CLEAN)


def empty_state() -> None:
    st.subheader(copy.EMPTY_TITLE)
    st.write(copy.EMPTY_BODY)
    st.caption(copy.EMPTY_FORMAT)
    st.code(",".join(REQUIRED_COLUMNS), language=None)


def overview(result: AnalysisRun) -> None:
    agg = result.aggregates
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(copy.KPI_TOTAL, agg.analysed)
    c2.metric(copy.KPI_POSITIVE, f"{agg.sentiment_pct['positive']}%")
    c3.metric(copy.KPI_NEGATIVE, f"{agg.sentiment_pct['negative']}%")
    c4.metric(copy.KPI_URGENT, agg.urgent, help=copy.KPI_URGENT_HELP)

    st.markdown(f"**{copy.CHART_SENTIMENT}**")
    st.plotly_chart(components.sentiment_chart(agg), width="stretch", config={"displayModeBar": False})

    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"**{copy.CHART_CATEGORY}**")
        st.plotly_chart(components.category_chart(agg), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown(f"**{copy.CHART_PLATFORM}**")
        st.plotly_chart(components.platform_chart(agg), width="stretch", config={"displayModeBar": False})

    df = result.df
    pending = df[df["status"] == NEEDS_REVIEW]
    if not pending.empty:
        with st.expander(copy.NEEDS_REVIEW_TITLE.format(n=len(pending))):
            st.caption(copy.NEEDS_REVIEW_BODY)
            cols = ["review_id", "date", "platform", "rating", "urgency", "review_text"]
            st.dataframe(components.display_table(pending, cols), hide_index=True, width="stretch")
    spam = df[df["status"] == "spam"]
    if not spam.empty:
        with st.expander(copy.SPAM_TITLE.format(n=len(spam))):
            st.caption(copy.SPAM_BODY)
            cols = ["review_id", "date", "platform", "rating", "review_text"]
            st.dataframe(components.display_table(spam, cols), hide_index=True, width="stretch")


def reviews(result: AnalysisRun) -> None:
    df = result.df
    high_only = st.toggle(copy.HIGH_ONLY, key="high_only")
    f1, f2, f3, f4 = st.columns(4)
    sentiments = f1.multiselect(
        copy.FILTER_SENTIMENT, list(SENTIMENTS), format_func=copy.SENTIMENT_LABELS.get, key="f_sent"
    )
    categories = f2.multiselect(
        copy.FILTER_CATEGORY, list(CATEGORIES), format_func=copy.CATEGORY_LABELS.get, key="f_cat"
    )
    platforms = f3.multiselect(copy.FILTER_PLATFORM, sorted(df["platform"].unique()), key="f_plat")
    urgencies = f4.multiselect(
        copy.FILTER_URGENCY,
        list(URGENCIES),
        format_func=copy.URGENCY_LABELS.get,
        key="f_urg",
        disabled=high_only,
    )

    view = df[df["status"] != "spam"]
    if high_only:
        view = view[view["urgency"] == "high"]
    elif urgencies:
        view = view[view["urgency"].isin(urgencies)]
    if sentiments:
        view = view[view["sentiment"].isin(sentiments)]
    if categories:
        view = view[view["category"].isin(categories)]
    if platforms:
        view = view[view["platform"].isin(platforms)]
    view = view.sort_values(["date", "review_id"], ascending=[False, True]).reset_index(drop=True)

    st.caption(copy.SHOWING.format(shown=len(view), total=int((df["status"] != "spam").sum())))
    if view.empty:
        st.info(copy.NO_MATCH)
        return

    st.caption(copy.SELECT_HINT)
    event = st.dataframe(
        components.display_table(view, TABLE_COLUMNS),
        hide_index=True,
        width="stretch",
        height=460,
        on_select="rerun",
        selection_mode="single-row",
        key="review_table",
        column_config={
            copy.COLUMNS["summary"]: st.column_config.TextColumn(width="large"),
            copy.COLUMNS["suggested_reply"]: st.column_config.TextColumn(width="large"),
        },
    )
    selected = event.selection.rows if event and event.selection else []
    if selected:
        row = view.iloc[selected[0]]
        with st.container(border=True):
            st.markdown(f"**{row['review_id']}** · {row['platform']} · {row['rating']}/5 · {row['date']}")
            st.markdown(f"**{copy.DETAIL_REVIEW}**")
            st.write(row["review_text"])
            if row["summary"]:
                st.markdown(f"**{copy.DETAIL_SUMMARY}**")
                st.write(row["summary"])
            if row["suggested_reply"]:
                st.markdown(f"**{copy.DETAIL_REPLY}**")
                st.code(row["suggested_reply"], language=None, wrap_lines=True)
            if row.get("urgency_rule"):
                st.caption(copy.DETAIL_RULE)
            if row.get("reply_fallback"):
                st.caption(copy.DETAIL_FALLBACK)


def weekly_report(result: AnalysisRun) -> None:
    st.code(result.report_text, language=None)
    stem = f"weekly_report_{result.aggregates.date_to or 'week'}"
    c1, c2, _ = st.columns([1, 1, 4])
    c1.download_button(copy.REPORT_DOWNLOAD_TXT, result.report_text.encode("utf-8"), f"{stem}.txt", "text/plain")
    c2.download_button(copy.REPORT_DOWNLOAD_MD, result.report_markdown.encode("utf-8"), f"{stem}.md", "text/markdown")


def export(result: AnalysisRun) -> None:
    st.subheader(copy.EXPORT_TITLE)
    st.write(copy.EXPORT_BODY.format(cols=", ".join(EXPORT_COLUMNS)))
    source = Path(st.session_state.get("source_name", "reviews.csv")).stem
    st.download_button(copy.EXPORT_BUTTON, to_csv_bytes(result.df), f"{source}_tagged.csv", "text/csv", type="primary")
    preview = pd.DataFrame(result.df[EXPORT_COLUMNS].head(10))
    st.dataframe(components.display_table(preview, EXPORT_COLUMNS), hide_index=True, width="stretch")


# --- page --------------------------------------------------------------------


def main() -> None:
    if not access_granted():
        return
    st.title(copy.APP_TITLE)
    st.caption(copy.APP_TAGLINE)

    business, use_cache = sidebar()
    if st.session_state.get("requested"):
        start(business, use_cache)

    validation_box()
    result: AnalysisRun | None = st.session_state.get("result")
    if result is None:
        empty_state()
        return

    # A key keeps the selected tab when a filter change reruns the script.
    t1, t2, t3, t4 = st.tabs(
        [copy.TAB_OVERVIEW, copy.TAB_REVIEWS, copy.TAB_REPORT, copy.TAB_EXPORT], key="main_tabs", on_change="rerun"
    )
    with t1:
        overview(result)
    with t2:
        reviews(result)
    with t3:
        weekly_report(result)
    with t4:
        export(result)


main()
