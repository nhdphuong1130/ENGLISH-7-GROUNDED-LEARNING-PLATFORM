import 'dart:typed_data';

import 'package:english7_mobile/api/http_transport.dart';
import 'package:english7_mobile/api/http_transport_web.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('browser transport preserves binary request and response data', () async {
    final client = MockClient.streaming((request, bodyStream) async {
      expect(request.method, 'POST');
      expect(request.url, Uri.parse('https://example.test/api/items?q=1'));
      expect(request.headers['x-test'], 'present');
      expect(await bodyStream.toBytes(), [1, 2, 3]);
      return http.StreamedResponse(
        Stream.value([9, 8, 7]),
        201,
        headers: {'X-Result': 'created'},
      );
    });
    final transport = BrowserHttpTransport(client);

    final response = await transport.send(
      TransportRequest(
        'POST',
        Uri.parse('https://example.test/api/items?q=1'),
        const {'X-Test': 'present'},
        Uint8List.fromList([1, 2, 3]),
      ),
    );

    expect(response.statusCode, 201);
    expect(response.headers, {'x-result': 'created'});
    expect(response.body, [9, 8, 7]);
  });
}
