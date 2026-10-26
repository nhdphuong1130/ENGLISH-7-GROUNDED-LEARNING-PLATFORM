import 'dart:io';
import 'dart:typed_data';

import 'http_transport.dart';

HttpTransport createHttpTransport() => IOHttpTransport();

class IOHttpTransport implements HttpTransport {
  final HttpClient _client;
  String? _hostOverride;

  IOHttpTransport([HttpClient? client]) : _client = client ?? HttpClient();

  @override
  Future<TransportResponse> send(TransportRequest request) async {
    var effectiveUri = request.uri;
    if (_hostOverride != null && effectiveUri.host != _hostOverride) {
      effectiveUri = effectiveUri.replace(host: _hostOverride);
    }

    try {
      return await _execute(request, effectiveUri);
    } on SocketException {
      final altHost = effectiveUri.host == '10.0.2.2'
          ? '127.0.0.1'
          : (effectiveUri.host == '127.0.0.1' ? '10.0.2.2' : null);
      if (altHost != null) {
        final altUri = effectiveUri.replace(host: altHost);
        final res = await _execute(request, altUri);
        _hostOverride = altHost;
        return res;
      }
      rethrow;
    }
  }

  Future<TransportResponse> _execute(
    TransportRequest request,
    Uri uri,
  ) async {
    final outgoing = await _client.openUrl(request.method, uri);
    request.headers.forEach(outgoing.headers.set);
    if (request.body != null) outgoing.add(request.body!);
    final incoming = await outgoing.close();
    final chunks = <int>[];
    await for (final chunk in incoming) {
      chunks.addAll(chunk);
    }
    final headers = <String, String>{};
    incoming.headers.forEach((name, values) {
      headers[name.toLowerCase()] = values.join(',');
    });
    return TransportResponse(
      incoming.statusCode,
      headers,
      Uint8List.fromList(chunks),
    );
  }
}
