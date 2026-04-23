# Recession Model Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the existing recession-model module in two ordered phases. **Phase 2B** is a pure refactor that extracts a single feature-engineering source of truth and decomposes the monolithic `model.py` training loop while preserving byte-for-byte behavior. **Phase 2A** then layers methodology improvements (walk-forward backtest harness, ensemble-level probability calibration, explicit feature lag dating) on top of the refactored skeleton, and reconciles the two recession probabilities surfaced in the app (the ML ensemble becomes the canonical readout; the scorecard's signal-weighted estimate is renamed and demoted to a secondary "live signal" indicator).

**Architecture:**
- Single source of truth for feature engineering: a new `modules/recession_model/features.py` module exposes `engineer_features(df)`, `FEATURE_SERIES`, `HORIZONS`, `START_DATE`, `CORE_REQUIRED`, `get_feature_columns(df)`. Both training (`data_builder.build_dataset`) and live prediction (`data_builder.build_current_features`) call this exact function — no parallel implementations.
- Decomposed training pipeline: `model.py` becomes a thin orchestrator (~250 lines). Per-model fit/eval logic moves to `modules/recession_model/training.py`. Persistence (joblib + metadata.json) moves to `modules/recession_model/persistence.py` (incl. legacy loader). A new `modules/recession_model/calibration.py` houses the calibration harness (Phase 2A).
- Walk-forward backtest harness: `modules/recession_model/backtest.py` produces honest out-of-sample metrics and per-fold predictions used both as the calibration training set and as the displayed performance numbers.
- Ensemble-level calibration: after the AUC-weighted average is computed, a single `IsotonicRegression` (or `LogisticRegression` Platt scaler — chosen by Brier score on the held-out walk-forward predictions) maps raw ensemble probabilities → calibrated probabilities. Per-horizon calibrators are saved alongside the models.
- Feature lag dating: each FRED series gets an explicit `release_lag_months` field in config; `build_current_features` shifts each series's "as-of" date so the live snapshot matches what would have been observable at training time for that calendar month.
- Recession probability reconciliation: ML ensemble = canonical "Recession Probability" surfaced in the dashboard, risk scorecard, and `/recession-model` page. The scorecard's existing signal-weighted heuristic is renamed to "Live Signal Recession Estimate" and labeled as a secondary, real-time read-through indicator. No data is removed; only labels and prominence change.

**Tech Stack:** Python 3, pandas, numpy, scikit-learn (LogReg, KNN, RandomForest, GradientBoosting, IsotonicRegression, calibration), joblib, FastAPI, pytest, React 18 + TypeScript + Tailwind CSS.

**Baseline:** Commit `18301dc` on branch `claude/recession-model-rework` carved out from `main` HEAD (`bc5aa9b`). All work in this plan lands on top of that baseline.

**Out of scope (explicitly deferred):**
- Phase 2C — frontend decomposition of `RecessionModel.tsx` (843 lines, 11 useState calls, embedded subcomponents).
- Phase 2D — train pipeline robustness (FRED retry/backoff hardening, partial-failure recovery, training-progress streaming).

---

## File Structure

### New backend files
- `modules/recession_model/features.py` — single source of truth for FRED config + `engineer_features()`
- `modules/recession_model/training.py` — per-model fit/eval extracted from `model.py`
- `modules/recession_model/persistence.py` — save/load + legacy loader extracted from `model.py`
- `modules/recession_model/backtest.py` — walk-forward harness (Phase 2A)
- `modules/recession_model/calibration.py` — ensemble-level Platt/isotonic calibrator (Phase 2A)
- `tests/test_recession_features.py` — engineer_features golden snapshot
- `tests/test_recession_training.py` — single-model fit returns expected metric keys
- `tests/test_recession_persistence.py` — save→load round trip
- `tests/test_recession_backtest.py` — walk-forward fold generation + leakage guard (Phase 2A)
- `tests/test_recession_calibration.py` — calibration improves Brier on synthetic miscalibrated data (Phase 2A)
- `tests/test_recession_lag.py` — release_lag_months shifts as-of dates correctly (Phase 2A)

