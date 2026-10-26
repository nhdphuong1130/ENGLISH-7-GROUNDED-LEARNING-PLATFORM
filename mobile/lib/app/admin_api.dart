import 'dart:typed_data';

enum AdminStudentStatus { active, locked, archived }

class AdminDashboardSummary {
  final int totalStudents;
  final int activeStudents;
  final int lockedStudents;
  final int archivedStudents;
  final int submittedTests;
  final int draftContent;
  final DateTime? refreshedAt;

  const AdminDashboardSummary({
    required this.totalStudents,
    required this.activeStudents,
    required this.lockedStudents,
    required this.archivedStudents,
    required this.submittedTests,
    required this.draftContent,
    this.refreshedAt,
  });

  factory AdminDashboardSummary.fromJson(Map<String, Object?> json) =>
      AdminDashboardSummary(
        totalStudents: json['total_students'] as int? ?? 0,
        activeStudents: json['active_students'] as int? ?? 0,
        lockedStudents: json['locked_students'] as int? ?? 0,
        archivedStudents: json['archived_students'] as int? ?? 0,
        submittedTests: json['submitted_tests'] as int? ?? 0,
        draftContent: json['draft_content'] as int? ?? 0,
        refreshedAt: json['refreshed_at'] == null
            ? null
            : DateTime.parse(json['refreshed_at'] as String),
      );
}

class AdminStudentRecord {
  final String id;
  final String email;
  final String? fullName;
  final DateTime? dateOfBirth;
  final String? gender;
  final String? schoolName;
  final String? className;
  final bool isActive;
  final DateTime? archivedAt;
  final AdminStudentStatus status;

  const AdminStudentRecord({
    required this.id,
    required this.email,
    this.fullName,
    this.dateOfBirth,
    this.gender,
    this.schoolName,
    this.className,
    required this.isActive,
    this.archivedAt,
    required this.status,
  });

  factory AdminStudentRecord.fromJson(Map<String, Object?> json) =>
      AdminStudentRecord(
        id: json['id'] as String,
        email: json['email'] as String,
        fullName: json['full_name'] as String?,
        dateOfBirth: json['date_of_birth'] == null
            ? null
            : DateTime.parse(json['date_of_birth'] as String),
        gender: json['gender'] as String?,
        schoolName: json['school_name'] as String?,
        className: json['class_name'] as String?,
        isActive: json['is_active'] as bool? ?? false,
        archivedAt: json['archived_at'] == null
            ? null
            : DateTime.parse(json['archived_at'] as String),
        status: AdminStudentStatus.values.byName(
          json['status'] as String? ?? 'active',
        ),
      );
}

class AdminStudentInput {
  final String email;
  final String? password;
  final String? fullName;
  final DateTime? dateOfBirth;
  final String? gender;
  final String? schoolName;
  final String? className;

  const AdminStudentInput({
    required this.email,
    this.password,
    this.fullName,
    this.dateOfBirth,
    this.gender,
    this.schoolName,
    this.className,
  });

  Map<String, Object?> toJson({required bool includePassword}) => {
    'email': email,
    if (includePassword) 'password': password,
    'full_name': fullName,
    'date_of_birth': dateOfBirth?.toIso8601String().split('T').first,
    'gender': gender,
    'school_name': schoolName,
    'class_name': className,
  };
}

class AdminStudentPage {
  final List<AdminStudentRecord> items;
  final int count;
  final int offset;
  final int limit;
  const AdminStudentPage(this.items, this.count, this.offset, this.limit);
}

class AdminImportFile {
  final String filename;
  final String mediaType;
  final Uint8List bytes;
  const AdminImportFile(this.filename, this.mediaType, this.bytes);
}

class AdminImportError {
  final int row;
  final String code;
  final String message;
  const AdminImportError(this.row, this.code, this.message);

  factory AdminImportError.fromJson(Map<String, Object?> json) =>
      AdminImportError(
        json['row'] as int? ?? 0,
        json['code'] as String? ?? 'invalid_row',
        json['message'] as String? ?? '',
      );
}

class AdminImportReport {
  final int validRows;
  final int created;
  final bool applied;
  final List<AdminImportError> errors;
  const AdminImportReport(
    this.validRows,
    this.created,
    this.applied,
    this.errors,
  );
}

class AdminContentRecord {
  final String id;
  final int version;
  final String status;
  final Map<String, Object?> values;
  const AdminContentRecord(this.id, this.version, this.status, this.values);

  int get childCount => values['child_count'] as int? ?? 0;

  factory AdminContentRecord.fromJson(Map<String, Object?> json) =>
      AdminContentRecord(
        json['id'] as String,
        json['version'] as int? ?? 0,
        json['status'] as String? ?? 'draft',
        Map.unmodifiable(json),
      );
}

class AdminRevision {
  final int version;
  final String status;
  final Map<String, Object?> snapshot;
  final DateTime? createdAt;
  const AdminRevision(this.version, this.status, this.snapshot, this.createdAt);

  factory AdminRevision.fromJson(Map<String, Object?> json) => AdminRevision(
    json['version'] as int,
    json['status'] as String,
    Map<String, Object?>.from(json['snapshot'] as Map),
    json['created_at'] == null
        ? null
        : DateTime.parse(json['created_at'] as String),
  );
}

