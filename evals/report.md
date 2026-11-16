# ReviewLens evaluation report

- Date: 2026-11-16 14:15 UTC
- Model: `gpt-4o-mini`, prompt version `v3`; reply grader `gpt-4o` (sentence count checked in code)
- Golden set: 80 reviews (50 English, 15 Tanglish, 15 Tamil)
- Service calls: 104 (retries 4), tokens in/out 177,071/7,716
- Estimated cost: $0.0312, time 56.5 s
- Rows marked needs_review: 0

Note: R-1041, R-1042 and R-1043 from the course brief are also few-shot examples in the prompt.

## Scores

| Metric | Score | Target | Result | Change vs previous |
|---|---|---|---|---|
| Sentiment accuracy | 100.0% | 90.0% | PASS | = |
| Category accuracy | 96.2% | 85.0% | PASS | = |
| High-urgency recall | 100.0% | 95.0% | PASS | = |
| High-urgency precision | 100.0% |  |  | = |
| Urgency accuracy (3-way) | 98.8% |  |  | = |
| Language accuracy | 98.8% |  |  | = |
| Injection cases resisted (3/3) | 100.0% | 100.0% | PASS | = |
| Reply rubric pass rate (20 sampled) | 95.0% | 90.0% | PASS | +35.0% |

## Sentiment confusion matrix

| expected \ predicted | positive | neutral | negative |
|---|---|---|---|
| positive | 27 | 0 | 0 |
| neutral | 0 | 11 | 0 |
| negative | 0 | 0 | 42 |

## Category confusion matrix

| expected \ predicted | food_quality | delivery | price | staff | packaging | app |
|---|---|---|---|---|---|---|
| food_quality | 29 | 1 | 2 | 0 | 0 | 0 |
| delivery | 0 | 17 | 0 | 0 | 0 | 0 |
| price | 0 | 0 | 8 | 0 | 0 | 0 |
| staff | 0 | 0 | 0 | 9 | 0 | 0 |
| packaging | 0 | 0 | 0 | 0 | 6 | 0 |
| app | 0 | 0 | 0 | 0 | 0 | 6 |

## Language confusion matrix

| expected \ predicted | English | Tamil | Tanglish |
|---|---|---|---|
| English | 50 | 0 | 0 |
| Tamil | 0 | 15 | 0 |
| Tanglish | 1 | 0 | 14 |
| Other | 0 | 0 | 0 |

## Misses

| Review | Field | Expected | Got | Text |
|---|---|---|---|---|
| G-017 | category | food_quality | price | Portion size of the parotta has become very small for the price. |
| G-035 | urgency | medium | low | The pickle jar lid was loose and the label was torn. |
| T-005 | category | food_quality | delivery | Food was great, delivery on time, very happy with the order! |
| TG-007 | language | Tanglish | English | Taste ok than, but delivery 15 mins late |
| TG-008 | category | food_quality | price | Parotta quantity romba kammi, worth illa |

## Reply rubric failures

- G-029: The reply admits legal liability by stating 'Your safety is our priority.'

## Verdict

All targets met.
