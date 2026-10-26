import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';

class SecureTokenStore implements TokenStore, DeviceIdentityStore {
  static const _tokenKey = 'access_token';
  static const _deviceIdKey = 'device_id';
  final FlutterSecureStorage _storage;

  const SecureTokenStore([this._storage = const FlutterSecureStorage()]);

  @override
  Future<void> clear() => _storage.delete(key: _tokenKey);

  @override
  Future<String?> read() => _storage.read(key: _tokenKey);

  @override
  Future<void> write(String token) =>
      _storage.write(key: _tokenKey, value: token);

  @override
  Future<String> getOrCreateDeviceId() async {
    final existing = await _storage.read(key: _deviceIdKey);
    if (existing != null && existing.length >= 16) return existing;
    final random = Random.secure();
    final bytes = List<int>.generate(24, (_) => random.nextInt(256));
    final created = base64UrlEncode(bytes).replaceAll('=', '');
    await _storage.write(key: _deviceIdKey, value: created);
    return created;
  }
}