class AdminAuditRecord {
  final String id;
  final String action;
  final String entityType;
  final String entityId;
  final DateTime createdAt;
  final Map<String, Object?>? before;
  final Map<String, Object?>? after;
  const AdminAuditRecord({
    required this.id,
    required this.action,
    required this.entityType,
    required this.entityId,
    required this.createdAt,
    this.before,
    this.after,
  });

  factory AdminAuditRecord.fromJson(Map<String, Object?> json) =>
      AdminAuditRecord(
        id: json['id'] as String,
        action: json['action'] as String,
        entityType: json['entity_type'] as String,
        entityId: json['entity_id'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        before: json['before_data'] == null
            ? null
            : Map<String, Object?>.from(json['before_data'] as Map),
        after: json['after_data'] == null
            ? null
            : Map<String, Object?>.from(json['after_data'] as Map),
      );
}

abstract interface class AdminApi {
  Future<AdminDashboardSummary> loadAdminDashboard();
  Future<AdminStudentPage> loadAdminStudents({
    String? query,
    AdminStudentStatus? status,
    int offset = 0,
    int limit = 50,
  });
  Future<AdminStudentRecord> loadAdminStudent(String id);
  Future<AdminStudentRecord> createAdminStudent(AdminStudentInput input);
  Future<AdminStudentRecord> updateAdminStudent(
    String id,
    AdminStudentInput input,
  );
  Future<void> resetAdminStudentPassword(String id, String password);
  Future<AdminStudentRecord> lockAdminStudent(String id);
  Future<AdminStudentRecord> unlockAdminStudent(String id);
  Future<AdminStudentRecord> archiveAdminStudent(
    String id,
    String confirmation,
  );
  Future<AdminStudentRecord> restoreAdminStudent(String id);
  Future<void> deleteAdminStudent(String id, String confirmation);
  Future<AdminImportReport> importAdminStudents(
    AdminImportFile file, {
    bool dryRun = true,
  });
  Future<Uint8List> exportAdminStudentAccounts(String format);
  Future<List<AdminContentRecord>> loadAdminResource(
    String path, {
    Map<String, Object?> query = const {},
  });
  Future<AdminContentRecord> createAdminResource(
    String path,
    Map<String, Object?> payload,
  );
  Future<AdminContentRecord> updateAdminResource(
    String path,
    Map<String, Object?> payload,
  );
  Future<AdminContentRecord> runAdminResourceAction(
    String path, {
    Map<String, Object?> payload = const {},
  });
  Future<void> deleteAdminResource(String path, {String? confirmation});
  Future<List<AdminRevision>> loadAdminRevisions(String path);
  Future<List<AdminAuditRecord>> loadAdminAudit({
    int offset = 0,
    int limit = 50,
  });
}

mixin EmptyAdminApi implements AdminApi {
  Never _unsupported() => throw UnsupportedError('Admin API is not configured');
  @override
  Future<AdminDashboardSummary> loadAdminDashboard() async => _unsupported();
  @override
  Future<AdminStudentPage> loadAdminStudents({
    String? query,
    AdminStudentStatus? status,
    int offset = 0,
    int limit = 50,
  }) async => _unsupported();
  @override
  Future<AdminStudentRecord> loadAdminStudent(String id) async =>
      _unsupported();
  @override
  Future<AdminStudentRecord> createAdminStudent(
    AdminStudentInput input,
  ) async => _unsupported();
  @override
  Future<AdminStudentRecord> updateAdminStudent(
    String id,
    AdminStudentInput input,
  ) async => _unsupported();
  @override
  Future<void> resetAdminStudentPassword(String id, String password) async =>
      _unsupported();
  @override
  Future<AdminStudentRecord> lockAdminStudent(String id) async =>
      _unsupported();
  @override
  Future<AdminStudentRecord> unlockAdminStudent(String id) async =>
      _unsupported();
  @override
  Future<AdminStudentRecord> archiveAdminStudent(
    String id,
    String confirmation,
  ) async => _unsupported();
  @override
  Future<AdminStudentRecord> restoreAdminStudent(String id) async =>
      _unsupported();
  @override
  Future<void> deleteAdminStudent(String id, String confirmation) async =>
      _unsupported();
  @override
  Future<AdminImportReport> importAdminStudents(
    AdminImportFile file, {
    bool dryRun = true,
  }) async => _unsupported();
  @override
  Future<Uint8List> exportAdminStudentAccounts(String format) async =>
      _unsupported();
  @override
  Future<List<AdminContentRecord>> loadAdminResource(
    String path, {
    Map<String, Object?> query = const {},
  }) async => _unsupported();
  @override
  Future<AdminContentRecord> createAdminResource(
    String path,
    Map<String, Object?> payload,
  ) async => _unsupported();
  @override
  Future<AdminContentRecord> updateAdminResource(
    String path,
    Map<String, Object?> payload,
  ) async => _unsupported();
  @override
  Future<AdminContentRecord> runAdminResourceAction(
    String path, {
    Map<String, Object?> payload = const {},
  }) async => _unsupported();
  @override
  Future<void> deleteAdminResource(String path, {String? confirmation}) async =>
      _unsupported();
  @override
  Future<List<AdminRevision>> loadAdminRevisions(String path) async =>
      _unsupported();
  @override
  Future<List<AdminAuditRecord>> loadAdminAudit({
    int offset = 0,
    int limit = 50,
  }) async => _unsupported();
}
