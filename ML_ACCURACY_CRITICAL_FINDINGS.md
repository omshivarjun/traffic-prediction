# ML Model Accuracy Testing - CRITICAL FINDINGS

## Executive Summary

**Status:** ⚠️ **MODELS INCOMPATIBLE - CANNOT TEST ACCURACY**  
**Date:** 2025-10-05  
**Severity:** **HIGH** - Blocking accuracy verification  
**Safety Impact:** **CANNOT VERIFY PREDICTION ACCURACY**

## Critical Issue Discovered

### Problem: NumPy Version Incompatibility

The trained ML models in HDFS (`/traffic-data/models/`) were created with an **older version of NumPy** and cannot be loaded in the current environment with NumPy 1.26.4.

**Error:**
```
ValueError: <class 'numpy.random._mt19937.MT19937'> is not a known BitGenerator module.
```

**Root Cause:**
- Models were pickled using an older NumPy version (likely <1.20)
- Pickle format for `numpy.random.MT19937` changed between versions
- Current environment has NumPy 1.26.4 which cannot deserialize the old format
- This is a **known incompatibility** in the NumPy ecosystem

### Models Found in HDFS

✅ **Successfully Downloaded (but cannot load):**
1. `random_forest_speed.joblib` (29.5 MB)
2. `gradient_boosting_speed.joblib` (143 KB)
3. `random_forest_congestion.joblib` (29.5 MB)
4. `scaler_features.joblib` (1.3 KB)
5. `encoder_highway.joblib` (519 bytes)
6. `model_metadata.json` (3.2 KB)

All files downloaded successfully from HDFS using docker cp method, but loading fails due to NumPy incompatibility.

## Impact on Safety-Critical Testing

### What This Means

1. **Cannot Verify Accuracy:** We cannot test if predictions match reality (MAE, RMSE, R²)
2. **Cannot Assess Production Readiness:** Unknown if models meet accuracy thresholds
3. **Safety Gap:** Output validation ensures predictions are SAFE (0-100 mph), but we cannot verify they are CORRECT

### Current Safety Status

| Layer | Status | Coverage |
|-------|--------|----------|
| **Input Validation** | ✅ COMPLETE | Prevents garbage sensor data |
| **Output Validation** | ✅ COMPLETE | Prevents dangerous predictions |
| **Accuracy Verification** | ❌ **BLOCKED** | Cannot load models to test |

**Safety Concern:** Predictions can be within safe bounds (0-100 mph) but still completely WRONG (predict 60 mph when actual is 5 mph). Without accuracy testing, we cannot verify correctness.

## Attempted Fixes

### Compatibility Patches Tested ❌

1. **Monkey-patching sys.modules** - Failed (not seen by joblib)
2. **Patching numpy.random._pickle** - Failed (unpickler runs before patch)
3. **Using sklearn's joblib** - Failed (same underlying issue)
4. **getattr to avoid name mangling** - Failed (error occurs in NumPy internals)

**Conclusion:** The incompatibility occurs deep in NumPy's unpickling process BEFORE our patches can intercept it. **Models must be retrained.**

## Solutions

### Option 1: Retrain Models (RECOMMENDED) ✅

**Reconstruct and Run:** `metr_la_ml_training.py`

**Current Status:** File is CORRUPTED (850 lines, corruption on line 19)

**Action Required:**
1. Reconstruct `src/batch-processing/metr_la_ml_training.py` from scratch
2. Use existing METR-LA data in HDFS: `/traffic-data/raw/.../metr-la-historical.jsonl` (33 MB)
3. Train models with current NumPy 1.26.4 and scikit-learn 1.7.2
4. Save models to HDFS with current versions
5. Run accuracy testing

**Timeline:**
- File reconstruction: 2-3 hours
- Model training: 1-2 hours (depending on data size)
- Accuracy testing: 30 minutes
- **Total: 4-6 hours**

### Option 2: Downgrade NumPy ❌ NOT RECOMMENDED

**Why Not:**
- Would require downgrading entire environment
- May break other dependencies (scikit-learn 1.7.2 requires recent NumPy)
- Creates technical debt
- Doesn't fix underlying compatibility issue

### Option 3: Skip Accuracy Testing ❌ UNSAFE

**Why Not:**
- User's safety concern: "accidents will happen due to wrong predictions"
- Cannot deploy models without knowing accuracy
- Would violate safety-critical requirements
- Safe ≠ Correct (predictions can be bounded but wrong)

## Recommended Path Forward

### Immediate Priority (Phase 3 - CURRENT)

