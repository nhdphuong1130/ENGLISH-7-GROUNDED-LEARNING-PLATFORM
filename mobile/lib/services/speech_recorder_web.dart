import 'dart:async';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:record/record.dart';

import 'speech_recorder.dart';
import 'wav_audio.dart';

SpeechRecorder createSpeechRecorder() => WebSpeechRecorder();

class WebSpeechRecorder implements SpeechRecorder {
  static const _sampleRate = 16000;
  static const _maxPcmBytes = _sampleRate * 2 * 15;

  final AudioRecorder _recorder;
  final AudioPlayer _player;
  final BytesBuilder _buffer = BytesBuilder(copy: false);
  StreamSubscription<Uint8List>? _subscription;
  Completer<void>? _streamDone;
  bool _recording = false;
  bool _overflow = false;

  WebSpeechRecorder({AudioRecorder? recorder, AudioPlayer? player})
    : _recorder = recorder ?? AudioRecorder(),
      _player = player ?? AudioPlayer();

  @override
  Future<void> start() async {
    if (_recording) {
      throw const SpeechRecordingException('Một bản thu đang được thực hiện.');
    }
    try {
      if (!await _recorder.hasPermission()) {
        throw const SpeechRecordingException(
          'Safari chưa có quyền microphone. Hãy cho phép Microphone rồi thử lại.',
        );
      }
      _buffer.clear();
      _overflow = false;
      _streamDone = Completer<void>();
      final stream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: _sampleRate,
          numChannels: 1,
          autoGain: true,
          echoCancel: true,
          noiseSuppress: true,
        ),
      );
      _recording = true;
      _subscription = stream.listen(
        (chunk) {
          if (_buffer.length + chunk.length <= _maxPcmBytes) {
            _buffer.add(chunk);
          } else {
            _overflow = true;
          }
        },
        onError: (Object error, StackTrace stack) {
          if (!(_streamDone?.isCompleted ?? true)) {
            _streamDone!.completeError(error, stack);
          }
        },
        onDone: () {
          if (!(_streamDone?.isCompleted ?? true)) _streamDone!.complete();
        },
      );
    } on SpeechRecordingException {
      rethrow;
    } catch (_) {
      throw const SpeechRecordingException(
        'Không thể mở microphone trên Safari. Vui lòng thử lại.',
      );
    }
  }

  @override
  Future<Uint8List> stop() async {
    if (!_recording) {
      throw const SpeechRecordingException('Chưa bắt đầu thu âm.');
    }
    try {
      await _recorder.stop();
      await _streamDone?.future.timeout(const Duration(seconds: 2));
      final pcm = _buffer.takeBytes();
      if (_overflow) {
        throw const SpeechRecordingException(
          'Bản thu quá dài. Vui lòng thu lại trong tối đa 15 giây.',
        );
      }
      if (pcm.isEmpty) {
        throw const SpeechRecordingException('Bản thu trống. Vui lòng thu lại.');
      }
      return pcm16ToWav(pcm, sampleRate: _sampleRate, channels: 1);
    } on SpeechRecordingException {
      rethrow;
    } catch (_) {
      throw const SpeechRecordingException(
        'Không thể hoàn tất bản thu. Vui lòng thử lại.',
      );
    } finally {
      _recording = false;
      await _subscription?.cancel();
      _subscription = null;
      _streamDone = null;
    }
  }

  @override
  Future<void> play(Uint8List bytes) =>
      _player.play(BytesSource(bytes, mimeType: 'audio/wav'));

  @override
  Future<void> dispose() async {
    if (_recording) await _recorder.cancel();
    _recording = false;
    await _subscription?.cancel();
    await _recorder.dispose();
    await _player.dispose();
  }
}
