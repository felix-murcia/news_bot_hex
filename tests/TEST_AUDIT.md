# Test Audit Report

**Date:** 2026-05-28  
**Objective:** Identify gaps in test coverage related to infrastructure validation and data integrity

---

## Executive Summary

### Current State
- **Total test files:** 21
- **Total test methods:** ~450+
- **Coverage:** Behavior validation ✅ | Data validation ⚠️ | Infrastructure validation ❌

### Critical Finding
**Tests can pass even with wrong database configuration.** This is the root cause of the critical incident.

Example:
- Test that loads RSS sources from MongoDB uses a mock
- Mock returns test data even if appdb is empty
- Test passes ✅ but system has no real data ❌

---

## Test Organization

### Category 1: Unit Tests with Mocks (13 files)

Pure behavior tests using `@patch` decorators. Do NOT validate real data.

| File | Tests | Issue |
|------|-------|-------|
| test_audio_adapters.py | 19 | Mocks all dependencies |
| test_audio_converter_tts.py | 15 | No real MongoDB access |
| test_audio_pipeline.py | 17 | Mocks all external calls |
| test_domain_services.py | 16 | Tests logic only, not data |
| test_entrypoints.py | 43 | Mocks repositories |
| test_infrastructure_adapters.py | 18 | Some mocks, some real |
| test_news_usecases.py | 24 | ❌ Heavy mocking |
| test_news_usecases_detailed.py | 50 | ❌ Mocked data repos |
| test_process_url_endpoint.py | 16 | Mocks HTTP + repos |
| test_process_url_refactored.py | 11 | Mocked pipelines |
| test_shared_adapters.py | 34 | Mix of real + mocks |
| test_video_generator.py | 14 | Mocks all video ops |
| test_video_pipeline.py | 12 | Mocked pipeline |

**Problem:** These tests validate "does the code do what it's supposed to?" but NOT "does the data exist?"

### Category 2: Integration Tests with Real DB (4 files)

Use actual MongoDB connection.

| File | Tests | Quality |
|------|-------|---------|
| test_infrastructure_validation.py ✅ | 14 | ✅ NEW - validates infrastructure |
| test_mongo_integration.py | 60 | ✅ Good - real DB access |
| test_shared_adapters.py | 34 | ⚠️ Some real + some mocks |
| test_video_pipeline_integration.py | 15 | ⚠️ Real DB but limited scope |

**Good:** These hit real MongoDB. **Issue:** Not enough coverage of critical paths.

### Category 3: E2E Tests (5 files)

| File | Tests | Scope |
|------|-------|-------|
| test_integration.py | 42 | Broad - good coverage |
| test_mongo_integration.py | 60 | Overlaps with integration |
| test_news_pipeline_integration.py | 22 | Pipeline-specific |
| test_process_url_e2e.py | 3 | ❌ Very limited (only 3 tests) |
| test_video_pipeline_integration.py | 15 | Video pipeline only |

---

## Critical Gaps

### Gap 1: No Data Validation in Most Tests

**Severity:** 🔴 CRITICAL

11 test files do NOT validate that data exists in the correct quantities.

**Example of the Problem:**

```python
# BAD - passes even if RSS sources are missing
@patch('MongoRSSSourceRepository.get_all_sources')
def test_fetch_rss(mock_sources):
    mock_sources.return_value = [{"source": "test"}]  # Mocked data
    result = fetch_rss()
    assert result == expected  # ✅ PASSES even if appdb has 0 sources
```

**What's needed:**

```python
# GOOD - fails if real data is missing
def test_fetch_rss_from_appdb():
    sources = MongoRSSSourceRepository().get_all_sources()
    assert len(sources) >= 10, "appdb must have 10+ RSS sources"
    result = fetch_rss()
    assert result is not None
```

**Affected files:**
- test_audio_adapters.py
- test_audio_converter_tts.py
- test_audio_pipeline.py
- test_domain_services.py
- test_news_pipeline.py
- test_news_usecases.py (24 tests, all mocked)
- test_news_usecases_detailed.py (50 tests, mostly mocked)
- test_video_generator.py
- test_video_pipeline.py

### Gap 2: No RSS Sources Validation

**Severity:** 🔴 CRITICAL

Zero tests validate that:
- RSS sources are loaded from MongoDB (not hardcoded)
- There are 10+ sources (currently 18)
- Sources are from `appdb` (not another database)

**Missing test:**

```python
def test_rss_sources_loaded_from_appdb():
    """Verify RSS sources come from appdb, not DEFAULT_SOURCES or hardcoded."""
    from src.news.infrastructure.adapters import MongoRSSSourceRepository
    
    repo = MongoRSSSourceRepository()
    sources = repo.get_all_sources()
    
    assert len(sources) >= 10, f"Expected 10+ sources, got {len(sources)}"
    assert sources[0].get('source') is not None
    assert sources[0].get('url') is not None
    # Verify these are REAL sources, not test data
    source_names = [s.get('source') for s in sources]
    assert 'BBC World' in source_names  # Known source from appdb
```

### Gap 3: No Article Quantity Validation in Pipeline Tests

**Severity:** 🔴 CRITICAL

Pipeline tests don't validate that articles processed:
- Actually come from appdb (not hardcoded)
- Are > 0 (proves pipeline is using real data)
- Match expected schema

**Missing test:**