1. **Reconstruct `metr_la_ml_training.py`** (HIGH PRIORITY)
   - Based on existing training pipeline architecture
   - Use METR-LA dataset structure from `scripts/generate-metr-la-data.py`
   - Follow patterns from working stream processing code
   - Include: Feature engineering, model training, validation, HDFS export

2. **Train New Models** (CRITICAL)
   - Use 33 MB METR-LA historical data already in HDFS
   - Train RandomForestRegressor and GradientBoostingRegressor
   - Save with current library versions
   - Export scaler and encoder

3. **Run Accuracy Testing** (SAFETY-CRITICAL)
   - Execute `scripts/test_ml_accuracy.py` (already created and debugged)
   - Verify MAE <5 mph (excellent) or <10 mph (acceptable)
   - Verify RMSE <8 mph (excellent) or <15 mph (acceptable)
   - Verify R² >0.7 (excellent) or >0.5 (acceptable)

4. **Make Production Decision**
   - **If EXCELLENT:** Deploy to production
   - **If ACCEPTABLE:** Deploy with monitoring, plan improvements
   - **If POOR:** Retrain with more data/features before deployment

### Next Steps After Accuracy Testing

5. **Generate Sample Data** (Phase 3 continued)
   - Create realistic METR-LA sensor readings
   - Normal, rush hour, accident, extreme weather scenarios
   - Produce to Kafka topics

6. **End-to-End Pipeline Test**
   - Trace data: Kafka → Validation → Processing → HDFS → ML → Database → API → Frontend
   - Verify no data loss or corruption
   - Test real-time updates
   - Validate safety bounds at each stage

7. **Production Integration**
   - Integrate validators into Kafka/Spark pipeline
   - Create monitoring dashboards
   - Set up alerting for validation failures
   - Performance and load testing

## Test Framework Ready ✅

**Good News:** Testing infrastructure is complete and ready to use once models are retrained:

- ✅ `scripts/test_ml_accuracy.py` (600+ lines)
- ✅ Model download from HDFS working (docker cp method)
- ✅ Test data loading ready
- ✅ Feature preparation implemented
- ✅ Accuracy metrics configured (MAE, RMSE, R²)
- ✅ Production readiness assessment logic
- ✅ JSON report generation

**Just waiting for:** Compatible models to test against

## Data Assets Confirmed ✅

**HDFS Contains:**
- ✅ Training data: 33 MB METR-LA historical (JSONL)
- ✅ Processed features: 1.3 MB ML features (CSV)
- ✅ Hourly aggregates: 1.5 MB aggregated data
- ✅ Old models: 60 MB (incompatible but shows training ran successfully)

**All necessary data exists for retraining**

## Safety Timeline

### Completed (Phases 1 & 2)
- ✅ Output validation: Prevents impossible predictions (14 tests passing)
- ✅ Input validation: Prevents garbage sensor data (22 tests passing)
- ✅ Dual-layer protection: Clean input + Safe output

### Blocked (Phase 3)
- ⏸️ Accuracy verification: **WAITING ON MODEL RETRAINING**
- ⏸️ Production readiness: Cannot assess without accuracy metrics
- ⏸️ End-to-end testing: Should use validated accurate models

### Critical Question Unanswered

**"Are predictions ACCURATE?"** - CANNOT ANSWER until models retrained

User needs to know:
- ❓ Do predictions match reality? (UNKNOWN - can't test)
- ❓ Is MAE acceptable for safety? (UNKNOWN - can't measure)
- ❓ Are models production-ready? (UNKNOWN - can't evaluate)

## Conclusion

**Current State:**
- Safety validation layers: ✅ COMPLETE (input + output)
- Accuracy verification: ❌ BLOCKED (model incompatibility)
- Production deployment: ⏸️ ON HOLD (waiting for accuracy confirmation)

**Critical Path:**
1. Reconstruct `metr_la_ml_training.py`
2. Retrain models with current NumPy
3. Test accuracy with ready-to-use test framework
4. Make production deployment decision based on results

**User Safety Concern Address:**
- "Accidents will happen due to wrong predictions"
- ✅ Safe predictions: Bounds enforced (0-100 mph)
- ✅ Clean data: Input validation prevents garbage
- ❓ Correct predictions: **CANNOT VERIFY** until models retrained

**Recommendation:** Prioritize model retraining as the blocker for completing safety-critical testing.

---

**Report Generated:** 2025-10-05  
**Test Framework:** `scripts/test_ml_accuracy.py`  
**Status:** Ready to test once models are compatible
