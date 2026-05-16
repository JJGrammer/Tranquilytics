# Tranquilytics — Mathematics, Probability, and Algorithms

Reference for formulas and logic used in preview/report generation.  
**Source of truth:** Python modules under `backend/app/services/` (cited below).  
**UI copy:** `frontend/src/analysisExplanations.ts` should stay aligned when thresholds change.

This document describes **modeling and policy math**, not HTTP routes or deployment.

---

## 1. Notation

| Symbol | Meaning |
|--------|---------|
| $t$ | Index of a trading day in the OHLC history (chronological). |
| $P_t$ | Adjusted **close** price on day $t$ (`close` in the feature frame). |
| $h$ | Forward **horizon** in trading days: **5** (short) or **30** (long) in production preview/report. |
| $\mathbf{x}_t$ | Vector of **technical features** on day $t$ (10 columns; see §3). |
| $y_t$ | Binary **label**: 1 if forward return over $h$ days is positive, else 0 (see §4). |
| $P_{\text{tech}}$ | Technical **probability of "up"** from logistic regression (`fit_predict_prob_up`). |
| $P_{\text{sent}}$ | Headline **bullish-aligned probability** in $[0,1]$ from VADER pooling. |
| $p$ | **Blended** probability passed to the tone policy (`prob_up` in `decide`). |
| $\mu$ | **Sentiment-nudged expected fractional return** over the horizon (`expected_return` in `decide`). |
| $\sigma$ | **Daily return volatility** estimate (`volatility` in `decide`; not annualized). |
| $c$ | **Confidence** shown on the UI meter (`AdviceDecision.confidence`). |

**`clip(x, a, b)`** means $\min(b, \max(a, x))$.

---

## 2. End-to-end pipeline (per symbol, per horizon)

For each lookup (`ReportService.preview` / `generate`):

1. Fetch ~**1 year** daily OHLC (+ headlines; RSS optional in `screen_mode`).
2. **`compute_technical_features`** → feature table.
3. **`make_horizon_labels`** → $y_t$ for $h \in \{5, 30\}$.
4. **`fit_predict_prob_up`** → $P_{\text{tech}}$ (short and long separately).
5. **`estimate_expected_return`**, **`estimate_volatility`** → $r_{\text{tech}}$, $\sigma$ (shared vol for both horizons; return uses respective $h$).
6. **`analyze_dual_horizon_sentiment`** → $P_{\text{sent}}$, labels, counts (short vs long headline sets).
7. **`blend_probability`**, **`nudge_expected_return`** → $p$, $\mu$ per horizon.
8. **`decide(p, μ, σ)`** → tone + $c$.
9. **`risk_level_from_volatility(σ)`** → Low / Moderate / High.

**UI confidence** is **only** $c$ from step 8, not $P_{\text{tech}}$ alone.

---

## 3. Technical features

**Module:** `backend/app/services/features.py` — `compute_technical_features`.

Inputs: Yahoo-style history with `Close`, `Volume`, and `Date` or `Datetime`.

### 3.1 Returns

$$
r_{1d,t} = \frac{P_t}{P_{t-1}} - 1, \quad
r_{5d,t} = \frac{P_t}{P_{t-5}} - 1, \quad
r_{10d,t} = \frac{P_t}{P_{t-10}} - 1
$$

(Code: `ret_1d`, `ret_5d`, `ret_10d` via `pct_change`.)

### 3.2 Moving-average ratios

$$
\text{MA}_{k,t} = \frac{1}{k}\sum_{i=0}^{k-1} P_{t-i}, \quad
\text{ma\_ratio}_{5/20,t} = \frac{\text{MA}_{5,t}}{\text{MA}_{20,t}} - 1, \quad
\text{ma\_ratio}_{10/20,t} = \frac{\text{MA}_{10,t}}{\text{MA}_{20,t}} - 1
$$

### 3.3 Rolling volatility of daily returns

$$
\text{vol}_{k,t} = \mathrm{std}\bigl(r_{1d,t-k+1}, \ldots, r_{1d,t}\bigr)
$$

for $k \in \{5, 10, 20\}$ (pandas rolling std).

### 3.4 RSI(14)

Let $\Delta_t = P_t - P_{t-1}$, $u_t = \max(\Delta_t, 0)$, $d_t = \max(-\Delta_t, 0)$.

$$
\overline{u}_t = \mathrm{mean}(u_{t-13..t}), \quad
\overline{d}_t = \mathrm{mean}(d_{t-13..t}), \quad
RS_t = \frac{\overline{u}_t}{\overline{d}_t + 10^{-12}}
$$

