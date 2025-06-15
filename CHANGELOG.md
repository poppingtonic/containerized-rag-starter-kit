# Changelog

All notable changes to the WriteHere GraphRAG project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Latest] - 2025-06-15

### Added
- **Advanced QA System**: Implemented comprehensive question-answering capabilities as the default query processing
  - **Smart Chunk Classification**: LLM-based relevance scoring beyond vector similarity for more precise chunk selection
  - **Subquestion Amplification**: Complex query decomposition into focused subquestions for comprehensive analysis
  - **Answer Verification**: Built-in hallucination detection and confidence scoring to ensure response reliability
  - **Security-Aware Prompting**: Protection against prompt injection attacks with graceful handling of off-topic queries
  - **Multi-Step Processing**: Classification → Selection → Decomposition → Synthesis → Verification pipeline
- **New API Endpoints**:
  - `POST /query` - Main endpoint with advanced QA features (smart selection, amplification, verification)
  - `POST /query/simple` - Legacy endpoint for basic vector search without advanced features
  - `POST /query/classify-chunks` - Diagnostic endpoint for chunk relevance classification
  - `POST /query/generate-subquestions` - Diagnostic endpoint for question decomposition analysis
  - `POST /query/verify-answer` - Diagnostic endpoint for answer verification against context
- **QA Service Architecture**: Redesigned service layer with advanced prompting strategies
  - Renamed `EnhancedQAService` to `QAService` as the primary query processing service
  - Integrated digest-api's proven prompting techniques for better answer quality
  - Configurable features via environment variables (amplification, classification, verification)
- **Comprehensive Test Suite**: 9 test cases covering all advanced QA functionality
  - Complex query processing with climate/food security scenarios
  - Subquestion generation and decomposition testing
  - Answer verification with false claim detection
  - Security prompt injection resistance testing
  - Performance comparison between simple and advanced queries
  - Health policy, agricultural technology, and economic impact analysis tests

### Changed
- **Default Query Behavior**: `/query` endpoint now uses advanced QA features by default
  - Intelligent chunk selection using LLM classification
  - Optional subquestion amplification for complex queries
  - Built-in answer verification for quality assurance
  - Enhanced prompting with security instructions
- **Service Refactoring**: Restructured query processing architecture
  - `enhanced_qa_service.py` → `qa_service.py` (primary service)
  - `query_routes.py` → uses advanced QA features
  - `legacy_routes.py` → provides simple functionality for backward compatibility
- **Documentation Updates**: Updated all documentation to reflect new QA system
  - `ENHANCED_QA_README.md` → describes advanced capabilities as default
  - `CLAUDE.md` → updated with new usage examples and test commands

### Technical Implementation
- **Prompting Strategies**: Based on analysis of digest-api's ICE (Interactive Composition Explorer)
  - Binary classification prompts for chunk relevance ("Yes"/"No" responses)
  - Structured subquestion generation with context awareness
  - Answer verification against source documents
  - Security instructions embedded in all prompts
- **Performance Optimizations**:
  - Smart chunk selection reduces irrelevant processing
  - Parallel subquestion processing where possible
  - Configurable amplification threshold (500+ character contexts)
  - Token usage optimization with targeted model selection
- **Quality Assurance**:
  - Verification scores (0.0-1.0) with 0.7+ threshold for supported answers
  - Subquestion trace for transparent reasoning
  - Source-grounded citations with document references
  - Graceful degradation when advanced features are disabled

### Performance Metrics
- **Response Times**: 3-5 seconds for complex queries with amplification, <1 second for simple queries
- **Token Usage**: 20-30% increase for advanced features, optimized for quality/cost balance
- **Accuracy**: Verification system successfully detects false claims (0.1 score for obviously wrong answers)
- **Security**: Prompt injection resistance confirmed through testing
- **Backward Compatibility**: Legacy `/query/simple` endpoint maintains original performance

### Configuration Options
```bash
# Advanced QA feature toggles
ENABLE_ENHANCED_QA=true
ENABLE_CHUNK_CLASSIFICATION=true  
ENABLE_SUBQUESTION_AMPLIFICATION=true
ENABLE_ANSWER_VERIFICATION=true

# Quality thresholds
CHUNK_RELEVANCE_THRESHOLD=0.5
VERIFICATION_THRESHOLD=0.7
MAX_SUBQUESTIONS=4
AMPLIFICATION_MIN_CONTEXT_LENGTH=500
```

---

## [Previous] - 2025-06-13

### Fixed
- **CRITICAL**: Resolved JSON parsing errors causing 500 Internal Server Error on `/query` endpoint
  - Fixed improper handling of PostgreSQL `jsonb` columns in memory, query, and thread services
  - Removed unnecessary `json.loads()` calls on already-parsed objects
  - Added proper type checking for `source_metadata` field handling
- **Database Schema**: Fixed column name mismatches between code and database
  - Added generated column aliases for backward compatibility:
    - `query_cache.query` → `query_cache.query_text`
    - `query_cache.answer` → `query_cache.answer_text`
    - `user_feedback.is_thread` → `user_feedback.has_thread`
- **Frontend**: Fixed `threads.forEach is not a function` error in FavoritesList component
  - Properly extracted arrays from API responses (`data.favorites`, `data.threads`)
  - Added fallback handling for empty or malformed API responses

### Changed
- **API Services**: Improved JSON handling for PostgreSQL `jsonb` data types
  - Updated `MemoryService._format_memory_response()` to handle `jsonb` columns correctly
  - Updated `QueryService.generate_answer()` and `QueryService.process_query()` for proper metadata parsing
  - Updated `ThreadService._generate_thread_response()` for consistent JSON handling
- **Frontend**: Enhanced query request format
  - Added explicit `use_memory: true` parameter to query requests
  - Improved error handling for API response parsing

### Technical Details
- **Files Modified**:
  - `api_service/services/memory_service.py` - Fixed `jsonb` column handling and source metadata parsing
  - `api_service/services/query_service.py` - Fixed source metadata extraction and response formatting
  - `api_service/services/thread_service.py` - Fixed chunk formatting and reference extraction
  - `frontend/src/main.js` - Added explicit `use_memory` parameter to query requests
  - `frontend/src/components/FavoritesList.vue` - Fixed API response array extraction
- **Database Changes**:
  - Added generated column aliases for schema compatibility without breaking existing code

### Impact
- **System Stability**: Eliminated 500 errors on query endpoint
- **User Experience**: Restored full functionality for document querying with AI-powered answers
- **Data Integrity**: Proper handling of database JSON fields prevents data corruption
- **Frontend Reliability**: Fixed component crashes when loading favorites and threads

### Verified Functionality
- ✅ Query endpoint working with comprehensive answers and citations
- ✅ Memory caching and retrieval working correctly
- ✅ Vector similarity search functioning properly
- ✅ Reference extraction and source attribution working
- ✅ Favorites and threads endpoints returning proper data
- ✅ Frontend components loading without JavaScript errors
- ✅ All Docker services running and communicating correctly

---

*This changelog covers critical bug fixes that restored full system functionality after database schema updates and service modularization.*