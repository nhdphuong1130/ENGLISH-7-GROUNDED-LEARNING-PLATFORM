import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:english7_mobile/app/learning_api.dart';
import 'package:english7_mobile/features/flashcards/practice_session_store.dart';
import 'package:english7_mobile/features/flashcards/review_screen.dart';

class TestLearningApi implements LearningApi {
  final List<Flashcard> cards;
  final List<String> reviewedCardIds = [];

  TestLearningApi(this.cards);

  @override
  Future<List<Flashcard>> loadCards(String deckId) async => cards;

  @override
  Future<List<Flashcard>> loadReviewCards(String deckId) async => cards;

  @override
  Future<FlashcardReviewResult> reviewCard(
    String id, {
    required String requestId,
    required String answer,
    required String rating,
  }) async {
    reviewedCardIds.add(id);
    return FlashcardReviewResult(
      correct: rating == 'good',
      meaning: 'nghĩa',
      dueAt: DateTime.now(),
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  final testCards = [
    const Flashcard(id: 'c1', deckId: 'deck-1', word: 'apple', meaning: 'quả táo'),
    const Flashcard(id: 'c2', deckId: 'deck-1', word: 'banana', meaning: 'quả chuối'),
    const Flashcard(id: 'c3', deckId: 'deck-1', word: 'cherry', meaning: 'quả anh đào'),
  ];
  const testDeck = FlashcardDeck(id: 'deck-1', name: 'Trái cây', kind: 'textbook', cardCount: 3);

  testWidgets('ReviewScreen renders segmented mastery bar and true percentage', (tester) async {
    final api = TestLearningApi(testCards);
    final store = PracticeSessionStore(storage: const FlutterSecureStorage());

    await tester.pumpWidget(MaterialApp(
      home: ReviewScreen(api: api, deck: testDeck, sessionStore: store),
    ));
    await tester.pumpAndSettle();

    // Check header displays true mastery
    expect(find.textContaining('Đã thuộc: 0/3 (0%)'), findsOneWidget);

    // Tap 'Chưa nhớ' (again)
    await tester.tap(find.text('Chưa nhớ'));
    await tester.pumpAndSettle();

    // After 'again', mastery is still 0/3 (0%)
    expect(find.textContaining('Đã thuộc: 0/3 (0%)'), findsOneWidget);
    expect(find.text('banana'), findsOneWidget);

    // Tap 'Đã nhớ' (good)
    await tester.tap(find.text('Đã nhớ'));
    await tester.pumpAndSettle();

    // Now card 2 was remembered -> mastery is 1/3 (33%)
    expect(find.textContaining('Đã thuộc: 1/3 (33%)'), findsOneWidget);
    expect(find.text('cherry'), findsOneWidget);
  });

  testWidgets('ReviewScreen prompts resume dialog when in-progress session exists', (tester) async {
    final api = TestLearningApi(testCards);
    final store = PracticeSessionStore(storage: const FlutterSecureStorage());

    // Pre-save an in-progress session at index 1
    await store.save(PracticeSessionState(
      deckId: 'deck-1',
      mode: 'flashcard',
      currentIndex: 1,
      totalCards: 3,
      ratings: ['again'],
      scores: [],
      attempts: [],
      updatedAt: DateTime.now(),
    ));

    await tester.pumpWidget(MaterialApp(
      home: ReviewScreen(api: api, deck: testDeck, sessionStore: store),
    ));
    await tester.pumpAndSettle();

    // Dialog should appear
    expect(find.text('Tiếp tục bài học?'), findsOneWidget);
    expect(find.text('Tiếp tục'), findsOneWidget);
    expect(find.text('Học lại từ đầu'), findsOneWidget);

    // Tap 'Tiếp tục'
    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();

    // Should resume at card 2 (banana)
    expect(find.text('banana'), findsOneWidget);
    expect(find.textContaining('Thẻ 2 / 3'), findsOneWidget);
  });
}
