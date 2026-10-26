import 'dart:typed_data';

import 'speech_recorder_android.dart'
    if (dart.library.html) 'speech_recorder_web.dart' as platform;

abstract interface class SpeechRecorder {
  Future<void> start();
  Future<Uint8List> stop();
  Future<void> play(Uint8List bytes);
  Future<void> dispose();
}

SpeechRecorder createSpeechRecorder() => platform.createSpeechRecorder();

class SpeechRecordingException implements Exception {
  final String message;
  const SpeechRecordingException(this.message);

  @override
  String toString() => message;
}
