import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/learning_api.dart';
import '../../app/student_api.dart';
import '../quizzes/quiz_screen.dart';

class ProgressScreen extends StatefulWidget {
  final StudentApi api;
  final bool active;
  final void Function(int tabIndex, {String? initialPrompt})? onNavigateTab;
  const ProgressScreen({
    super.key,
    required this.api,
    required this.active,
    this.onNavigateTab,
  });
  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  StudentProgress? _progress;
  LearningProgress? _learning;
  KnowledgeGapAnalysis? _gaps;
  bool _loading = false;
  bool _failed = false;
  int _request = 0;

  bool _isAdmin = false;
  AdminProgressOverview? _adminOverview;
  List<AdminChatItem>? _adminChats;
  int _adminTab = 0;
  String _studentFilter = '';
  String _chatFilter = '';

  @override
  void initState() {
    super.initState();
    if (widget.active) _load();
  }

  @override
  void didUpdateWidget(covariant ProgressScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.active && (!oldWidget.active || oldWidget.api != widget.api)) {
      _load();
    }
  }

  Future<void> _load() async {
    final request = ++_request;
    setState(() {
      _loading = true;
      _failed = false;
    });

    try {
      StudentProfile? profile;
      try {
        profile = await widget.api.loadProfile();
      } catch (_) {}
      final isAdmin = profile?.role == 'admin';

      if (isAdmin) {
        final overview = await widget.api.loadAdminProgress();
        final chats = await widget.api
            .loadAdminChats()
            .catchError((_) => <AdminChatItem>[]);
        if (!mounted || request != _request) return;
        setState(() {
          _isAdmin = true;
          _adminOverview = overview;
          _adminChats = chats;
          _loading = false;
        });
        return;
      }

      final learningRequest = widget.api
          .loadLearningProgress()
          .then<LearningProgress?>((value) => value, onError: (Object _) => null);
      final gapRequest = widget.api
          .loadKnowledgeGaps()
          .then<KnowledgeGapAnalysis?>((value) => value, onError: (Object _) => null);
      final progress = await widget.api.loadProgress();
      final learning = await learningRequest;
      final gaps = await gapRequest;
      if (!mounted || request != _request) return;
      setState(() {
        _isAdmin = false;
        _progress = progress;
        _learning = learning;
        _gaps = gaps;
        _loading = false;
      });
    } catch (_) {
      if (!mounted || request != _request) return;
      setState(() {
        _failed = true;
        _loading = false;
      });
    }
  }

  String _date(DateTime value) {
    final date = value.toLocal();
    String pad(int n) => n.toString().padLeft(2, '0');
    return '${pad(date.day)}/${pad(date.month)}/${date.year} • ${pad(date.hour)}:${pad(date.minute)}';
  }

  Widget _buildAdminView(BuildContext context) {
    final theme = Theme.of(context);
    final overview = _adminOverview;
    final chats = _adminChats ?? [];

    final filteredStudents = (overview?.students ?? []).where((s) {
      final q = _studentFilter.toLowerCase().trim();
      if (q.isEmpty) return true;
      final name = (s.fullName ?? '').toLowerCase();
      final email = s.email.toLowerCase();
      final className = (s.className ?? '').toLowerCase();
      final school = (s.schoolName ?? '').toLowerCase();
      return name.contains(q) ||
          email.contains(q) ||
          className.contains(q) ||
          school.contains(q);
    }).toList();

    final filteredChats = chats.where((c) {
      final q = _chatFilter.toLowerCase().trim();
      if (q.isEmpty) return true;
      return c.question.toLowerCase().contains(q) ||
          c.answer.toLowerCase().contains(q) ||
          c.userEmail.toLowerCase().contains(q) ||
          (c.userName ?? '').toLowerCase().contains(q);
    }).toList();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Quản trị học tập & Chat',
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Báo cáo tiến độ toàn bộ học viên và lịch sử AI Tutor',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              IconButton(
                onPressed: _load,
                tooltip: 'Làm mới',
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SegmentedButton<int>(
            segments: [
              ButtonSegment(
                value: 0,
                icon: const Icon(Icons.people_alt_outlined),
                label: Text('Tiến độ học viên (${overview?.totalStudents ?? 0})'),
              ),
              ButtonSegment(
                value: 1,
                icon: const Icon(Icons.forum_outlined),
                label: Text('Quản lý đoạn chat (${chats.length})'),
              ),
            ],
            selected: {_adminTab},
            onSelectionChanged: (val) => setState(() => _adminTab = val.first),
          ),
          const SizedBox(height: 16),
          if (_adminTab == 0) ...[
            // KPI Summary Cards
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                _buildMetricCard(
                  context,
                  icon: Icons.school_outlined,
                  title: 'Tổng học viên',
                  value: '${overview?.totalStudents ?? 0}',
                  color: theme.colorScheme.primary,
                ),
                _buildMetricCard(
                  context,
                  icon: Icons.assignment_turned_in_outlined,
                  title: 'Bài thi đã nộp',
                  value: '${overview?.totalQuizzes ?? 0}',
                  color: Colors.green,
                ),
                _buildMetricCard(
                  context,
                  icon: Icons.percent_outlined,
                  title: 'Tỉ lệ đúng TB',
                  value: '${overview?.averageAccuracy ?? 0}%',
                  color: Colors.orange,
                ),
                _buildMetricCard(
                  context,
                  icon: Icons.style_outlined,
                  title: 'Thẻ ôn & Luyện nói',
                  value:
                      '${(overview?.students ?? []).fold<int>(0, (acc, s) => acc + s.reviewedCards + s.speakingCount)}',
                  color: Colors.purple,
                ),
              ],
            ),
            const SizedBox(height: 16),
            TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: 'Tìm theo tên, email, lớp, trường…',
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                suffixIcon: _studentFilter.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () => setState(() => _studentFilter = ''),
                      )
                    : null,
              ),
              onChanged: (v) => setState(() => _studentFilter = v),
            ),
            const SizedBox(height: 12),
            if (filteredStudents.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 32),
                child: Center(child: Text('Không tìm thấy học viên phù hợp')),
              )
            else
              for (final student in filteredStudents)
                Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            CircleAvatar(
                              backgroundColor:
                                  theme.colorScheme.primaryContainer,
                              child: Text(
                                (student.fullName?.isNotEmpty == true
                                        ? student.fullName![0]
                                        : student.email[0])
                                    .toUpperCase(),
                                style: TextStyle(
                                  color: theme.colorScheme.onPrimaryContainer,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    student.fullName?.isNotEmpty == true
                                        ? student.fullName!
                                        : student.email,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 16,
                                    ),
                                  ),
                                  Text(
                                    'Lớp: ${student.className ?? "—"} • Trường: ${student.schoolName ?? "—"}',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: theme.colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                  Text(
                                    student.email,
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: theme.colorScheme.outline,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 6,
                              ),
                              decoration: BoxDecoration(
                                color: (student.accuracyPercent >= 70
                                        ? Colors.green
                                        : Colors.orange)
                                    .withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(
                                '${student.accuracyPercent}% đúng',
                                style: TextStyle(
                                  color: student.accuracyPercent >= 70
                                      ? Colors.green.shade800
                                      : Colors.orange.shade800,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 6,
                          children: [
                            Chip(
                              visualDensity: VisualDensity.compact,
                              avatar: const Icon(Icons.assignment, size: 14),
                              label: Text(
                                '${student.completedQuizzes} bài test (${student.correctAnswers}/${student.totalQuestions} câu)',
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                            Chip(
                              visualDensity: VisualDensity.compact,
                              avatar: const Icon(Icons.style, size: 14),
                              label: Text(
                                '${student.reviewedCards} thẻ ôn',
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                            Chip(
                              visualDensity: VisualDensity.compact,
                              avatar: const Icon(Icons.record_voice_over, size: 14),
                              label: Text(
                                '${student.speakingCount} lượt nói',
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                            if (student.difficultCards > 0)
                              Chip(
                                visualDensity: VisualDensity.compact,
                                avatar: const Icon(
                                  Icons.warning_amber_rounded,
                                  size: 14,
                                  color: Colors.red,
                                ),
                                label: Text(
                                  '${student.difficultCards} thẻ khó',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: Colors.red,
                                  ),
                                ),
                              ),
                          ],
                        ),
                        if (student.recentQuizzes.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Divider(
                            height: 1,
                            color: theme.colorScheme.outlineVariant.withValues(
                              alpha: 0.5,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Bài nộp gần đây:',
                            style: theme.textTheme.labelSmall?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          for (final q in student.recentQuizzes.take(2))
                            Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Row(
                                children: [
                                  const Icon(
                                    Icons.check_circle_outline,
                                    size: 14,
                                    color: Colors.green,
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    '${q["correct"]}/${q["total"]} câu đúng',
                                    style: const TextStyle(fontSize: 12),
                                  ),
                                  const Spacer(),
                                  if (q["submitted_at"] != null)
                                    Text(
                                      _date(DateTime.parse(q["submitted_at"] as String)),
                                      style: theme.textTheme.bodySmall?.copyWith(
                                        fontSize: 11,
                                        color: theme.colorScheme.outline,
                                      ),
                                    ),
                                ],
                              ),
                            ),
                        ],
                      ],
                    ),
                  ),
                ),
          ] else ...[
            // Chat Logs
            TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: 'Tìm nội dung câu hỏi hoặc email học viên…',
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                suffixIcon: _chatFilter.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () => setState(() => _chatFilter = ''),
                      )
                    : null,
              ),
              onChanged: (v) => setState(() => _chatFilter = v),
            ),
            const SizedBox(height: 12),
            if (filteredChats.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 32),
                child: Center(child: Text('Chưa có đoạn chat nào được lưu')),
              )
            else
              for (final chat in filteredChats)
                Card(
                  margin: const EdgeInsets.only(bottom: 14),
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.person_pin,
                              size: 18,
                              color: theme.colorScheme.primary,
                            ),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                chat.userName?.isNotEmpty == true
                                    ? '${chat.userName} (${chat.userEmail})'
                                    : chat.userEmail,
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 13,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: theme.colorScheme.secondaryContainer,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                chat.language.toUpperCase(),
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: theme.colorScheme.onSecondaryContainer,
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              _date(chat.createdAt),
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontSize: 11,
                                color: theme.colorScheme.outline,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primaryContainer.withValues(
                              alpha: 0.35,
                            ),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.help_outline,
                                size: 16,
                                color: theme.colorScheme.primary,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: SelectableText(
                                  chat.question,
                                  style: const TextStyle(fontSize: 13),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 8),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                              color: theme.colorScheme.outlineVariant.withValues(
                                alpha: 0.6,
                              ),
                            ),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.auto_awesome,
                                size: 16,
                                color: theme.colorScheme.tertiary,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: SelectableText(
                                  chat.answer,
                                  style: const TextStyle(fontSize: 13),
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (chat.citations.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 6,
                            runSpacing: 4,
                            children: [
                              for (final cit in chat.citations)
                                Chip(
                                  visualDensity: VisualDensity.compact,
                                  avatar: const Icon(Icons.menu_book, size: 12),
                                  label: Text(
                                    cit['printed_page'] != null
                                        ? 'SGK trang ${cit["printed_page"]}'
                                        : 'PDF trang ${cit["pdf_page"]}',
                                    style: const TextStyle(fontSize: 11),
                                  ),
                                ),
                            ],
                          ),
                        ],
                        const SizedBox(height: 4),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.copy_rounded, size: 14),
                              tooltip: 'Sao chép đoạn chat',
                              visualDensity: VisualDensity.compact,
                              onPressed: () {
                                Clipboard.setData(
                                  ClipboardData(
                                    text:
                                        'Học sinh: ${chat.question}\nAI Tutor: ${chat.answer}',
                                  ),
                                );
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Đã sao chép đoạn chat'),
                                    duration: Duration(seconds: 1),
                                  ),
                                );
                              },
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
          ],
        ],
      ),
    );
  }

  void _showRemedialSheet(KnowledgeGapItem item) {
    final theme = Theme.of(context);
    final masteryPct = (item.masteryScore * 100).round();
    final statusColor = item.masteryScore < 0.50
        ? Colors.red
        : (item.masteryScore < 0.70 ? Colors.orange : Colors.green);

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: theme.colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 36,
                    height: 4,
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primaryContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Unit ${item.unitNumber}',
                        style: TextStyle(
                          color: theme.colorScheme.onPrimaryContainer,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: statusColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Thông thạo: $masteryPct%',
                        style: TextStyle(
                          color: statusColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  item.conceptName,
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Unit ${item.unitNumber}: ${item.unitTitle}',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: theme.colorScheme.outlineVariant.withValues(alpha: 0.6),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            Icons.menu_book_rounded,
                            size: 16,
                            color: theme.colorScheme.primary,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            'Kiến thức cốt lõi SGK',
                            style: theme.textTheme.labelLarge?.copyWith(
                              color: theme.colorScheme.primary,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        item.summary,
                        style: theme.textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          item.textbookCitation,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    key: const Key('start-remedial-quiz'),
                    icon: const Icon(Icons.bolt_rounded),
                    label: const Text('Luyện tập bù đắp (5 câu)'),
                    onPressed: () async {
                      Navigator.pop(ctx);
                      try {
                        final session = await widget.api.createRemedialQuiz(item.conceptKey);
                        if (!mounted) return;
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (context) => Scaffold(
                              appBar: AppBar(title: Text('Luyện tập: ${item.conceptName}')),
                              body: QuizScreen(api: widget.api, initialSession: session),
                            ),
                          ),
                        );
                      } catch (e) {
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Không thể tạo bài luyện tập: $e')),
                          );
                        }
                      }
                    },
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    key: const Key('ask-tutor-gap'),
                    icon: const Icon(Icons.auto_awesome),
                    label: const Text('Hỏi AI Tutor giải thích'),
                    onPressed: () {
                      Navigator.pop(ctx);
                      if (widget.onNavigateTab != null) {
                        widget.onNavigateTab!(1, initialPrompt: item.suggestedPrompt);
                      } else {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('Chuyển sang tab Tutor để hỏi: "${item.suggestedPrompt}"'),
                          ),
                        );
                      }
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildKnowledgeGapSection(BuildContext context, KnowledgeGapAnalysis gaps) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.psychology_alt_outlined, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Chẩn đoán lỗ hổng kiến thức',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: gaps.weakConceptsCount > 0
                        ? Colors.orange.withValues(alpha: 0.15)
                        : Colors.green.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    gaps.weakConceptsCount > 0
                        ? '${gaps.weakConceptsCount} điểm cần củng cố'
                        : 'Nắm vững kiến thức',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: gaps.weakConceptsCount > 0 ? Colors.orange.shade800 : Colors.green.shade800,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (gaps.gaps.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    const Icon(Icons.check_circle_outline, color: Colors.green, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Bạn đang làm rất tốt! Chưa phát hiện lỗ hổng kiến thức nào.',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ],
                ),
              )
            else
              for (final item in gaps.gaps) ...[
                Builder(
                  builder: (context) {
                    final pct = (item.masteryScore * 100).round();
                    final statusColor = item.masteryScore < 0.50
                        ? Colors.red
                        : (item.masteryScore < 0.70 ? Colors.orange : Colors.green);

                    return InkWell(
                      onTap: () => _showRemedialSheet(item),
                      borderRadius: BorderRadius.circular(8),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: theme.colorScheme.surfaceContainerHighest,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    'Unit ${item.unitNumber}',
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                      color: theme.colorScheme.primary,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    item.conceptName,
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      fontWeight: FontWeight.w600,
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                Text(
                                  '$pct%',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: statusColor,
                                  ),
                                ),
                                const SizedBox(width: 4),
                                Icon(
                                  Icons.chevron_right,
                                  size: 16,
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(3),
                              child: LinearProgressIndicator(
                                value: item.masteryScore.clamp(0.0, 1.0),
                                backgroundColor: theme.colorScheme.surfaceContainerHighest,
                                color: statusColor,
                                minHeight: 6,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Sai ${item.incorrectCount}/${item.totalAttempts} câu · ${item.textbookCitation}',
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontSize: 11,
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
                if (item != gaps.gaps.last) const Divider(height: 1),
              ],
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String value,
    required Color color,
  }) {
    final theme = Theme.of(context);
    final width = (MediaQuery.of(context).size.width - 44) / 2;
    return Container(
      width: width > 140 ? width : 150,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.6),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 20, color: color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  value,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  title,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    fontSize: 11,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_failed) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Không thể tải tiến độ. Vui lòng thử lại.'),
            const SizedBox(height: 12),
            FilledButton(onPressed: _load, child: const Text('Thử lại')),
          ],
        ),
      );
    }

    if (_isAdmin) {
      return _buildAdminView(context);
    }

    final progress = _progress;
    if (progress == null) return const SizedBox.shrink();
    final percent = progress.total == 0
        ? 0
        : (100 * progress.correct / progress.total).round();
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Tiến độ học tập',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              IconButton(
                onPressed: _load,
                tooltip: 'Làm mới',
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          if (_learning case final learning?)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Từ vựng & luyện nói',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 16,
                      runSpacing: 8,
                      children: [
                        Text('${learning.reviewedCards} thẻ đã ôn'),
                        Text('${learning.dueCards} thẻ đến hạn'),
                        Text('${learning.difficultCards} thẻ khó'),
                        Text('${learning.speakingCount} lượt luyện nói'),
                      ],
                    ),
                    if (learning.recentSpeaking.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      const Text(
                        'Luyện nói gần đây · mức khớp bản chép lời, không phải điểm phát âm',
                      ),
                      for (final item in learning.recentSpeaking)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(item.prompt),
                          subtitle: Text(
                            '${item.transcript}\n${_date(item.createdAt)}',
                          ),
                          trailing: Text('${item.matchPercent.round()}%'),
                        ),
                    ],
                  ],
                ),
              ),
            )
          else
            const Text('Chưa tải được tiến độ từ vựng và luyện nói.'),
          if (_gaps case final gaps?) ...[
            const SizedBox(height: 12),
            _buildKnowledgeGapSection(context, gaps),
          ],
          if (progress.completedQuizzes == 0) ...[
            const SizedBox(height: 48),
            const Icon(Icons.insights_outlined, size: 56),
            const SizedBox(height: 16),
            const Center(child: Text('Chưa có bài kiểm tra đã nộp')),
            const SizedBox(height: 8),
            const Text(
              'Hoàn thành và nộp bài ở tab Kiểm tra để theo dõi kết quả tại đây.',
              textAlign: TextAlign.center,
            ),
          ] else ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${progress.completedQuizzes} bài kiểm tra đã nộp'),
                    const SizedBox(height: 12),
                    Text(
                      '$percent%',
                      style: Theme.of(context).textTheme.headlineLarge,
                    ),
                    const Text('Tỷ lệ trả lời đúng'),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: progress.total == 0
                          ? 0
                          : progress.correct / progress.total,
                    ),
                    const SizedBox(height: 8),
                    Text('Đúng ${progress.correct} trên ${progress.total} câu'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Lịch sử làm bài',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            for (final item in progress.history)
              Card(
                child: ListTile(
                  leading: const Icon(Icons.assignment_turned_in_outlined),
                  title: Text('${item.correct}/${item.total} câu đúng'),
                  subtitle: Text(_date(item.submittedAt)),
                  trailing: Text(
                    '${item.total == 0 ? 0 : (10 * item.correct / item.total).toStringAsFixed(1)}/10',
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
