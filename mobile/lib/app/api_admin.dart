import 'dart:typed_data';

import '../api/api_client.dart';
import 'admin_api.dart';

mixin ApiAdmin implements AdminApi {
  ApiClient get adminClient;

  String _query(String path, Map<String, Object?> values) {
    final filtered = <String, String>{
      for (final entry in values.entries)
        if (entry.value != null && entry.value.toString().isNotEmpty)
          entry.key: entry.value.toString(),
    };
    return Uri(path: path, queryParameters: filtered).toString();
  }

  AdminStudentRecord _student(Map<String, Object?> body) =>
      AdminStudentRecord.fromJson(body);

  @override
  Future<AdminDashboardSummary> loadAdminDashboard() async =>
      AdminDashboardSummary.fromJson(
        (await adminClient.getJson('/api/v1/admin/dashboard')).body,
      );

  @override
  Future<AdminStudentPage> loadAdminStudents({
    String? query,
    AdminStudentStatus? status,
    int offset = 0,
    int limit = 50,
  }) async {
    final response = await adminClient.getJson(
      _query('/api/v1/admin/students', {
        'q': query,
        'status': status?.name ?? 'all',
        'offset': offset,
        'limit': limit,
      }),
    );
    final body = response.body;
    final items = (body['items'] as List? ?? [])
        .map(
          (item) => AdminStudentRecord.fromJson(
            Map<String, Object?>.from(item as Map),
          ),
        )
        .toList(growable: false);
    return AdminStudentPage(
      items,
      body['count'] as int? ?? items.length,
      body['offset'] as int? ?? offset,
      body['limit'] as int? ?? limit,
    );
  }

  @override
  Future<AdminStudentRecord> loadAdminStudent(String id) async => _student(
    (await adminClient.getJson(
      '/api/v1/admin/students/${Uri.encodeComponent(id)}',
    )).body,
  );

  @override
  Future<AdminStudentRecord> createAdminStudent(
    AdminStudentInput input,
  ) async => _student(
    (await adminClient.postJson(
      '/api/v1/admin/students',
      input.toJson(includePassword: true),
    )).body,
  );

  @override
  Future<AdminStudentRecord> updateAdminStudent(
    String id,
    AdminStudentInput input,
  ) async => _student(
    (await adminClient.patchJson(
      '/api/v1/admin/students/${Uri.encodeComponent(id)}',
      input.toJson(includePassword: false),
    )).body,
  );

  @override
  Future<void> resetAdminStudentPassword(String id, String password) =>
      adminClient.postNoContent(
        '/api/v1/admin/students/${Uri.encodeComponent(id)}/reset-password',
        {'new_password': password},
      );

  Future<AdminStudentRecord> _studentAction(
    String id,
    String action, [
    Map<String, Object?> payload = const {},
  ]) async => _student(
    (await adminClient.postJson(
      '/api/v1/admin/students/${Uri.encodeComponent(id)}/$action',
      payload,
    )).body,
  );

  @override
  Future<AdminStudentRecord> lockAdminStudent(String id) =>
      _studentAction(id, 'lock');
  @override
  Future<AdminStudentRecord> unlockAdminStudent(String id) =>
      _studentAction(id, 'unlock');
  @override
  Future<AdminStudentRecord> archiveAdminStudent(
    String id,
    String confirmation,
  ) => _studentAction(id, 'archive', {'confirmation': confirmation});
  @override
  Future<AdminStudentRecord> restoreAdminStudent(String id) =>
      _studentAction(id, 'restore');

  @override
  Future<void> deleteAdminStudent(String id, String confirmation) =>
      adminClient.delete(
        _query('/api/v1/admin/students/${Uri.encodeComponent(id)}', {
          'confirmation': confirmation,
        }),
      );

  @override
  Future<AdminImportReport> importAdminStudents(
    AdminImportFile file, {
    bool dryRun = true,
  }) async {
    final body = (await adminClient.postMultipart(
      _query('/api/v1/admin/students/import', {'dry_run': dryRun}),
      fieldName: 'file',
      filename: file.filename,
      mediaType: file.mediaType,
      bytes: file.bytes,
    )).body;
    return AdminImportReport(
      body['valid_rows'] as int? ?? 0,
      body['created'] as int? ?? 0,
      body['applied'] as bool? ?? false,
      (body['errors'] as List? ?? [])
          .map(
            (item) => AdminImportError.fromJson(
              Map<String, Object?>.from(item as Map),
            ),
          )
          .toList(growable: false),
    );
  }

  @override
  Future<Uint8List> exportAdminStudentAccounts(String format) =>
      adminClient.downloadBytes(
        _query('/api/v1/admin/students/accounts/export', {'format': format}),
      );

  @override
  Future<List<AdminContentRecord>> loadAdminResource(
    String path, {
    Map<String, Object?> query = const {},
  }) async {
    final body = (await adminClient.getJson(_query(path, query))).body;
    return (body['items'] as List? ?? [])
        .map(
          (item) => AdminContentRecord.fromJson(
            Map<String, Object?>.from(item as Map),
          ),
        )
        .toList(growable: false);
  }

  @override
  Future<AdminContentRecord> createAdminResource(
    String path,
    Map<String, Object?> payload,
  ) async => AdminContentRecord.fromJson(
    (await adminClient.postJson(path, payload)).body,
  );

  @override
  Future<AdminContentRecord> updateAdminResource(
    String path,
    Map<String, Object?> payload,
  ) async => AdminContentRecord.fromJson(
    (await adminClient.patchJson(path, payload)).body,
  );

  @override
  Future<AdminContentRecord> runAdminResourceAction(
    String path, {
    Map<String, Object?> payload = const {},
  }) async => AdminContentRecord.fromJson(
    (await adminClient.postJson(path, payload)).body,
  );

  @override
  Future<void> deleteAdminResource(String path, {String? confirmation}) =>
      adminClient.delete(
        confirmation == null
            ? path
            : _query(path, {'confirmation': confirmation}),
      );

  @override
  Future<List<AdminRevision>> loadAdminRevisions(String path) async {
    final body = (await adminClient.getJson(path)).body;
    return (body['items'] as List? ?? [])
        .map(
          (item) =>
              AdminRevision.fromJson(Map<String, Object?>.from(item as Map)),
        )
        .toList(growable: false);
  }

  @override
  Future<List<AdminAuditRecord>> loadAdminAudit({
    int offset = 0,
    int limit = 50,
  }) async {
    final body = (await adminClient.getJson(
      _query('/api/v1/admin/audit-events', {'offset': offset, 'limit': limit}),
    )).body;
    return (body['items'] as List? ?? [])
        .map(
          (item) =>
              AdminAuditRecord.fromJson(Map<String, Object?>.from(item as Map)),
        )
        .toList(growable: false);
  }
}
