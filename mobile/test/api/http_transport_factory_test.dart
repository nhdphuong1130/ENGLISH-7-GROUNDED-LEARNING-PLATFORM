import 'package:english7_mobile/api/http_transport.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('creates an HTTP transport for the active platform', () {
    expect(createHttpTransport(), isA<HttpTransport>());
  });
}
