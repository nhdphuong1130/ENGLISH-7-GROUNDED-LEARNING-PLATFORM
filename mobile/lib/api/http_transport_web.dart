import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'http_transport.dart';

HttpTransport createHttpTransport() => BrowserHttpTransport();

class BrowserHttpTransport implements HttpTransport {
  final http.Client _client;

  BrowserHttpTransport([http.Client? client]) : _client = client ?? http.Client();

  @override
  Future<TransportResponse> send(TransportRequest request) async {
    final outgoing = http.Request(request.method, request.uri)
      ..headers.addAll(request.headers);
    if (request.body != null) outgoing.bodyBytes = request.body!;

    final incoming = await _client.send(outgoing);
    final body = await incoming.stream.toBytes();
    return TransportResponse(
      incoming.statusCode,
      {
        for (final entry in incoming.headers.entries)
          entry.key.toLowerCase(): entry.value,
      },
      Uint8List.fromList(body),
    );
  }
}
