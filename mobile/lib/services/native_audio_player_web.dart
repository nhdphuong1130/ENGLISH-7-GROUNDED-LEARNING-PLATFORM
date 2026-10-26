import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';

class NativeAudioPlayer {
  static final AudioPlayer _player = AudioPlayer();

  static Future<bool> play(String url) async {
    try {
      await _player.play(UrlSource(url));
      return true;
    } catch (error) {
      debugPrint('Browser audio play error: $error');
      return false;
    }
  }

  static Future<void> pause() => _player.pause();

  static Future<void> stop() => _player.stop();

  static Future<void> seek(int positionMs) =>
      _player.seek(Duration(milliseconds: positionMs));

  static Future<Map<String, dynamic>> getStatus() async {
    final position = await _player.getCurrentPosition();
    final duration = await _player.getDuration();
    return {
      'isPlaying': _player.state == PlayerState.playing,
      'position': position?.inMilliseconds ?? 0,
      'duration': duration?.inMilliseconds ?? 0,
    };
  }
}