### Modified files
- `modules/recession_model/__init__.py` — re-export `RecessionModel` from new module layout
- `modules/recession_model/data_builder.py` — drop in-class `_engineer_features` + `_get_feature_columns`; delegate to `features.py`
- `modules/recession_model/model.py` — thin orchestrator; delegates fit→`training.py`, save/load→`persistence.py`, calibration→`calibration.py`
- `modules/recession_model/predictor.py` — apply ensemble calibrators on top of raw predictions; surface backtest metrics in `model_info`
- `modules/risk_scorecard/scorecard.py` — rename signal-weighted recession estimate field/label
- `frontend/src/pages/RecessionModel.tsx` — show backtest metrics alongside in-sample metrics; add calibration reliability summary
- `frontend/src/pages/RiskScorecard.tsx` — rename pillar/sub-readout label to "Live Signal Recession Estimate"
- `frontend/src/components/IntelligencePanel.tsx` — if it surfaces either probability, point it at the ML ensemble as canonical
- `requirements.txt` — already has `scikit-learn>=1.4.0` from baseline

### Untouched (deferred)
- `frontend/src/pages/RecessionModel.tsx` decomposition into subcomponents
- `data_builder.build_dataset` retry/backoff and progress streaming

---

# PHASE 2B — Refactor (preserve behavior)

**Goal:** Land a structurally-clean skeleton that produces byte-identical training output and byte-identical live predictions. No methodology changes. Every refactor task ends with a verification step that diffs the new metadata.json or prediction output against a checkpoint captured at the start.

## Task B0: Capture behavioral baseline

**Files:**
- Create (uncommitted, not in repo): `tmp/baseline_metadata.json`
- Create (uncommitted, not in repo): `tmp/baseline_prediction.json`

- [ ] **Step 1: Train baseline once and snapshot artifacts**

Run `POST /api/recession/train` against the baseline (commit `18301dc`). Wait for completion via `/api/recession/training-status`.

Copy `data/recession_model/metadata.json` → `tmp/baseline_metadata.json`.
Copy the JSON response of `GET /api/recession/probability` → `tmp/baseline_prediction.json`.

These two files are the behavioral oracle for every Phase 2B task. Add `tmp/` to `.gitignore` if not already excluded.

- [ ] **Step 2: Capture deterministic feature engineering snapshot**

Write a one-off script `scripts/snapshot_features.py` that:
1. Calls `RecessionDataBuilder().build_dataset()`
2. Saves `df.tail(120).to_csv('tmp/baseline_features.csv')`

Run it once. Discard the script after Phase 2B completes.

This guards against silent feature-engineering drift during the refactor.

## Task B1: Extract `features.py` (single source of truth)

**Files:**
- Create: `modules/recession_model/features.py`
- Modify: `modules/recession_model/data_builder.py`

- [ ] **Step 1: Move config constants and `_engineer_features` body into `features.py`**

Move verbatim from `data_builder.py` to `features.py`:
- `TIER1_SERIES`, `TIER2_SERIES`, `TIER3_SERIES`, `TIER4_SERIES`
- `FEATURE_SERIES`, `RECESSION_SERIES`, `START_DATE`, `HORIZONS`, `CORE_REQUIRED`
- The body of `RecessionDataBuilder._engineer_features` → module-level `engineer_features(df: pd.DataFrame) -> pd.DataFrame`
- The body of `RecessionDataBuilder._get_feature_columns` → module-level `get_feature_columns(df: pd.DataFrame) -> List[str]`

- [ ] **Step 2: Update `data_builder.py` to import from `features.py`**

Replace the in-class methods with delegating wrappers (or remove and update callers directly):
```python
from .features import (
    FEATURE_SERIES, RECESSION_SERIES, START_DATE, HORIZONS,
    CORE_REQUIRED, engineer_features, get_feature_columns,
)
# In build_dataset / build_current_features:
df = engineer_features(df)
```

Both `build_dataset` AND `build_current_features` must call the same `engineer_features` function. No parallel feature logic anywhere.

- [ ] **Step 3: Update `model.py` import**

`model.py` currently imports `HORIZONS` from `.data_builder` — change it to `from .features import HORIZONS`. Keep `from .data_builder import RecessionDataBuilder` for the dataset builder.

- [ ] **Step 4: Verification — feature engineering byte-identical**

Re-run `scripts/snapshot_features.py` (rename output `tmp/refactored_features.csv`).

