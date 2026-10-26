import 'dart:typed_data';

import 'http_transport_io.dart'
    if (dart.library.html) 'http_transport_web.dart' as platform;

class TransportRequest {
  final String method;
  final Uri uri;
  final Map<String, String> headers;
  final Uint8List? body;

  const TransportRequest(this.method, this.uri, this.headers, this.body);
}

class TransportResponse {
  final int statusCode;
  final Map<String, String> headers;
  final Uint8List body;

  const TransportResponse(this.statusCode, this.headers, this.body);
}

abstract interface class HttpTransport {
  Future<TransportResponse> send(TransportRequest request);
}

HttpTransport createHttpTransport() => platform.createHttpTransport();
