import 'dart:convert';
import 'dart:typed_data';

import 'package:english7_mobile/services/wav_audio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('wraps mono PCM16 samples in a valid 16 kHz WAV container', () {
    final pcm = Uint8List.fromList([1, 2, 3, 4]);

    final wav = pcm16ToWav(pcm, sampleRate: 16000, channels: 1);
    final data = ByteData.sublistView(wav);

    expect(ascii.decode(wav.sublist(0, 4)), 'RIFF');
    expect(data.getUint32(4, Endian.little), 40);
    expect(ascii.decode(wav.sublist(8, 12)), 'WAVE');
    expect(data.getUint16(22, Endian.little), 1);
    expect(data.getUint32(24, Endian.little), 16000);
    expect(data.getUint16(34, Endian.little), 16);
    expect(data.getUint32(40, Endian.little), pcm.length);
    expect(wav.sublist(44), pcm);
  });
}