Run `diff tmp/baseline_features.csv tmp/refactored_features.csv`. Must be empty.

If non-empty, the move was not faithful. Fix and re-verify before moving on.

## Task B2: Extract `training.py` (per-model fit/eval)

**Files:**
- Create: `modules/recession_model/training.py`
- Modify: `modules/recession_model/model.py`

- [ ] **Step 1: Move helpers into `training.py`**

Move from `model.py` to `training.py` as module-level functions:
- `_create_model(model_type)` → `create_model(model_type)`
- `RecessionModel._train_single_model` → `train_single_model(model_type, X_train, y_train, X_test, y_test) -> Tuple[Dict, Any, float]` (returns metrics, fitted_model, optimal_threshold)
- `RecessionModel._find_optimal_threshold` → `find_optimal_threshold(y_true, y_prob)`
- `RecessionModel._extract_tree_rules` → `extract_tree_rules(rf_model, feature_names) -> List[Dict]`

Make these pure functions: no dependency on `RecessionModel` instance state. `train_single_model` returns the optimal threshold instead of mutating `self.optimal_thresholds`.

Move `MODEL_TYPES` and `HORIZONS_LABELS` constants to `training.py` too.

- [ ] **Step 2: Update `model.py` `train()` method to call functions**

`RecessionModel.train()` now orchestrates:
```python
from .training import (
    MODEL_TYPES, create_model, train_single_model,
    find_optimal_threshold, extract_tree_rules,
)
# Inside the per-horizon loop:
metrics, fitted_model, threshold = train_single_model(
    model_type, X_train, y_train, X_test, y_test,
)
self.metrics[horizon][model_type] = metrics
self.models[horizon][model_type] = fitted_model
self.optimal_thresholds[horizon][model_type] = threshold
```

The full-data refit loop also calls `create_model(model_type)` from `training.py`.

- [ ] **Step 3: Verification — metadata.json identical**

Re-train (`POST /api/recession/train`). Diff the new `data/recession_model/metadata.json` against `tmp/baseline_metadata.json`. Differences must be limited to the `trained_at` ISO timestamp. Every metric, every weight, every tree rule must match exactly.

If anything else differs, behavior was not preserved. Fix.

## Task B3: Extract `persistence.py` (save/load + legacy)

**Files:**
- Create: `modules/recession_model/persistence.py`
- Modify: `modules/recession_model/model.py`

- [ ] **Step 1: Move `RecessionModel.save`, `load`, `_load_legacy` into `persistence.py`**

Expose:
```python
def save_model(model: 'RecessionModel') -> None: ...
def load_model(model: 'RecessionModel') -> bool: ...  # returns success
def _load_legacy(model: 'RecessionModel') -> bool: ...  # returns success
```

Keep all I/O details (file paths, joblib calls, JSON serialization) inside `persistence.py`. `MODEL_DIR = Path("data/recession_model")` lives here.

- [ ] **Step 2: Slim `model.py`**

```python
from .persistence import save_model, load_model

class RecessionModel:
    # ... __init__, train, predict, predict_history, get_model_info ...

    def save(self):
        save_model(self)

    def load(self) -> bool:
        return load_model(self)
```

- [ ] **Step 3: Verification — load round trip**

Run `RecessionModel().load()` on the artifacts already on disk (from Task B0). Run `predict()` on a fixed feature dict. Diff result against `tmp/baseline_prediction.json["probabilities"]`. Must match to 1 decimal place (the rounding precision in the codebase).

## Task B4: Add unit tests for the refactored modules

**Files:**
- Create: `tests/test_recession_features.py`
- Create: `tests/test_recession_training.py`
- Create: `tests/test_recession_persistence.py`

- [ ] **Step 1: `test_recession_features.py` — golden snapshot**

Build a deterministic synthetic 240-row DataFrame with all `FEATURE_SERIES` columns (e.g. seeded `np.random.RandomState(42)`). Call `engineer_features(df)`. Hash a stable subset of columns (e.g. `unrate_chg3`, `t10y2y_ma3`, `vix_zscore`, `payems_chg6_ma3`) — the exact column subset is recorded in the test. The hash is asserted equal to a checked-in expected value.

This protects against silent behavior drift in the feature engineering function for the rest of the rework.

