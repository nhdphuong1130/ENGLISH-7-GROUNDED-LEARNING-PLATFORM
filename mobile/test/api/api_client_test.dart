import 'dart:convert';
import 'dart:typed_data';

import 'package:english7_mobile/api/api_client.dart';
import 'package:english7_mobile/api/api_error.dart';
import 'package:english7_mobile/api/http_transport.dart';
import 'package:english7_mobile/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeTransport implements HttpTransport {
  TransportRequest? request;
  TransportResponse response;

  FakeTransport(this.response);

  @override
  Future<TransportResponse> send(TransportRequest request) async {
    this.request = request;
    return response;
  }
}

class FakeTokenStore implements TokenStore {
  final String? token;
  FakeTokenStore(this.token);

  @override
  Future<String?> read() async => token;

  @override
  Future<void> clear() async {}

  @override
  Future<void> write(String token) async {}
}

void main() {
  final config = AppConfig.fromEnvironment(const {
    'API_BASE_URL': 'https://api.example.test',
    'IMAGE_POLL_INTERVAL_MS': '250',
    'IMAGE_POLL_MAX_ATTEMPTS': '20',
  });

  test('attaches bearer token and parses JSON response', () async {
    final transport = FakeTransport(
      TransportResponse(200, const {
        'x-trace-id': 'trace-success',
      }, Uint8List.fromList(utf8.encode('{"status":"ok"}'))),
    );
    final client = ApiClient(config, transport, FakeTokenStore('token-123'));

    final response = await client.getJson('/api/v1/health');

    expect(response.body, {'status': 'ok'});
    expect(response.traceId, 'trace-success');
    expect(transport.request!.headers['Authorization'], 'Bearer token-123');
    expect(transport.request!.uri.path, '/api/v1/health');
  });

  test('maps standard backend errors and preserves trace ID', () async {
    final transport = FakeTransport(
      TransportResponse(
        422,
        const {'x-trace-id': 'trace-header'},
        Uint8List.fromList(
          utf8.encode(
            jsonEncode({
              'code': 'out_of_scope',
              'message': 'No verified evidence',
              'details': null,
              'trace_id': 'trace-body',
            }),
          ),
        ),
      ),
    );
    final client = ApiClient(config, transport, FakeTokenStore(null));

    await expectLater(
      client.getJson('/api/v1/tutor/ask'),
      throwsA(
        isA<ApiException>()
            .having((error) => error.code, 'code', 'out_of_scope')
            .having((error) => error.traceId, 'traceId', 'trace-body'),
      ),
    );
  });

  test('builds authenticated multipart image request', () async {
    final transport = FakeTransport(
      TransportResponse(
        202,
        const {},
        Uint8List.fromList(utf8.encode('{"id":"upload-1"}')),
      ),
    );
    final client = ApiClient(config, transport, FakeTokenStore('token-123'));

    await client.postMultipart(
      '/api/v1/tutor/images',
      fieldName: 'image',
      filename: 'exercise.png',
      mediaType: 'image/png',
      bytes: Uint8List.fromList([1, 2, 3]),
    );

    final request = transport.request!;
    expect(request.headers['Authorization'], 'Bearer token-123');
    expect(
      request.headers['Content-Type'],
      startsWith('multipart/form-data; boundary='),
    );
    final body = latin1.decode(request.body!);
    expect(body, contains('name="image"; filename="exercise.png"'));
    expect(body, contains('Content-Type: image/png'));
  });

  test('patchJson sends authenticated PATCH payload', () async {
    final transport = FakeTransport(
      TransportResponse(
        200,
        const {},
        Uint8List.fromList(utf8.encode('{"full_name":"Nguyễn An"}')),
      ),
    );
    final client = ApiClient(config, transport, FakeTokenStore('token-123'));

    await client.patchJson('/api/v1/auth/me', {'full_name': 'Nguyễn An'});

    expect(transport.request!.method, 'PATCH');
    expect(transport.request!.headers['Authorization'], 'Bearer token-123');
  });

  test('postNoContent accepts a successful empty response', () async {
    final transport = FakeTransport(
      TransportResponse(204, const {}, Uint8List(0)),
    );
    final client = ApiClient(config, transport, FakeTokenStore('token-123'));

    await client.postNoContent('/api/v1/auth/change-password', {
      'current_password': 'old-password',
      'new_password': 'new-password',
      'confirm_password': 'new-password',
    });

    expect(transport.request!.method, 'POST');
  });

  test('postNoContent maps a standard error response', () async {
    final transport = FakeTransport(
      TransportResponse(
        400,
        const {},
        Uint8List.fromList(
          utf8.encode(
            '{"code":"current_password_invalid","message":"Wrong password"}',
          ),
        ),
      ),
    );
    final client = ApiClient(config, transport, FakeTokenStore('token-123'));

    await expectLater(
      client.postNoContent('/api/v1/auth/change-password', const {}),
      throwsA(
        isA<ApiException>().having(
          (error) => error.code,
          'code',
          'current_password_invalid',
        ),
      ),
    );
  });

  test('handles empty body error response gracefully without FormatException', () async {
    final transport = FakeTransport(
      TransportResponse(502, const {}, Uint8List(0)),
    );
    final client = ApiClient(config, transport, FakeTokenStore(null));

    await expectLater(
      client.postJson('/api/v1/auth/otp/send', {'phone': '+84374423251'}),
      throwsA(
        isA<ApiException>()
            .having((error) => error.statusCode, 'statusCode', 502)
            .having((error) => error.message, 'message', contains('502')),
      ),
    );
  });

  test('handles HTML error response gracefully without FormatException', () async {
    final transport = FakeTransport(
      TransportResponse(
        502,
        const {'content-type': 'text/html'},
        Uint8List.fromList(utf8.encode('<html><body>502 Bad Gateway</body></html>')),
      ),
    );
    final client = ApiClient(config, transport, FakeTokenStore(null));

    await expectLater(
      client.postJson('/api/v1/auth/otp/send', {'phone': '+84374423251'}),
      throwsA(
        isA<ApiException>()
            .having((error) => error.statusCode, 'statusCode', 502)
            .having((error) => error.message, 'message', contains('502')),
      ),
    );
  });
}
