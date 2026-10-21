# Knowledge Gap Diagnosis & Remedial Learning System Design

## 1. Overview & Problem Statement
Students learning Grade 7 English (*Global Success 7*) take practice quizzes and unit tests. While total quiz scores indicate performance, students and teachers currently lack visibility into *specifically which grammar rules, vocabulary sets, or pronunciation sounds* are causing mistakes, and how to remedy those gaps directly from verified textbook material.

This design introduces the **Knowledge Gap Diagnosis & Remedial Learning System**, connecting historical student quiz answers (SQL Server) with the pedagogical curriculum ontology (Neo4j) to pinpoint weak concepts and provide targeted, 1-tap remediation.

---

## 2. Goals & Success Criteria
1. **Accurate Diagnosis:** Identify specific grammar rules, vocabulary words, and pronunciation sounds where a student has $< 70\%$ mastery or repeated mistakes.
2. **Pedagogical Grounding:** Every diagnosed weakness links to verified textbook evidence with unit and page citations (`[Unit X, Page Y]`).
3. **Actionable Remediation (1-Tap):** Students can either:
   - Ask AI Tutor to explain the concept grounded in the textbook.
   - Start an authentic 5-question targeted remedial quiz focusing solely on that weak concept.
4. **Seamless Mobile UX:** Visual display within the existing **Tiến độ** (Progress) tab with mastery percentage bars, status tags, and intuitive action sheets.
5. **Code & Architecture Quality:** Clean separation of concerns, backend unit/integration tests, mobile widget tests, 100% passing test suite (`make test` & `make analyze`).

---

## 3. Data Architecture & Neo4j Integration

### 3.1 Mapping Student Answers to Knowledge Concepts
```
StudentAnswer (SQL Server: is_correct)
  └──> QuizQuestion
        └──> QuestionSource
              └──> SourceFragment (sql_id)
                    └──> [Neo4j]
                          ├── (:GrammarRule) <-[:TEACHES_GRAMMAR]- (SourceFragment)
                          ├── (:Vocabulary) <-[:HAS_VOCABULARY]- (SourceFragment)
                          └── (:PronunciationSound) <-[:TEACHES_PRONUNCIATION]- (SourceFragment)
```

### 3.2 Mastery Calculation
For each diagnosed concept $c$ tested in $N \ge 1$ question attempts:
$$\text{Mastery}(c) = \frac{\text{Correct Answers for } c}{\text{Total Attempts for } c}$$

- **High Mastery ($\ge 70\%$):** Proficient (Xanh)
- **Moderate Gap ($50\% - 69\%$):** Cần củng cố (Vàng)
- **Critical Gap ($< 50\%$):** Lỗ hổng nghiêm trọng (Đỏ)

---

## 4. API Endpoints

### 4.1 `GET /api/v1/learning/knowledge-gap`
Returns the student's analyzed knowledge gaps and overall skill profile.

**Response Structure:**
```json
{
  "total_tested_concepts": 12,
  "weak_concepts_count": 3,
  "average_mastery": 0.65,
  "gaps": [
    {
      "concept_key": "grammar:past_simple",
      "concept_name": "Thì Quá khứ đơn (Past Simple)",
      "category": "grammar",
      "unit_number": 3,
      "unit_title": "Community Service",
      "mastery_score": 0.40,
      "total_attempts": 5,
      "incorrect_count": 3,
      "summary": "Cách dùng thì quá khứ đơn diễn tả hành động đã kết thúc trong quá khứ.",
      "textbook_citation": "SGK Tiếng Anh 7 Unit 3, Trang 28",
      "suggested_prompt": "Giải thích chi tiết về thì Quá khứ đơn trong Unit 3 và cách chia động từ có quy tắc/bất quy tắc giúp em."
    }
  ]
}
```

### 4.2 `POST /api/v1/learning/remedial-quiz`
**Payload:**
```json
{
  "concept_key": "grammar:past_simple"
}
```
**Response:** Standard `QuizSession` response initialized with 5 questions mapped to the requested concept.

---

## 5. Mobile Interface Design

### 5.1 Location: Tab "Tiến độ" (Progress)
- Positioned right below the Progress overview card and before/beside the Test History list.
- Header: **"Chẩn đoán lỗ hổng kiến thức"** with an overview badge (ví dụ: *"3 điểm cần củng cố"*).
- Card elements:
  - Concept Name (`Thì Quá khứ đơn (Past Simple)`)
  - Unit badge (`Unit 3`) + Category tag (`Ngữ pháp`)
  - Color-coded mastery bar (`40%`)
  - Arrow / tap trigger

### 5.2 Remedial Action Modal Bottom Sheet
When tapping a gap item:
- **Title & Status:** Concept Name with mastery indicator.
- **SGK Grounding Box:** Text summary + citation `[SGK Unit 3, Trang 28]`.
- **Action Buttons:**
  - `[🤖 Hỏi AI Tutor]`: Opens the Tutor tab with the prefilled question.
  - `[⚡ Luyện tập bù đắp (5 câu)]`: Starts the remedial quiz instantly.

---

## 6. Verification & Test Plan
- **Backend Tests:**
  - Unit tests for `KnowledgeGapService` computing mastery and querying graph mapping.
  - API router tests for `GET /api/v1/learning/knowledge-gap` and `POST /api/v1/learning/remedial-quiz`.
- **Mobile Tests:**
  - Widget test for `ProgressScreen` rendering knowledge gaps.
  - Widget test for tapping a gap and opening the remedial action sheet.
  - Widget test for triggering the remedial quiz and navigating to AI Tutor.
- **Full Verification:**
  - `make test-backend`
  - `make test-mobile`
  - `make analyze`