- [ ] **Step 2: `test_recession_training.py` — single-model fit contract**

For each `model_type in MODEL_TYPES`, on a synthetic 200-row classification problem:
- `train_single_model(...)` returns `(metrics, model, threshold)`.
- `metrics` contains keys: `accuracy`, `precision`, `recall`, `f1`, `auc_roc`, `optimal_threshold`, `confusion_matrix`.
- `model` has either `predict_proba` or `decision_function`.
- `threshold` is in `[0, 1]`.

- [ ] **Step 3: `test_recession_persistence.py` — round trip**

Train a 1-horizon mini-model on synthetic data, call `save_model`, instantiate a fresh `RecessionModel`, call `load_model`, assert `feature_names`, `metrics`, `ensemble_weights`, `optimal_thresholds` all match the original. Then call `predict()` on the same inputs and assert outputs are identical.

- [ ] **Step 4: Run all tests**

```
pytest tests/test_recession_features.py tests/test_recession_training.py tests/test_recession_persistence.py -v
```
All must pass.

## Task B5: Phase 2B size budget verification

- [ ] **Step 1: Confirm files are under target sizes**

Run `wc -l` on:
- `modules/recession_model/features.py` (target: < 600 lines — feature engineering body is large)
- `modules/recession_model/data_builder.py` (target: < 250 lines after extraction)
- `modules/recession_model/model.py` (target: < 280 lines after `training.py` + `persistence.py` extractions)
- `modules/recession_model/training.py` (target: < 250 lines)
- `modules/recession_model/persistence.py` (target: < 250 lines)

Document actual line counts in the commit message.

- [ ] **Step 2: Final regression check**

Re-train end-to-end one more time. Diff `metadata.json` against `tmp/baseline_metadata.json`. Diff `GET /api/recession/probability` response against `tmp/baseline_prediction.json`. Both must match (modulo `trained_at` timestamp).

---

# PHASE 2A — Methodology

**Goal:** Replace in-sample metrics with honest walk-forward backtest numbers, calibrate ensemble probabilities, and date features by FRED release lag instead of calendar month. Reconcile the two on-screen recession probabilities so the ML ensemble is the canonical figure.

## Task A1: Walk-forward backtest harness

**Files:**
- Create: `modules/recession_model/backtest.py`
- Create: `tests/test_recession_backtest.py`
- Modify: `modules/recession_model/model.py`
- Modify: `modules/recession_model/persistence.py`

- [ ] **Step 1: Walk-forward fold generator**

In `backtest.py`:
```python
def walk_forward_folds(
    n_samples: int,
    initial_train_size: int,  # e.g. int(n_samples * 0.5)
    step: int,                # e.g. 12 (months)
    test_size: int,           # e.g. 12 (months)
) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, test_idx) tuples in time order, no overlap."""
```

Time-ordered, expanding window. Test indices are strictly later than train indices in every fold. Asserted by test in step 4.

- [ ] **Step 2: Per-horizon walk-forward run**

```python
def run_walk_forward(
    X: np.ndarray, y: np.ndarray, horizon: int,
    feature_names: List[str],
) -> Dict[str, Any]:
    """
    Returns:
      {
        'oof_probs': np.ndarray of length n_samples (NaN for indices never tested),
        'oof_predictions': np.ndarray (binary at the per-fold optimal threshold),
        'fold_metrics': List[Dict] (one per fold, each with f1/auc/brier),
        'aggregate_metrics': Dict (avg + std of f1, auc, brier across folds),
      }
    """
```

Each fold: refit `StandardScaler` on the fold's training window (no leakage), fit each `MODEL_TYPES` member, compute AUC-weighted ensemble probability for that fold's test window, store. Per-fold optimal threshold computed on a 20% inner validation slice carved off the END of the train window.

- [ ] **Step 3: Wire into `RecessionModel.train()`**

After the existing in-sample training, run `run_walk_forward` once per horizon. Store on the model as `self.walk_forward_metrics[horizon]` and `self.oof_probs[horizon]`. Persist via `persistence.py` into `metadata.json` under new keys `walk_forward_metrics` and (small enough to include) `oof_summary`. Full `oof_probs` array saves to `data/recession_model/oof_probs_{horizon}m.npy`.

- [ ] **Step 4: Tests**

