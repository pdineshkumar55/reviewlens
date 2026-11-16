"""Build the synthetic review files in data/ (deterministic, no API calls).

    python scripts/make_sample_data.py

Writes:
  data/reviews_week40.csv      the three rows from the course brief
  data/reviews_sample_240.csv  240 valid reviews + 2 junk rows (empty text, duplicate ID)
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEED = 40
WEEK_START = date(2026, 9, 29)

BRIEF_ROWS = [
    ("R-1041", "2026-10-03", "Zomato", 5, "Biryani was amazing, packing also neat. Will order again!"),
    ("R-1042", "2026-10-03", "Swiggy", 1, "Ordered at 8pm, came at 9:10. Food fully cold. Very bad."),
    ("R-1043", "2026-10-04", "Google", 2, "Saapadu nalla irundhuchu but bill la extra charge pottanga"),
]

ITEMS_EN = [
    "biryani",
    "chicken biryani",
    "masala dosa",
    "ghee roast dosa",
    "parotta",
    "meals",
    "filter coffee",
    "idli",
    "pongal",
    "chicken 65",
    "mutton biryani",
    "kothu parotta",
]
ITEMS_TA = ["பிரியாணி", "தோசை", "பரோட்டா", "சாப்பாடு", "ஃபில்டர் காபி", "இட்லி", "பொங்கல்"]

EN = {
    "positive": [
        "The {item} was excellent, will definitely order again.",
        "Loved the {item}. Hot, fresh and well packed.",
        "Great {item} and quick delivery. Thank you!",
        "Best {item} in town and the staff were very polite.",
        "Neat packaging and a generous portion of {item}.",
        "Ordered {item} for the family and everyone loved it.",
        "Good value for money, the {item} was tasty.",
        "Fast delivery and the {item} was still hot.",
        "Friendly staff at the counter and really tasty {item}.",
        "The {item} tasted just like home. Filter coffee was perfect too.",
        "Consistent quality every time. The {item} never disappoints.",
        "Quick service even on a busy Sunday, {item} was spot on.",
    ],
    "neutral": [
        "The {item} was okay, nothing special.",
        "Food was decent but the place was crowded.",
        "Average {item}. A bit pricey for the quantity.",
        "Delivery was 15 minutes late but the {item} was fine.",
        "Taste was fine, packaging could be better.",
        "ok",
    ],
    "negative": [
        "The {item} was too salty this time.",
        "Portion of {item} was very small for the price.",
        "Delivery took 40 minutes extra and the {item} was lukewarm.",
        "Extra packing charges were added to the bill without telling us.",
        "Sambar leaked inside the bag, packaging needs to improve.",
        "The app did not apply my coupon at checkout.",
        "Waited 25 minutes at the counter, staff were not attentive.",
        "Second time the {item} came with less quantity. Not happy.",
        "Overpriced {item}, not worth it.",
        "The {item} was bland and oily today.",
    ],
}

TANGLISH = {
    "positive": [
        "{item} semma taste, packing um neat ah irundhuchu",
        "Saapadu romba nalla irundhuchu, delivery time ku vandhuduchu",
        "{item} vera level! Kandippa thirumba order panuven",
        "Staff romba friendly ah pesunanga, {item} super",
        "Filter coffee sema, {item} um nalla irundhuchu",
    ],
    "neutral": [
        "{item} paravaillai, but price konjam adhigam",
        "Taste ok than, delivery konjam late",
        "{item} average ah irundhuchu",
    ],
    "negative": [
        "{item} la quantity romba kammi, worth illa",
        "Delivery 45 mins late, saapadu aaripochu",
        "Bill la extra charge pottanga, kekkave illa",
        "Parcel la sambar leak aayiduchu, bag full ah oothiduchu",
        "App la coupon apply aagala, rendu thadava try panen",
        "Counter la staff romba slow, 20 mins wait panna vechanga",
    ],
}

TAMIL = {
    "positive": [
        "{item} மிகவும் சுவையாக இருந்தது. மீண்டும் ஆர்டர் செய்வேன்.",
        "சாப்பாடு நன்றாக இருந்தது, டெலிவரி நேரத்திற்கு வந்தது.",
        "{item} அருமை! பார்சல் சுத்தமாக கட்டப்பட்டிருந்தது.",
        "ஊழியர்கள் மிகவும் அன்பாக நடந்துகொண்டார்கள். {item} சூப்பர்.",
    ],
    "neutral": [
        "{item} சுமாராக இருந்தது. விலை கொஞ்சம் அதிகம்.",
        "சாப்பாடு பரவாயில்லை, ஆனால் டெலிவரி கொஞ்சம் தாமதம்.",
    ],
    "negative": [
        "{item} ரொம்ப காரமாக இருந்தது, அளவும் குறைவு.",
        "டெலிவரி 40 நிமிடம் தாமதமாக வந்தது. சாப்பாடு ஆறிப்போயிருந்தது.",
        "பில்லில் கூடுதல் கட்டணம் போட்டிருக்கிறார்கள்.",
        "பார்சலில் சாம்பார் கசிந்துவிட்டது.",
        "ஆப்பில் கூப்பன் வேலை செய்யவில்லை.",
    ],
}

# Clearly urgent reviews planted in the data (plus R-1042 from the brief).
HIGH_URGENCY = [
    ("Swiggy", 1, "Got food poisoning after eating the chicken biryani yesterday. My whole family fell sick."),
    ("Zomato", 1, "Found a cockroach in my parotta. Disgusting!"),
    ("Swiggy", 1, "I ordered mutton biryani and received veg meals. Wrong order, I want a refund."),
    ("Google", 1, "The staff at the counter shouted at me and used abusive words."),
    ("Zomato", 1, "I was charged twice for the same order on the app. Please fix this."),
    ("Swiggy", 1, "Biryani la mudi irundhuchu, romba disgusting. Refund venum"),
    ("Zomato", 1, "Payment rendu thadava debit aayiduchu, unga app la problem"),
    ("Google", 1, "சாப்பாட்டில் முடி இருந்தது. மிகவும் மோசம்."),
]

LANG_TOTALS = {"English": 156, "Tanglish": 48, "Tamil": 36}
SENTIMENT_TOTALS = {"positive": 144, "neutral": 36, "negative": 60}
PLATFORM_WEIGHTS = {"Google": 30, "Zomato": 30, "Swiggy": 30, "Amazon": 10}
RATINGS = {"positive": [4, 5, 5], "neutral": [3, 3, 4], "negative": [1, 2, 2, 3]}


def build_rows(rng: random.Random) -> list[tuple]:
    langs = dict(LANG_TOTALS)
    sents = dict(SENTIMENT_TOTALS)
    # Brief rows: EN pos, EN neg, Tanglish neg. Planted urgent: 5 EN, 2 Tanglish, 1 Tamil, all negative.
    langs["English"] -= 2 + 5
    langs["Tanglish"] -= 1 + 2
    langs["Tamil"] -= 1
    sents["positive"] -= 1
    sents["negative"] -= 2 + len(HIGH_URGENCY)

    lang_slots = [lang for lang, n in langs.items() for _ in range(n)]
    sent_slots = [s for s, n in sents.items() for _ in range(n)]
    rng.shuffle(lang_slots)
    rng.shuffle(sent_slots)

    platforms, weights = zip(*PLATFORM_WEIGHTS.items())
    rows = []
    for lang, sentiment in zip(lang_slots, sent_slots):
        if lang == "English":
            text = rng.choice(EN[sentiment]).format(item=rng.choice(ITEMS_EN))
            if sentiment == "positive":
                text = text[0].upper() + text[1:]
        elif lang == "Tanglish":
            text = rng.choice(TANGLISH[sentiment]).format(item=rng.choice(ITEMS_EN).title())
        else:
            text = rng.choice(TAMIL[sentiment]).format(item=rng.choice(ITEMS_TA))
        rows.append((rng.choices(platforms, weights)[0], rng.choice(RATINGS[sentiment]), text))

    rows += HIGH_URGENCY
    rng.shuffle(rows)
    return rows


def main() -> None:
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    header = ["review_id", "date", "platform", "rating", "review_text"]

    with open(DATA / "reviews_week40.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(BRIEF_ROWS)

    out = []
    for n, (platform, rating, text) in enumerate(build_rows(rng)):
        day = WEEK_START + timedelta(days=rng.randrange(7))
        out.append((f"R-{1100 + n}", day.isoformat(), platform, rating, text))
    out += BRIEF_ROWS
    out.sort(key=lambda r: (r[1], r[0]))

    # Junk rows to prove validation: empty text and a duplicate ID.
    out.append(("R-9001", "2026-10-02", "Google", 4, ""))
    out.append(("R-1041", "2026-10-05", "Zomato", 3, "Duplicate entry exported twice by mistake."))

    with open(DATA / "reviews_sample_240.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(out)

    print(f"wrote {len(out)} rows ({len(out) - 2} valid) to {DATA / 'reviews_sample_240.csv'}")


if __name__ == "__main__":
    main()
