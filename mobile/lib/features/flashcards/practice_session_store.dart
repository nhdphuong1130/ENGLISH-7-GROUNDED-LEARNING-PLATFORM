import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class PracticeSessionState {
  final String deckId;
  final String mode; // 'flashcard' | 'speaking_word' | 'speaking_sentence'
  final int currentIndex;
  final int totalCards;
  final List<String> ratings;
  final List<double> scores;
  final List<int> attempts;
  final DateTime updatedAt;

  const PracticeSessionState({
    required this.deckId,
    required this.mode,
    required this.currentIndex,
    required this.totalCards,
    required this.ratings,
    required this.scores,
    required this.attempts,
    required this.updatedAt,
  });

  Map<String, dynamic> toJson() => {
    'deckId': deckId,
    'mode': mode,
    'currentIndex': currentIndex,
    'totalCards': totalCards,
    'ratings': ratings,
    'scores': scores,
    'attempts': attempts,
    'updatedAt': updatedAt.toIso8601String(),
  };

  factory PracticeSessionState.fromJson(Map<String, dynamic> json) {
    return PracticeSessionState(
      deckId: json['deckId'] as String? ?? '',
      mode: json['mode'] as String? ?? '',
      currentIndex: (json['currentIndex'] as num?)?.toInt() ?? 0,
      totalCards: (json['totalCards'] as num?)?.toInt() ?? 0,
      ratings: (json['ratings'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      scores: (json['scores'] as List<dynamic>?)
              ?.map((e) => (e as num).toDouble())
              .toList() ??
          [],
      attempts: (json['attempts'] as List<dynamic>?)
              ?.map((e) => (e as num).toInt())
              .toList() ??
          [],
      updatedAt: json['updatedAt'] != null
          ? DateTime.tryParse(json['updatedAt'] as String) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class PracticeSessionStore {
  final FlutterSecureStorage storage;

  const PracticeSessionStore({this.storage = const FlutterSecureStorage()});

  String _key(String deckId, String mode) => 'practice_session_${deckId}_$mode';

  Future<void> save(PracticeSessionState state) async {
    final key = _key(state.deckId, state.mode);
    final jsonStr = jsonEncode(state.toJson());
    await storage.write(key: key, value: jsonStr);
  }

  Future<PracticeSessionState?> load(String deckId, String mode) async {
    final key = _key(deckId, mode);
    final jsonStr = await storage.read(key: key);
    if (jsonStr == null || jsonStr.trim().isEmpty) {
      return null;
    }
    try {
      final decoded = jsonDecode(jsonStr);
      if (decoded is Map<String, dynamic>) {
        return PracticeSessionState.fromJson(decoded);
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  Future<void> clear(String deckId, String mode) async {
    final key = _key(deckId, mode);
    await storage.delete(key: key);
  }
}