```python
def test_pipeline_processes_real_articles_from_appdb():
    """Verify pipeline fetches and processes real articles from appdb."""
    from src.news.application.usecases import FetchRSSNewsUseCase
    from src.news.infrastructure.adapters import (
        MongoRSSSourceRepository,
        MongoArticleRepository,
        FeedparserRSSFetcher,
    )
    
    use_case = FetchRSSNewsUseCase(
        MongoRSSSourceRepository(),  # Real repos, not mocked
        MongoArticleRepository(),
        FeedparserRSSFetcher(),
    )
    
    result = use_case.execute()
    
    assert result['status'] != 'error', f"Pipeline failed: {result.get('message')}"
    assert result.get('new_articles', 0) > 0, "Pipeline must process > 0 articles"
    
    # Verify articles are in appdb
    article_count = MongoArticleRepository().count_articles()
    assert article_count >= 1000, f"appdb has {article_count} articles, expected >= 1000"
```

### Gap 4: No DEFAULT_SOURCES Detection

**Severity:** 🟠 HIGH

If someone adds hardcoded DEFAULT_SOURCES, tests won't detect it.

**Missing test:**

```python
def test_no_hardcoded_default_sources():
    """Prevent hardcoding default RSS sources - always use MongoDB."""
    # Search codebase for DEFAULT_SOURCES
    import subprocess
    result = subprocess.run(
        ["grep", "-r", "DEFAULT_SOURCES", "src/"],
        capture_output=True
    )
    assert result.returncode != 0, (
        "Found DEFAULT_SOURCES in code. "
        "All RSS sources must come from MongoDB, not hardcoded defaults."
    )
```

### Gap 5: No Database Configuration Validation in Existing Tests

**Severity:** 🟠 HIGH

Tests don't verify that they're running against `appdb`, not some other database.

Each test should start with:
```python
def test_uses_correct_appdb():
    from config.settings import Settings
    assert Settings.MONGO_DB_NAME == 'appdb', "Tests must use appdb"
```

---

## Recommended Fixes (Priority Order)

### PRIORITY 1: Critical (This week)

**1.1 Create integration tests for RSS sources**
- File: `tests/src/test_rss_sources_integration.py`
- Validate: Sources load from appdb, count >= 10, structure valid
- Dependencies: Real MongoDB required

**1.2 Create pipeline end-to-end tests**
- File: `tests/src/test_pipeline_e2e_with_real_data.py`
- Validate: Pipeline processes > 0 articles from appdb
- Dependencies: Real MongoDB + RSS sources + articles required

**1.3 Add data validation to existing integration tests**
- Files: test_mongo_integration.py, test_entrypoints.py
- Add: Assertions about article counts, source counts, data structures

### PRIORITY 2: Important (Week 2)

**2.1 Convert heavy-mock tests to use real MongoDB where possible**
- test_news_usecases_detailed.py: Has 50 tests, mostly mocked
- Test with real data: Process 5-10 real articles, not mocked ones

**2.2 Add data validation to pipeline tests**
- test_news_pipeline_integration.py: Add assertions about quantities
- test_audio_pipeline.py: Same pattern

### PRIORITY 3: Nice to have (Week 3+)

**3.1 Code coverage analysis**
- Run `pytest --cov=src --cov-report=html`
- Identify untested code paths
- Target 80%+ coverage on critical modules

---

## Implementation Strategy

### Phase 1: Add Critical Tests (2-3 days)

1. Create `test_rss_sources_integration.py` with 5-8 tests
2. Create `test_pipeline_e2e_real_data.py` with 4-6 tests
3. Update `test_infrastructure_validation.py` with pipeline-specific tests
4. All new tests use REAL MongoDB, not mocks

### Phase 2: Improve Existing Tests (3-4 days)

1. Add assertions to test_mongo_integration.py
2. Add data validation to test_entrypoints.py
3. Reduce mock usage in test_news_usecases_detailed.py

### Phase 3: Coverage Analysis (1-2 days)

1. Run pytest with coverage
2. Identify gaps in critical modules
3. Add tests for gaps

---

## Success Criteria

### After Audit (NOW)
- ✅ Identified 5 critical gaps
- ✅ Documented which tests use mocks vs real data
- ✅ Created prioritized fix list

### After Phase 1 (This week)
- ✅ New tests for RSS sources and pipeline with real data
- ✅ Tests fail if appdb has < 1000 articles
- ✅ Tests fail if < 10 RSS sources
- ❌ Never fails due to mocks masking real problems

### After Phase 2 (Week 2)
- ✅ 80%+ of pipeline tests use real MongoDB
- ✅ Data validation in all integration tests
- ✅ No test can pass with wrong database

### After Phase 3 (Week 3)
- ✅ Code coverage report available
- ✅ 80%+ coverage on critical paths
- ✅ Gaps identified and prioritized

---

## Metrics to Track

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Integration tests (real DB) | 4 files | 6+ files | Phase 1 |
| Pipeline data validation | 0 | 3+ tests | Phase 1 |
| RSS source validation | 0 | 2+ tests | Phase 1 |
| Code coverage | Unknown | 80%+ | Phase 3 |
| Mocks in critical paths | HIGH | LOW | Phase 2 |

---

## Files to Create/Modify

| Action | File | Phase | Complexity |
|--------|------|-------|-----------|
| CREATE | tests/src/test_rss_sources_integration.py | 1 | Medium |
| CREATE | tests/src/test_pipeline_e2e_real_data.py | 1 | High |
| MODIFY | tests/src/test_infrastructure_validation.py | 1 | Low |
| MODIFY | tests/src/test_mongo_integration.py | 2 | Medium |
| MODIFY | tests/src/test_news_pipeline_integration.py | 2 | Low |
| MODIFY | conftest.py | 2 | Medium |

