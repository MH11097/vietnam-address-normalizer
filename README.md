# Vietnamese Address Normalizer

Hệ thống phân tích và chuẩn hóa địa chỉ Việt Nam với 5-phase pipeline, tối ưu hóa hiệu suất cao.

## ✨ Đặc điểm nổi bật

- ✅ **Database-driven**: Matching với 9,991 admin divisions (tỉnh-huyện-xã)
- ✅ **Token Index**: Tối ưu 61x speedup (14.5s → 237ms)
- ✅ **Multi-source**: Kết hợp local DB + disambiguation + OSM/Goong API
- ✅ **Smart API**: Chỉ gọi API khi local confidence < 0.7
- ✅ **Hierarchical validation**: Kiểm tra phân cấp hành chính
- ✅ **No keywords required**: N-gram matching không cần từ khóa (phường, quận, tỉnh)

## 📊 Performance

| Tình huống | Thời gian | Ghi chú |
|------------|-----------|---------|
| Full search (9,991 records) | 237ms | Token index enabled |
| With province hint (~300 records) | 11.4s | Scoped search |
| Memory usage | ~50MB | With caching |

## 🏗️ Kiến trúc 5 Phases

```
Raw Address → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Structured Output
              ↓          ↓          ↓          ↓          ↓
           Normalize  Extract   Candidates  Validate   Format
```

### Phase 1: Preprocessing
- Unicode normalization (NFC)
- Context-aware abbreviation expansion (97 safe entries)
- Diacritic removal

### Phase 2: Extraction
- Database N-gram matching (no keywords needed)
- Token index pre-filtering (50-100x speedup)
- Geographic hints support
- Extracts potential matches

### Phase 3: Candidate Generation
- Generates candidates from Phase 2 potentials
- Multi-source: local DB + disambiguation + street-based + API
- Conditional OSM/Goong calls (only when needed)
- Populates full names (prevents redundant DB lookups)

### Phase 4: Validation & Ranking
- Hierarchical validation (ward→district→province)
- Ensemble confidence scoring
- Multi-factor ranking

### Phase 5: Post-processing
- STATE/COUNTY code lookup
- Remaining address extraction
- Output formatting with quality flags

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/MH11097/vietnam-address-normalizer.git
cd vietnam-address-normalizer

# Create virtual environment
python -m venv .wvenv
.wvenv\Scripts\activate  # Windows
source .wvenv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Usage

**Single address mode:**
```bash
python demo.py --address "dien bien ba dinh ha noi"
python demo.py --address "22 ngo 629 giai phong" --province "ha noi"
```

**Database batch mode:**
```bash
python demo.py --limit 5
python demo.py --limit 10 --offset 100
```

## 📁 Project Structure

```
vietnam-address-normalizer/
├── src/
│   ├── processors/              # 5 Phase processors
│   │   ├── phase1_preprocessing.py
│   │   ├── phase2_extraction.py
│   │   ├── phase3_candidates.py
│   │   ├── phase4_validation.py
│   │   └── phase5_postprocessing.py
│   │
│   ├── utils/                   # Utilities
│   │   ├── db_utils.py          # Database operations
│   │   ├── extraction_utils.py  # N-gram matching
│   │   ├── token_index.py       # Token index optimization
│   │   ├── text_utils.py        # Text processing
│   │   └── matching_utils.py    # Fuzzy matching
│   │
│   └── crawl/                   # Data crawlers
│
├── data/                        # Database files (not in repo)
├── demo.py                      # Interactive demo
├── requirements.txt
├── ARCHITECTURE.md              # Detailed architecture
└── TODO.md                      # Implementation tracking

```

## 🎯 Example Output

**Input:**
```
Address: "dien bien ba dinh ha noi"
Province hint: "ha noi"
```

**Output:**
```
✓ Phase 1: 2.0ms - Normalized text
✓ Phase 2: 237ms - Extracted potentials
✓ Phase 3: 1362ms - Generated 3 candidates (local + OSM)
✓ Phase 4: 0.0ms - Best match: Ba Dinh, Ha Noi (confidence: 0.66)
✓ Phase 5: 2.0ms - Formatted output

Result:
  Ward: ____
  District: Ba Dinh
  Province: Thành Phố Hà Nội
  Quality: partial_address
  Remaining: DIEN BIEN
```

## 🔧 Configuration

Create `.env` file (use `.env.example` as template):
```bash
# Database path
DATABASE_PATH=data/address.db

# OSM Nominatim API
OSM_NOMINATIM_URL=https://nominatim.openstreetmap.org

# Goong API (optional)
USE_GOONG_API=false
GOONG_API_KEY=your_api_key_here
```

## 📚 Documentation

- **ARCHITECTURE.md** - Complete system architecture and refactoring notes
- **TODO.md** - Detailed implementation tracking (532 lines)

## 🔍 Key Features Detail

### 1. Token Index Optimization
Pre-filters candidates by token overlap before fuzzy matching:
- Reduces search space: 9,991 → 10-50 candidates
- 50-100x speedup for fuzzy operations
- Memory efficient: ~5-10MB

### 2. Multi-source Candidate Generation
```
Local DB → Disambiguation → Street-based → OSM/Goong API
          (if ambiguous)   (if streets)   (if confidence < 0.7)
```

### 3. Hierarchical Validation
Validates ward belongs to correct district/province:
- Database validation with O(1) lookup
- -20% confidence penalty for invalid hierarchy

### 4. Ensemble Confidence Scoring
```
Final Score = (Match Type × 50%) + (At Rule × 30%) +
              (String Similarity × 15%) + (Source Reliability × 15%) +
              Geographic Bonus (+10%) - Hierarchy Penalty (-20%)
```

## 🛠️ Development

### Running Tests
```bash
# Test single address
python demo.py --address "test address"

# Test with database
python demo.py --limit 10
```

### Performance Profiling
Check phase timing in demo output for bottleneck identification.

## 📋 TODO

### Completed ✅
- [x] 5-phase pipeline implementation
- [x] Token index optimization
- [x] Multi-source candidate generation
- [x] Phase 2-3 refactoring
- [x] Full names population
- [x] Conditional API calls

### In Progress 🔄
- [ ] Scoped search optimization
- [ ] Unit tests

### Planned 📝
- [ ] Parallel batch processing
- [ ] API rate limiting
- [ ] ML-based extraction (PhoBERT NER)
- [ ] Monitoring dashboard

## 📄 License

MIT License

---

**Simple, Fast, Accurate! 🎯**