$$
RSI_t = 100 - \frac{100}{1 + RS_t}
$$

### 3.5 Volume change

$$
\text{volchg}_{1d,t} = \frac{V_t}{V_{t-1}} - 1
$$

(with $\pm\infty$ replaced by NaN).

### 3.6 Feature vector for ML

$$
\mathbf{x}_t = \bigl(
r_{1d}, r_{5d}, r_{10d},
\text{ma\_ratio}_{5/20}, \text{ma\_ratio}_{10/20},
\text{vol}_5, \text{vol}_{10}, \text{vol}_{20},
RSI, \text{volchg}_{1d}
\bigr)^\top
$$

Rows with NaN in any column are dropped before training/prediction.

---

## 4. Supervised labels

**Module:** `features.py` — `make_horizon_labels(df, horizon_days, buffer_return=0.0)`.

Forward return from $t$ over $h$ sessions:

$$
R_{t,h} = \frac{P_{t+h}}{P_t} - 1
$$

$$
y_t = \begin{cases}
1 & \text{if } R_{t,h} > \text{buffer\_return} \\
0 & \text{otherwise}
\end{cases}
$$

Default **`buffer_return = 0`**: strictly positive forward return ⇒ class 1.  
Trailing rows without $P_{t+h}$ yield NaN labels and are excluded after `dropna` on features.

---

## 5. Technical probability — logistic regression

**Module:** `backend/app/services/ml.py` — `fit_predict_prob_up`.

### 5.1 Fallback (no fit)

If fewer than **80** usable rows or only one class in $y$:

$$
P_{\text{tech}} = \mathrm{clip}\bigl(\bar{y},\, 0.05,\, 0.95\bigr), \quad
\bar{y} = \frac{1}{n}\sum_t y_t
$$

If no labels: $\bar{y}$ defaults to **0.5** before clipping.

### 5.2 StandardScaler

For each feature index $j \in \{1,\ldots,10\}$, using training column statistics $\mu_j$, $s_j$:

$$
z_{j} = \frac{x_{j} - \mu_j}{s_j}
$$

- $x_j$: raw feature value on a given day.  
- $\mu_j$: mean of feature $j$ over training rows.  
- $s_j$: standard deviation of feature $j$ over training rows.  
- $z_j$: scaled input to logistic regression.

### 5.3 Logistic regression

$$
P(y=1 \mid \mathbf{z}) = \sigma(\mathbf{w}^\top \mathbf{z} + b)
= \frac{1}{1 + \exp\bigl(-(\mathbf{w}^\top \mathbf{z} + b)\bigr)}
$$

- $\mathbf{w}, b$: learned by minimizing log loss on historical $(\mathbf{z}_t, y_t)$.  
- **`class_weight="balanced"`**: sklearn reweights classes inversely to frequency.  
- **`max_iter=2000`**: solver iteration cap.

**Training:** fit on all valid historical rows for **this ticker** and **this $h$**.  
**Prediction:** only the **latest** row $\mathbf{z}_{\text{last}}$ is scored.

### 5.4 Probability calibration (preferred path)

**`CalibratedClassifierCV`** with **`method="isotonic"`** and **`TimeSeriesSplit(n_splits=5)`**:

- CV folds are **time-ordered** (train on past, calibrate on future chunks).  
- Isotonic regression learns a monotone map $f$ so out-of-fold probabilities are better calibrated.  
- Final score: $P_{\text{tech}} = f\bigl(\sigma(\mathbf{w}^\top \mathbf{z}_{\text{last}} + b)\bigr)$ (conceptually; sklearn applies the fitted calibrator).

If calibration raises **`ValueError`** (e.g. single-class fold), fit **un-calibrated** pipeline on full $X, y$ and use raw `predict_proba`.

### 5.5 Output clip

$$
P_{\text{tech}} \leftarrow \mathrm{clip}(P_{\text{tech}},\, 0.01,\, 0.99)
$$

---

## 6. Heuristic expected return and volatility

**Module:** `ml.py`.

### 6.1 Expected return (technical leg)

Let $\mathcal{R}_{20}$ be the last up to **20** non-NaN daily returns $r_{1d}$.

$$
\bar{r}_{20} = \mathrm{mean}(\mathcal{R}_{20}), \quad
r_{\text{tech}} = \mathrm{clip}\bigl(\bar{r}_{20} \cdot h,\,-0.25,\,0.25\bigr)
$$

- $\bar{r}_{20}$: recent average **daily** fractional return.  
- $h$: horizon days (5 or 30).  
- **±0.25**: cap on fractional move (25 percentage points as a fraction).

### 6.2 Daily volatility

$$
\sigma = \mathrm{std}(\mathcal{R}_{20})
$$

