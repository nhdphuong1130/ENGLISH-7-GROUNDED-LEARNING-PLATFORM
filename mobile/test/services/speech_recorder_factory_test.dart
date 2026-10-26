import 'package:english7_mobile/services/speech_recorder.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('creates a speech recorder for the active platform', () {
    expect(createSpeechRecorder(), isA<SpeechRecorder>());
  });
}
