import 'dart:convert';
import 'dart:typed_data';

Uint8List pcm16ToWav(
  Uint8List pcm, {
  required int sampleRate,
  required int channels,
}) {
  final output = Uint8List(44 + pcm.length);
  final data = ByteData.sublistView(output);

  output.setRange(0, 4, ascii.encode('RIFF'));
  data.setUint32(4, 36 + pcm.length, Endian.little);
  output.setRange(8, 12, ascii.encode('WAVE'));
  output.setRange(12, 16, ascii.encode('fmt '));
  data.setUint32(16, 16, Endian.little);
  data.setUint16(20, 1, Endian.little);
  data.setUint16(22, channels, Endian.little);
  data.setUint32(24, sampleRate, Endian.little);
  data.setUint32(28, sampleRate * channels * 2, Endian.little);
  data.setUint16(32, channels * 2, Endian.little);
  data.setUint16(34, 16, Endian.little);
  output.setRange(36, 40, ascii.encode('data'));
  data.setUint32(40, pcm.length, Endian.little);
  output.setRange(44, output.length, pcm);
  return output;
}
