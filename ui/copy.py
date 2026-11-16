"""Every user-visible string in the app.

scripts/check_ui_copy.py scans this file and app.py for banned words and
AI-style phrasing, so keep copy plain, specific and in sentence case.
"""

APP_TITLE = "ReviewLens"
APP_TAGLINE = "Tag a week of customer reviews and see what needs attention."
PAGE_ICON = "\U0001f4ca"  # bar chart

# Access code
ACCESS_TITLE = "Enter access code"
ACCESS_LABEL = "Access code"
ACCESS_BUTTON = "Continue"
ACCESS_WRONG = "That code is not correct."

# Sidebar
SIDEBAR_HEADER = "Reviews"
BUSINESS_LABEL = "Business name"
BUSINESS_HELP = "Used in replies to positive reviews and in the report header."
UPLOAD_LABEL = "Upload reviews (CSV)"
UPLOAD_HELP = "Columns: review_id, date, platform, rating, review_text."
SAMPLE_BUTTON = "Try with sample data"
SAMPLE_LOADED = "Sample file loaded: {name} ({rows} rows)."
ANALYSE_BUTTON = "Analyse"
REANALYSE_BUTTON = "Re-analyse all"
REANALYSE_HELP = "Ignore saved results and process every review again."
FILE_READY = "Ready: {name}"
LIMITS_NOTE = "Limits: {mb} MB per file, {rows} reviews per run."

# Run status
PROCESSING = "Processing reviews {done} / {total}"
BUILDING_REPORT = "Building report"
RUN_DONE = "Done. {rows} reviews processed in {secs:.0f} s ({cached} reused from earlier runs)."

# Errors and limits
NO_FILE = "Upload a CSV file or use the sample data first."
FILE_TOO_LARGE = "The file is larger than {mb} MB. Split it into smaller files."
FILE_INVALID = "This file could not be read. {reason}"
NO_ROWS = "No usable reviews were found in this file."
SERVICE_UNAVAILABLE = "Analysis service unavailable. Please retry in a minute."
UNEXPECTED_ERROR = "Something went wrong while processing the file. Please retry."
SESSION_LIMIT = "You have reached the limit of {n} runs for this session."
DAILY_LIMIT = "Daily limit reached. Please try again tomorrow."

# Validation summary
VALIDATION_TITLE = "File check"
VALIDATION_READ = "Rows read: {n}"
VALIDATION_KEPT = "Reviews kept: {n}"
VALIDATION_DROPPED = "Dropped: {n} ({reason})"
VALIDATION_CLEAN = "No rows dropped."

# Empty state
EMPTY_TITLE = "No reviews analysed yet"
EMPTY_BODY = (
    "Upload a CSV of reviews in the sidebar and press Analyse, or press Try with sample data to see a demo week."
)
EMPTY_FORMAT = "Expected columns"

# Tabs
TAB_OVERVIEW = "Overview"
TAB_REVIEWS = "Reviews"
TAB_REPORT = "Weekly report"
TAB_EXPORT = "Export"

# Overview
KPI_TOTAL = "Reviews"
KPI_POSITIVE = "Positive"
KPI_NEGATIVE = "Negative"
KPI_URGENT = "Urgent"
KPI_URGENT_HELP = "High-urgency reviews that need a reply within 24 hours."
CHART_SENTIMENT = "Sentiment split"
CHART_CATEGORY = "Reviews by category"
CHART_PLATFORM = "Reviews by platform"
AXIS_REVIEWS = "Reviews"
NEEDS_REVIEW_TITLE = "Needs review ({n})"
NEEDS_REVIEW_BODY = "These reviews could not be tagged automatically. They are not counted in the percentages."
SPAM_TITLE = "Spam ({n})"
SPAM_BODY = "Adverts or unrelated text. Not counted and no reply suggested."

# Reviews tab
FILTER_SENTIMENT = "Sentiment"
FILTER_CATEGORY = "Category"
FILTER_PLATFORM = "Platform"
FILTER_URGENCY = "Urgency"
HIGH_ONLY = "Show only high urgency"
SHOWING = "Showing {shown} of {total} reviews."
SELECT_HINT = "Select a row to read the full review and copy the reply."
DETAIL_REVIEW = "Review"
DETAIL_SUMMARY = "Summary"
DETAIL_REPLY = "Suggested reply"
DETAIL_RULE = "Marked high urgency because the review mentions a health or safety issue."
DETAIL_FALLBACK = "Standard reply used for this review."
NO_MATCH = "No reviews match these filters."

# Weekly report tab
REPORT_DOWNLOAD_TXT = "Download .txt"
REPORT_DOWNLOAD_MD = "Download .md"

# Export tab
EXPORT_TITLE = "Download the tagged reviews"
EXPORT_BODY = "UTF-8 CSV that opens in Excel with Tamil text intact. Columns: {cols}."
EXPORT_BUTTON = "Download CSV"

# Table column headers
COLUMNS = {
    "review_id": "Review ID",
    "date": "Date",
    "platform": "Platform",
    "rating": "Rating",
    "language": "Language",
    "sentiment": "Sentiment",
    "category": "Category",
    "urgency": "Urgency",
    "summary": "Summary",
    "suggested_reply": "Suggested reply",
    "review_text": "Review",
    "status": "Status",
}

# Value labels
SENTIMENT_LABELS = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
CATEGORY_LABELS = {
    "food_quality": "Food quality",
    "delivery": "Delivery",
    "price": "Price",
    "staff": "Staff",
    "packaging": "Packaging",
    "app": "Ordering app",
}
URGENCY_LABELS = {"high": "High", "medium": "Medium", "low": "Low", "needs_review": "Needs review"}
STATUS_LABELS = {"ok": "Tagged", "needs_review": "Needs review", "spam": "Spam"}
