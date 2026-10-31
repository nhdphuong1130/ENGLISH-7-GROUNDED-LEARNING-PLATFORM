import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:english7_mobile/app/learning_api.dart';
import 'package:english7_mobile/features/flashcards/practice_session_store.dart';
import 'package:english7_mobile/features/speaking/sentence_practice_screen.dart';
import 'package:english7_mobile/services/speech_recorder.dart';
import 'package:english7_mobile/services/tts_service.dart';

class FakeTestRecorder implements SpeechRecorder {
  @override
  Future<void> start() async {}
  @override
  Future<Uint8List> stop() async => Uint8List.fromList([1, 2, 3]);
  @override
  Future<void> play(Uint8List audioBytes) async {}
  @override
  Future<void> dispose() async {}
}

class FakeTestTts implements TtsService {
  @override
  Future<void> speak(String text, {String language = 'en-GB', double? rate}) async {}
  @override
  Future<void> stop() async {}
  @override
  Future<void> dispose() async {}
}

class FakeSpeakingApi implements LearningApi {
  final List<Flashcard> cards;
  double mockMatchPercent = 100.0;

  FakeSpeakingApi(this.cards);

  @override
  Future<List<Flashcard>> loadCards(String deckId) async => cards;

  @override
  Future<SpeakingVoices> loadVoices() async => const SpeakingVoices(items: [], selectedVoice: 'v1', available: false);

  @override
  Future<SpeakingResult> submitSpeaking({
    required String requestId,
    required String cardId,
    required String voiceId,
    required Uint8List audio,
    String? prompt,
  }) async {
    return SpeakingResult(
      id: 'res-1',
      cardId: cardId,
      prompt: prompt ?? '',
      transcript: prompt ?? '',
      feedback: 'Good',
      matchPercent: mockMatchPercent,
      createdAt: DateTime.now(),
      missingWords: const [],
      extraWords: const [],
      wordEvaluations: const [],
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  const testDeck = FlashcardDeck(
    id: 'deck-speaking',
    name: 'Unit 1 Speaking',
    kind: 'textbook',
    cardCount: 2,
  );

  final testCards = [
    const Flashcard(
      id: 'c1',
      deckId: 'deck-speaking',
      word: 'hobby',
      meaning: 'sở thích',
      example: 'My hobby is reading.',
    ),
    const Flashcard(
      id: 'c2',
      deckId: 'deck-speaking',
      word: 'craft',
      meaning: 'thủ công',
      example: 'I love making crafts.',
    ),
  ];

  testWidgets('Score decays on retry attempts (attempt 2 = 75%)', (tester) async {
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final api = FakeSpeakingApi([testCards[0]]);
    final recorder = FakeTestRecorder();
    final tts = FakeTestTts();
    final store = PracticeSessionStore(storage: const FlutterSecureStorage());

    // 1st attempt fails with 50%
    api.mockMatchPercent = 50.0;

    await tester.pumpWidget(MaterialApp(
      home: SentencePracticeScreen(
        api: api,
        deck: const FlashcardDeck(id: 'deck-speaking', name: 'U1', kind: 'textbook', cardCount: 1),
        recorder: recorder,
        ttsService: tts,
        sessionStore: store,
        isSentenceMode: true,
      ),
    ));
    await tester.pumpAndSettle();

    // Tap record
    await tester.tap(find.text('Thu âm'));
    await tester.pump();
    await tester.tap(find.text('Dừng thu & Chấm điểm'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Cần đạt ≥ 80%'), findsOneWidget);

    // 2nd attempt passes with 100% raw score -> should decay by 0.75 -> 75%
    api.mockMatchPercent = 100.0;
    await tester.tap(find.text('Thử lại ↻ (Lần 1/5)'));
    await tester.pump();
    await tester.tap(find.text('Dừng thu & Chấm điểm'));
    await tester.pumpAndSettle();

    // Summary screen should show 75%
    expect(find.textContaining('Hoàn thành bài luyện nói'), findsOneWidget);
    expect(find.text('75%'), findsOneWidget);
  });

  testWidgets('SentencePracticeScreen prompts resume dialog when in-progress session exists', (tester) async {
    final api = FakeSpeakingApi(testCards);
    final recorder = FakeTestRecorder();
    final tts = FakeTestTts();
    final store = PracticeSessionStore(storage: const FlutterSecureStorage());

    // Pre-save session at index 1
    await store.save(PracticeSessionState(
      deckId: 'deck-speaking',
      mode: 'speaking_sentence',
      currentIndex: 1,
      totalCards: 2,
      ratings: [],
      scores: [100.0],
      attempts: [1],
      updatedAt: DateTime.now(),
    ));

    await tester.pumpWidget(MaterialApp(
      home: SentencePracticeScreen(
        api: api,
        deck: testDeck,
        recorder: recorder,
        ttsService: tts,
        sessionStore: store,
        isSentenceMode: true,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Tiếp tục bài học?'), findsOneWidget);
    expect(find.text('Tiếp tục'), findsOneWidget);
    expect(find.text('Học lại từ đầu'), findsOneWidget);

    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();

    // Should resume at card 2
    expect(find.textContaining('Câu 2 / 2'), findsOneWidget);
  });
}