Same window as $\bar{r}_{20}$; **not** annualized. Used for risk bucket and policy buffers.

---

## 7. Risk level from volatility

**Module:** `backend/app/services/risk.py` — `risk_level_from_volatility`.

$$
\text{risk} =
\begin{cases}
\text{Low} & \sigma < 0.012 \\
\text{Moderate} & \sigma < 0.028 \\
\text{High} & \text{otherwise}
\end{cases}
$$

If $\sigma$ is missing: **Moderate**.

---

## 8. Headline sentiment (VADER + pooling)

**Module:** `backend/app/services/sentiment.py`.  
**Library:** VADER `SentimentIntensityAnalyzer.polarity_scores(title)` — **lexicon unchanged**.

Per headline $i$ with scores `compound`, `pos`, `neg`:

$$
d_i = \frac{\text{compound}_i + (\text{pos}_i - \text{neg}_i)}{2}
$$

Aggregate over headline set $\mathcal{H}$:

$$
\bar{c} = \frac{1}{|\mathcal{H}|}\sum_{i\in\mathcal{H}} \text{compound}_i, \quad
\bar{d} = \frac{1}{|\mathcal{H}|}\sum_{i\in\mathcal{H}} d_i
$$

$$
\text{blended} = \frac{\bar{c} + \bar{d}}{2}
$$

**Display label** (`LABEL_THRESHOLD = 0.028`):

$$
\text{label} =
\begin{cases}
\text{Bullish} & \text{blended} \ge 0.028 \\
\text{Bearish} & \text{blended} \le -0.028 \\
\text{Neutral} & \text{otherwise}
\end{cases}
$$

**Synthesizer input:**

$$
P_{\text{sent}} = \mathrm{clip}\left(\frac{\text{blended} + 1}{2},\, 0.02,\, 0.98\right)
$$

Empty headline set: $P_{\text{sent}} = 0.5$, label Neutral, count 0.

### 8.1 Dual horizons (`analyze_dual_horizon_sentiment`)

| Layer | Headline selection |
|--------|-------------------|
| **Short** | Titles with `published` in last **72h**; if fewer than **2**, fallback to **newest** up to **8** undated/dated pool. |
| **Long** | **Oldest dated** headline as narrative anchor; if none, **longest title**; if still empty, pool up to **10** titles. |

Yahoo and Google RSS lists are merged elsewhere (`dedupe_news`); VADER runs on the selected subsets.

---

## 9. Synthesizer — blend and return nudge

**Module:** `backend/app/services/synthesizer.py`.

### 9.1 Weights

| Horizon | $w_t$ (technical) | $w_s$ (sentiment) |
|---------|---------------------|---------------------|
| Short | 0.56 | 0.44 |
| Long | 0.70 | 0.30 |

Weights are clamped to $[0,1]$ and renormalized: $w_t' = w_t/(w_t+w_s)$, $w_s' = w_s/(w_t+w_s)$.

### 9.2 Blended probability

$$
p = w_t' \, P_{\text{tech}} + w_s' \, P_{\text{sent}}
$$

This $p$ is **`prob_up`** in `decide`.

### 9.3 Nudged expected return

Let $\text{mean\_compound}$ be the mean VADER compound over the headlines used for that horizon layer.

$$
\mu = \mathrm{clip}\bigl(r_{\text{tech}} + 0.02 \cdot \text{mean\_compound},\,-0.25,\,0.25\bigr)
$$

---

## 10. Tone policy and confidence

**Module:** `backend/app/services/advice_policy.py` — `decide(prob_up, expected_return, volatility)`.

Inputs: $p =$ `prob_up`, $\mu =$ `expected_return`, $\sigma =$ `volatility`.

### 10.1 Buffers

$$
\text{buffer} = \mathrm{clip}(0.75 \cdot \sigma,\, 0.005,\, 0.03)
$$

$$
\text{edge\_buffer} = 1.35 \times \text{buffer}
$$

Higher $\sigma$ ⇒ wider thresholds (less aggressive strong signals on noisy names).

### 10.2 Rules (first match wins)

**Safer Buy** — if $p \ge 0.73$ and $\mu \ge \text{edge\_buffer}$:

$$
c = \min\left(1,\ \max\left(p,\ 0.5 + \frac{\mu}{\max(\text{buffer}, 10^{-6})} \cdot 0.05\right)\right)
$$

**Sell Soon** — if $p \le 0.27$ and $\mu \le -\text{edge\_buffer}$:

$$
c = \min\left(1,\ \max\left(1-p,\ 0.5 + \frac{-\mu}{\max(\text{buffer}, 10^{-6})} \cdot 0.05\right)\right)
$$