`test_recession_backtest.py`:
- `walk_forward_folds` produces expected number of folds for known sizes; every test index strictly greater than every train index in its fold (leakage guard).
- `run_walk_forward` on synthetic data returns finite `aggregate_metrics`; `oof_probs` has expected NaN/non-NaN pattern.

## Task A2: Ensemble-level calibration

**Files:**
- Create: `modules/recession_model/calibration.py`
- Create: `tests/test_recession_calibration.py`
- Modify: `modules/recession_model/model.py`
- Modify: `modules/recession_model/predictor.py`
- Modify: `modules/recession_model/persistence.py`

- [ ] **Step 1: Calibrator selection by Brier**

In `calibration.py`:
```python
def fit_calibrator(
    raw_probs: np.ndarray, y_true: np.ndarray,
) -> Tuple[Any, str, Dict[str, float]]:
    """
    Fit both Platt (LogisticRegression) and Isotonic on the OOF probs.
    Pick the one with lower Brier score on the same OOF set
    (with a tie-break preferring isotonic).
    Returns (fitted_calibrator, method_name, brier_comparison).
    """

def apply_calibrator(calibrator, raw_probs: np.ndarray) -> np.ndarray:
    """Apply the chosen calibrator. Returns probabilities in [0, 1]."""
```

Use `sklearn.linear_model.LogisticRegression` for Platt and `sklearn.isotonic.IsotonicRegression(out_of_bounds='clip')` for isotonic.

- [ ] **Step 2: Train + persist calibrators**

In `RecessionModel.train()`, after Task A1's walk-forward step, fit one calibrator per horizon on `(oof_probs[horizon], y[horizon])`. Store on `self.calibrators[horizon]` and `self.calibration_method[horizon]`. Persist alongside scalers via joblib at `data/recession_model/calibrator_{horizon}m.joblib`. Add `calibration_method` and `calibration_brier_comparison` to `metadata.json`.

- [ ] **Step 3: Apply at predict time**

In `RecessionModel.predict()` and `RecessionModel.predict_history()`, after computing the AUC-weighted ensemble probability, pass through `apply_calibrator(self.calibrators[horizon], raw)`. Surface BOTH `raw_ensemble` and `calibrated_ensemble` in the returned dict so the frontend can show both. The `signal` / `signal_label` thresholds in `predictor.py` should switch to using the calibrated value.

- [ ] **Step 4: Tests**

`test_recession_calibration.py`:
- On synthetic miscalibrated data (e.g. raw_probs = `np.power(true_p, 2)`, where true_p ∈ [0,1]), `fit_calibrator` followed by `apply_calibrator` produces a Brier score lower than raw.
- Calibrator output is always in `[0, 1]`.

## Task A3: Feature lag dating

**Files:**
- Modify: `modules/recession_model/features.py`
- Modify: `modules/recession_model/data_builder.py`
- Create: `tests/test_recession_lag.py`

- [ ] **Step 1: Add `release_lag_months` to series config**

Convert each tier dict from `{series_id: human_name}` to `{series_id: {"name": ..., "release_lag_months": int}}`. Backfill `release_lag_months` from FRED documentation:
- UNRATE/PAYEMS/ICSA/UMCSENT/AWHMAN: 0 (current-month release)
- INDPRO/HOUST/PERMIT/DGORDER/NEWORDER: 1
- CPIAUCSL/CPILFESL/PPIACO/PCEPILFE: 1
- M1SL/M2SL: 1
- USALOLITONOSTSAM (OECD LEI): 2
- BOGZ1FL072052006Q (quarterly): 3
- All daily yields/spreads/VIX/oil/dollar (DGS10, T10Y2Y, etc.): 0
- NFCI/ANFCI/STLFSI2: 0 (weekly, current)
- W875RX1, TOTALSL, JTSJOL, JTSQUR: 1
- EMRATIO/CIVPART/U6RATE/LNS12300060: 0 (released with UNRATE)
- TEDRATE: 0 (daily, but flag as discontinued in 2022 — leave as-is)

Add a fallback: any series not in the config defaults to `release_lag_months=1`.

- [ ] **Step 2: Apply lag in `build_current_features` only**

