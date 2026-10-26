import '../../../app/admin_api.dart';

enum AdminContentKind {
  unit,
  section,
  activity,
  fragment,
  blueprint,
  question,
  deck,
  card,
}

class AdminContentSchema {
  final String label;
  final String listPath;
  final Map<String, Object?> query;
  final AdminContentKind kind;
  final String entityType;
  final String basePath;
  final String versionBasePath;
  final String createPath;
  final Map<String, Object?> createDefaults;
  final AdminContentSchema? Function(AdminContentRecord item)? child;

  const AdminContentSchema({
    required this.label,
    required this.listPath,
    required this.kind,
    required this.entityType,
    required this.basePath,
    required this.versionBasePath,
    String? createPath,
    this.createDefaults = const {},
    this.query = const {},
    this.child,
  }) : createPath = createPath ?? listPath;

  String title(AdminContentRecord item) => switch (kind) {
    AdminContentKind.activity =>
      'Activity ${item.values['number'] ?? ''}'.trim(),
    AdminContentKind.fragment =>
      (item.values['normalized_text'] ?? 'Đoạn nội dung ${item.id}').toString(),
    AdminContentKind.question =>
      (item.values['prompt'] ?? 'Câu hỏi ${item.id}').toString(),
    _ =>
      (item.values['title'] ??
              item.values['name'] ??
              item.values['word'] ??
              'Nội dung ${item.id}')
          .toString(),
  };

  String? subtitle(AdminContentRecord item) => switch (kind) {
    AdminContentKind.section => item.values['section_type']?.toString(),
    AdminContentKind.activity => item.values['instruction']?.toString(),
    AdminContentKind.fragment =>
      item.values['printed_page'] == null
          ? null
          : 'Trang SGK ${item.values['printed_page']}',
    AdminContentKind.blueprint =>
      '${item.values['duration_minutes'] ?? 0} phút • ${item.values['difficulty'] ?? ''}',
    AdminContentKind.question => item.values['question_type']?.toString(),
    AdminContentKind.deck =>
      item.childCount == 0 ? 'Chưa có thẻ' : '${item.childCount} thẻ',
    AdminContentKind.card => item.values['meaning']?.toString(),
    AdminContentKind.unit =>
      item.childCount == 0
          ? 'Chưa có mục bài học'
          : '${item.childCount} mục bài học',
  };
}

AdminContentSchema _activities(AdminContentRecord section) =>
    AdminContentSchema(
      label: 'Hoạt động • ${section.values['title'] ?? ''}',
      listPath: '/api/v1/admin/content/sections/${section.id}/activities',
      kind: AdminContentKind.activity,
      entityType: 'activity',
      basePath: '/api/v1/admin/content/activities',
      versionBasePath: '/api/v1/admin/content',
      createPath: '/api/v1/admin/content/sections/${section.id}/activities',
      child: (activity) => AdminContentSchema(
        label: 'Nội dung • Activity ${activity.values['number'] ?? ''}',
        listPath: '/api/v1/admin/content/fragments',
        query: {'activity_id': activity.id},
        kind: AdminContentKind.fragment,
        entityType: 'fragment',
        basePath: '/api/v1/admin/content/fragments',
        versionBasePath: '/api/v1/admin/content',
        createPath: '/api/v1/admin/content/fragments',
        createDefaults: {'activity_id': activity.id},
      ),
    );

AdminContentSchema _sections(AdminContentRecord unit) => AdminContentSchema(
  label: 'Mục bài học • ${unit.values['title'] ?? ''}',
  listPath: '/api/v1/admin/content/units/${unit.id}/sections',
  kind: AdminContentKind.section,
  entityType: 'section',
  basePath: '/api/v1/admin/content/sections',
  versionBasePath: '/api/v1/admin/content',
  createPath: '/api/v1/admin/content/units/${unit.id}/sections',
  child: _activities,
);

AdminContentSchema _cards(AdminContentRecord deck) => AdminContentSchema(
  label: 'Thẻ • ${deck.values['name'] ?? ''}',
  listPath: '/api/v1/admin/practice/decks/${deck.id}/cards',
  kind: AdminContentKind.card,
  entityType: 'flashcard',
  basePath: '/api/v1/admin/practice/cards',
  versionBasePath: '/api/v1/admin/practice',
  createPath: '/api/v1/admin/practice/decks/${deck.id}/cards',
);

final adminRootSchemas = <AdminContentSchema>[
  AdminContentSchema(
    label: 'Unit sách giáo khoa',
    listPath: '/api/v1/admin/content/units',
    kind: AdminContentKind.unit,
    entityType: 'unit',
    basePath: '/api/v1/admin/content/units',
    versionBasePath: '/api/v1/admin/content',
    child: _sections,
  ),
  const AdminContentSchema(
    label: 'Mẫu bài kiểm tra',
    listPath: '/api/v1/admin/practice/quiz-blueprints',
    kind: AdminContentKind.blueprint,
    entityType: 'quiz_blueprint',
    basePath: '/api/v1/admin/practice/quiz-blueprints',
    versionBasePath: '/api/v1/admin/practice',
  ),
  const AdminContentSchema(
    label: 'Ngân hàng câu hỏi',
    listPath: '/api/v1/admin/practice/questions',
    kind: AdminContentKind.question,
    entityType: 'quiz_question',
    basePath: '/api/v1/admin/practice/questions',
    versionBasePath: '/api/v1/admin/practice',
  ),
  AdminContentSchema(
    label: 'Bộ flashcard',
    listPath: '/api/v1/admin/practice/decks',
    kind: AdminContentKind.deck,
    entityType: 'flashcard_deck',
    basePath: '/api/v1/admin/practice/decks',
    versionBasePath: '/api/v1/admin/practice',
    child: _cards,
  ),
  const AdminContentSchema(
    label: 'Nội dung luyện nói',
    listPath: '/api/v1/admin/practice/speaking-prompts',
    kind: AdminContentKind.card,
    entityType: 'flashcard',
    basePath: '/api/v1/admin/practice/cards',
    versionBasePath: '/api/v1/admin/practice',
  ),
];
