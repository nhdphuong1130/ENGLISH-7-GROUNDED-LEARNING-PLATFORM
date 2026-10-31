import 'package:english7_mobile/features/flashcards/practice_session_store.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('saves and loads flashcard practice session', () async {
    const storage = FlutterSecureStorage();
    final store = PracticeSessionStore(storage: storage);

    final state = PracticeSessionState(
      deckId: 'deck-123',
      mode: 'flashcard',
      currentIndex: 3,
      totalCards: 10,
      ratings: ['good', 'again', 'good'],
      scores: [],
      attempts: [],
      updatedAt: DateTime.parse('2026-10-29T02:00:00Z'),
    );

    await store.save(state);
    final loaded = await store.load('deck-123', 'flashcard');

    expect(loaded, isNotNull);
    expect(loaded!.deckId, 'deck-123');
    expect(loaded.mode, 'flashcard');
    expect(loaded.currentIndex, 3);
    expect(loaded.totalCards, 10);
    expect(loaded.ratings, ['good', 'again', 'good']);
    expect(loaded.scores, isEmpty);
    expect(loaded.attempts, isEmpty);
  });

  test('saves and loads speaking practice session with scores and attempts', () async {
    const storage = FlutterSecureStorage();
    final store = PracticeSessionStore(storage: storage);

    final state = PracticeSessionState(
      deckId: 'deck-456',
      mode: 'speaking_word',
      currentIndex: 2,
      totalCards: 5,
      ratings: [],
      scores: [95.0, 71.25],
      attempts: [1, 2],
      updatedAt: DateTime.parse('2026-10-29T02:15:00Z'),
    );

    await store.save(state);
    final loaded = await store.load('deck-456', 'speaking_word');

    expect(loaded, isNotNull);
    expect(loaded!.deckId, 'deck-456');
    expect(loaded.mode, 'speaking_word');
    expect(loaded.currentIndex, 2);
    expect(loaded.scores, [95.0, 71.25]);
    expect(loaded.attempts, [1, 2]);
  });

  test('clears session for deck and mode', () async {
    const storage = FlutterSecureStorage();
    final store = PracticeSessionStore(storage: storage);

    final state = PracticeSessionState(
      deckId: 'deck-789',
      mode: 'flashcard',
      currentIndex: 5,
      totalCards: 10,
      ratings: ['good'],
      scores: [],
      attempts: [],
      updatedAt: DateTime.now(),
    );

    await store.save(state);
    expect(await store.load('deck-789', 'flashcard'), isNotNull);

    await store.clear('deck-789', 'flashcard');
    expect(await store.load('deck-789', 'flashcard'), isNull);
  });

  test('returns null when no session is saved', () async {
    const storage = FlutterSecureStorage();
    final store = PracticeSessionStore(storage: storage);

    final loaded = await store.load('non-existent', 'flashcard');
    expect(loaded, isNull);
  });
}
