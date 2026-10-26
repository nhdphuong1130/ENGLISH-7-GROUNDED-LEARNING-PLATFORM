import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

class NativeAudioPlayer {
  static const MethodChannel _channel = MethodChannel('vn.english7/audio_player');

  static Future<bool> play(String url) async {
    try {
      final res = await _channel.invokeMethod<Map>('play', {'url': url});
      return res != null;
    } catch (e) {
      debugPrint('NativeAudioPlayer play error: $e');
      return false;
    }
  }

  static Future<void> pause() async {
    try {
      await _channel.invokeMethod('pause');
    } catch (e) {
      debugPrint('NativeAudioPlayer pause error: $e');
    }
  }

  static Future<void> stop() async {
    try {
      await _channel.invokeMethod('stop');
    } catch (e) {
      debugPrint('NativeAudioPlayer stop error: $e');
    }
  }

  static Future<void> seek(int positionMs) async {
    try {
      await _channel.invokeMethod('seek', {'position': positionMs});
    } catch (e) {
      debugPrint('NativeAudioPlayer seek error: $e');
    }
  }

  static Future<Map<String, dynamic>> getStatus() async {
    try {
      final res = await _channel.invokeMethod<Map>('getStatus');
      if (res != null) return Map<String, dynamic>.from(res);
    } catch (_) {
      // The UI treats an unavailable player as stopped.
    }
    return {'isPlaying': false, 'position': 0, 'duration': 0};
  }
}