In `RecessionDataBuilder.build_current_features`, after the resample step, shift each column's last available value backward by its `release_lag_months`. Concretely:
```python
# For each series, the "as-of" date for live prediction
# is today - release_lag_months. The latest row reflects that.
for sid in monthly:
    lag = SERIES_LAGS.get(sid, 1)
    if lag > 0:
        # Drop the most recent `lag` months of values for this series
        monthly[sid] = monthly[sid].iloc[:-lag] if len(monthly[sid]) > lag else monthly[sid]
```

This ensures live features mirror the as-of state of training-time monthly rows — no peeking at not-yet-released series.

Do NOT modify `build_dataset`. Training already uses end-of-month observation_date alignment via FRED's published dates.

- [ ] **Step 3: Tests**

`test_recession_lag.py`:
- For a series configured with `release_lag_months=2`, after `build_current_features` the latest available value for that series equals the value from 2 months prior in the original raw data.
- For `release_lag_months=0`, the latest value is preserved.
- A series id not in config gets the default lag of 1.

## Task A4: Recession probability reconciliation

**Files:**
- Modify: `modules/risk_scorecard/scorecard.py`
- Modify: `frontend/src/pages/RiskScorecard.tsx`
- Modify: `frontend/src/components/IntelligencePanel.tsx`

- [ ] **Step 1: Backend rename**

In `scorecard.py`, rename the field surfacing the signal-weighted recession estimate from whatever it is currently called (`recession_probability` / `composite_recession_probability` / etc.) to `live_signal_recession_estimate`. Keep the computation unchanged. Bump any keys in the JSON response.

If the scorecard currently labels a pillar "Recession Risk" with a number that is actually the signal-weighted estimate, rename the pillar's display field too. The label string returned to the frontend becomes `"Live Signal Recession Estimate"`.

- [ ] **Step 2: Frontend rename**

In `RiskScorecard.tsx`, find every reference to "Recession Probability" / "Recession Risk" that maps to the renamed field and update both the rendered label and any `aria-label` / tooltip / methodology copy. Add a one-line caption: "Real-time read-through from current signals — see /recession-model for the canonical ML ensemble."

In `IntelligencePanel.tsx`, if any tab references "Recession Probability", repoint it to `GET /api/recession/probability` (the ML ensemble) and label it accordingly.

- [ ] **Step 3: Verification**

Manual: visit `/risk-scorecard` and `/recession-model`. Confirm:
- `/risk-scorecard` shows "Live Signal Recession Estimate" with the existing signal-weighted number.
- `/recession-model` shows "Recession Probability" with the calibrated ML ensemble number.
- The two numbers can differ — that is intentional and explained in the scorecard caption.

## Task A5: Surface backtest + calibration metrics in UI

**Files:**
- Modify: `modules/recession_model/model.py` (`get_model_info`)
- Modify: `frontend/src/pages/RecessionModel.tsx`

- [ ] **Step 1: Expose backtest + calibration in `get_model_info`**

Add to the returned dict:
```python
"walk_forward_metrics": {f"{h}m": self.walk_forward_metrics.get(h, {}) for h in HORIZONS},
"calibration": {
    f"{h}m": {
        "method": self.calibration_method.get(h),
        "brier_raw": ...,        # from Task A2 brier_comparison
        "brier_calibrated": ...,
    } for h in HORIZONS
},
```

- [ ] **Step 2: Render in `RecessionModel.tsx`**

Add a "Out-of-sample (walk-forward)" metrics column next to the existing in-sample metrics table per horizon. Show F1 / AUC / Brier (mean ± std across folds).

Add a small calibration panel: "Calibration method: {isotonic|platt} — Brier {raw} → {calibrated}".

No structural decomposition of the page — that is Phase 2C and explicitly deferred.

- [ ] **Step 3: Final integration check**

`pytest tests/test_recession_*.py -v` — all green.

`POST /api/recession/train`, then `GET /api/recession/model-info`. Inspect response: walk_forward_metrics, calibration, optimal_thresholds, feature_names, metrics all populated.

Visit `/recession-model`. Confirm calibrated ensemble probability shows in the headline gauge; in-sample + walk-forward metrics both render; calibration method visible.

---

## Final integration

Use `superpowers:finishing-a-development-branch` after Phase 2A Task A5 completes to decide on merge/PR/cleanup.
