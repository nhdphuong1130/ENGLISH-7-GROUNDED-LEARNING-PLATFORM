import 'dart:typed_data';

import '../api/api_client.dart';
import '../api/api_error.dart';
import 'learning_api.dart';

mixin ApiLearning on Object implements LearningApi {
  ApiClient get learningClient;
  Map<String, dynamic> _json(Map<String, Object?> body) =>
      Map<String, dynamic>.from(body);
  List<T> _items<T>(
    Map<String, Object?> body,
    T Function(Map<String, dynamic>) parse,
  ) => (body['items'] as List)
      .map((v) => parse(Map<String, dynamic>.from(v as Map)))
      .toList();

  @override
  Future<List<FlashcardDeck>> loadDecks() async {
    try {
      final response = await learningClient.getJson('/api/v1/flashcards/decks');
      return _items(response.body, FlashcardDeck.fromJson);
    } on ApiException catch (error) {
      if (error.statusCode != 403) rethrow;
      final adminResponse = await learningClient.getJson('/api/v1/admin/decks');
      return _items(adminResponse.body, FlashcardDeck.fromJson);
    }
  }

  @override
  Future<FlashcardDeck> createDeck(String name) async => FlashcardDeck.fromJson(
    _json(
      (await learningClient.postJson('/api/v1/flashcards/decks', {
        'name': name,
      })).body,
    ),
  );
  @override
  Future<FlashcardDeck> renameDeck(String id, String name) async =>
      FlashcardDeck.fromJson(
        _json(
          (await learningClient.patchJson('/api/v1/flashcards/decks/$id', {
            'name': name,
          })).body,
        ),
      );
  @override
  Future<void> deleteDeck(String id) =>
      learningClient.delete('/api/v1/flashcards/decks/$id');
  @override
  Future<List<Flashcard>> loadCards(String deckId) async {
    try {
      final response = await learningClient.getJson(
        '/api/v1/flashcards/decks/$deckId/cards',
      );
      return _items(response.body, Flashcard.fromJson);
    } on ApiException catch (error) {
      if (error.statusCode != 403) rethrow;
      final adminResponse = await learningClient.getJson(
        '/api/v1/admin/decks/$deckId/cards',
      );
      return _items(adminResponse.body, Flashcard.fromJson);
    }
  }
  @override
  Future<Flashcard> createCard(
    String deckId,
    Map<String, Object?> fields,
  ) async => Flashcard.fromJson(
    _json(
      (await learningClient.postJson(
        '/api/v1/flashcards/decks/$deckId/cards',
        fields,
      )).body,
    ),
  );
  @override
  Future<Flashcard> updateCard(String id, Map<String, Object?> fields) async =>
      Flashcard.fromJson(
        _json(
          (await learningClient.patchJson(
            '/api/v1/flashcards/cards/$id',
            fields,
          )).body,
        ),
      );
  @override
  Future<void> deleteCard(String id) =>
      learningClient.delete('/api/v1/flashcards/cards/$id');
  @override
  Future<List<Flashcard>> loadReviewCards(String deckId) async =>
      loadCards(deckId);
  @override
  Future<FlashcardReviewResult> reviewCard(
    String id, {
    required String requestId,
    required String answer,
    required String rating,
  }) async => FlashcardReviewResult.fromJson(
    _json(
      (await learningClient.postJson('/api/v1/flashcards/cards/$id/review', {
        'request_id': requestId,
        'answer': answer,
        'rating': rating,
      })).body,
    ),
  );
  @override
  Future<Flashcard> flagCard(String id, bool difficult) async =>
      Flashcard.fromJson(
        _json(
          (await learningClient.patchJson('/api/v1/flashcards/cards/$id/flag', {
            'difficult': difficult,
          })).body,
        ),
      );
  @override
  Future<LearningProgress> loadLearningProgress() async =>
      LearningProgress.fromJson(
        _json((await learningClient.getJson('/api/v1/learning/progress')).body),
      );
  @override
  Future<SpeakingVoices> loadVoices() async {
    try {
      final res = await learningClient.getJson('/api/v1/speaking/voices');
      return SpeakingVoices.fromJson(_json(res.body));
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        final res = await learningClient.getJson('/api/v1/admin/speaking/voices');
        return SpeakingVoices.fromJson(_json(res.body));
      }
      rethrow;
    }
  }

  @override
  Future<void> selectVoice(String id) async {
    try {
      await learningClient.putJson('/api/v1/speaking/voice', {'voice_id': id});
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        await learningClient.putJson(
          '/api/v1/admin/speaking/voice',
          {'voice_id': id},
        );
        return;
      }
      rethrow;
    }
  }

  @override
  Future<Uint8List> previewVoice(String id) async {
    try {
      return await learningClient.audioBytes(
        '/api/v1/speaking/preview',
        payload: {'voice_id': id},
      );
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        return await learningClient.audioBytes(
          '/api/v1/admin/speaking/preview',
          payload: {'voice_id': id},
        );
      }
      rethrow;
    }
  }

  @override
  Future<SpeakingResult> submitSpeaking({
    required String requestId,
    required String cardId,
    required String voiceId,
    required Uint8List audio,
    String? prompt,
  }) async {
    final params = {'card_id': cardId, 'voice_id': voiceId};
    if (prompt != null && prompt.isNotEmpty) {
      params['prompt'] = prompt;
    }
    final query = Uri(queryParameters: params).query;
    try {
      final response = await learningClient.postMultipart(
        '/api/v1/speaking/attempts/$requestId?$query',
        fieldName: 'audio',
        filename: 'recording.wav',
        mediaType: 'audio/wav',
        bytes: audio,
      );
      return SpeakingResult.fromJson(_json(response.body));
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        final response = await learningClient.postMultipart(
          '/api/v1/admin/speaking/attempts/$requestId?$query',
          fieldName: 'audio',
          filename: 'recording.wav',
          mediaType: 'audio/wav',
          bytes: audio,
        );
        return SpeakingResult.fromJson(_json(response.body));
      }
      rethrow;
    }
  }

  @override
  Future<List<SpeakingResult>> loadSpeakingHistory() async {
    try {
      final res = await learningClient.getJson('/api/v1/speaking/history');
      return _items(res.body, SpeakingResult.fromJson);
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        final res = await learningClient.getJson('/api/v1/admin/speaking/history');
        return _items(res.body, SpeakingResult.fromJson);
      }
      rethrow;
    }
  }

  @override
  Future<Uint8List> loadSpeakingAudio(String id) async {
    try {
      return await learningClient.audioBytes(
        '/api/v1/speaking/attempts/$id/audio',
        payload: {},
      );
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        return await learningClient.audioBytes(
          '/api/v1/admin/speaking/attempts/$id/audio',
          payload: {},
        );
      }
      rethrow;
    }
  }
  @override
  Future<Uint8List> loadSampleAudio(String url) =>
      learningClient.audioBytes(url);
  @override
  Future<Uint8List> loadCardAudio(String cardId) =>
      learningClient.audioBytes('/api/v1/flashcards/cards/$cardId/audio');
}