**Buy** — if $p \ge 0.58$ and $\mu \ge \text{buffer}$:

$$
c = p
$$

**Sell** — if $p \le 0.42$ and $\mu \le -\text{buffer}$:

$$
c = 1 - p
$$

**Neutral** — otherwise:

$$
c = \mathrm{clip}\bigl(1 - 2|p - 0.5|,\, 0,\, 1\bigr)
$$

Maximum $c$ at $p = 0.5$; $c = 0$ at $p \in \{0, 1\}$.

---

## 11. Display-only market move

**Module:** `report_service._latest_session_change_pct`.

$$
\text{change\_pct\_day} \approx \left(\frac{C_{\text{last}}}{C_{\text{prev}}} - 1\right) \times 100
$$

$C_{\text{last}}$, $C_{\text{prev}}$: last two **Close** values in the fetched history.  
Not an input to `decide`; descriptive UI field only.

---

## 12. Daily picks screening (policy reuse)

**Module:** `daily_picks.py`.

Uses the same preview pipeline; a symbol is listed if (for chosen focus):

- **Short focus:** short tone is **Safer Buy**, or **Buy** with risk **Low**.  
- **Long focus:** long tone is **Safer Buy**, or **Buy** with risk **Low**.

`screen_mode` previews skip Google RSS and company blurb; $P_{\text{sent}}$ may differ slightly from full dashboard preview.

---

## 13. Constants quick reference

| Constant | Value | Location |
|----------|-------|----------|
| Short horizon $h$ | 5 days | `report_service` |
| Long horizon $h$ | 30 days | `report_service` |
| Min rows to fit logistic | 80 | `ml.py` |
| $P_{\text{tech}}$ clip | [0.01, 0.99] | `ml.py` |
| Baseline rate clip | [0.05, 0.95] | `ml.py` |
| Return clip | ±0.25 | `ml.py`, `synthesizer.py` |
| Sentiment label threshold | ±0.028 | `sentiment.py` |
| $P_{\text{sent}}$ clip | [0.02, 0.98] | `sentiment.py` |
| Short recency window | 72 hours | `sentiment.py` |
| Short blend weights | 0.56 / 0.44 | `synthesizer.py` |
| Long blend weights | 0.70 / 0.30 | `synthesizer.py` |
| Sentiment return nudge | 0.02 × mean_compound | `synthesizer.py` |
| Vol → buffer scale | 0.75 | `advice_policy.py` |
| Buffer clip | [0.005, 0.03] | `advice_policy.py` |
| edge_buffer factor | 1.35 | `advice_policy.py` |
| Safer Buy $p$, $\mu$ | ≥ 0.73, ≥ edge_buffer | `advice_policy.py` |
| Sell Soon $p$, $\mu$ | ≤ 0.27, ≤ −edge_buffer | `advice_policy.py` |
| Buy $p$, $\mu$ | ≥ 0.58, ≥ buffer | `advice_policy.py` |
| Sell $p$, $\mu$ | ≤ 0.42, ≤ −buffer | `advice_policy.py` |
| Risk Low / Moderate $\sigma$ | < 0.012 / < 0.028 | `risk.py` |
| TimeSeriesSplit folds | 5 | `ml.py` |
| Calibration method | isotonic | `ml.py` |

---

## 14. Source file map

| Topic | File |
|-------|------|
| Features & labels | `backend/app/services/features.py` |
| Logistic regression, heuristics | `backend/app/services/ml.py` |
| Sentiment / VADER pooling | `backend/app/services/sentiment.py` |
| Blend & nudge | `backend/app/services/synthesizer.py` |
| Tones & confidence | `backend/app/services/advice_policy.py` |
| Risk bucket | `backend/app/services/risk.py` |
| Orchestration | `backend/app/services/report_service.py` |
| Headline merge / RSS | `backend/app/services/google_news_feed.py` |
| UI formula copy | `frontend/src/analysisExplanations.ts` |

---

## 15. Limitations (read before citing in papers or reports)

- Market data and news are **unofficial** (Yahoo via yfinance, Google News RSS).  
- Models are **re-fit per request** per ticker (no persistent cross-sectional model).  
- **Confidence** $c$ is a **policy display score**, not calibrated forecast accuracy or trading edge.  
- Logistic labels use **in-sample** history on the same symbol; **TimeSeriesSplit** is used for calibration folds, not reported hold-out performance in the API.  
- Headline sentiment uses **titles only**, not full article bodies.

---

*Last aligned with repository logic in `backend/app/services/` and `frontend/src/analysisExplanations.ts`.*
