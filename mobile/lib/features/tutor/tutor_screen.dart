import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../api/api_error.dart';
import '../../app/student_api.dart';
import '../../widgets/source_citation.dart';
import 'image_selector.dart';

class _ChatMessage {
  final bool isUser;
  final String text;
  final SelectedImage? image;
  final TutorResult? result;
  final bool isRefusal;

  _ChatMessage({
    required this.isUser,
    required this.text,
    this.image,
    this.result,
    this.isRefusal = false,
  });
}

class TutorScreen extends StatefulWidget {
  final StudentApi api;
  final ImageSelector imageSelector;
  final String? initialPrompt;
  const TutorScreen({
    super.key,
    required this.api,
    required this.imageSelector,
    this.initialPrompt,
  });

  @override
  State<TutorScreen> createState() => _TutorScreenState();
}

class _TutorScreenState extends State<TutorScreen> {
  final _question = TextEditingController();
  final _scrollController = ScrollController();
  final List<_ChatMessage> _messages = [];
  List<TutorConversationSummary> _conversations = [];

  TutorLanguage _language = TutorLanguage.vietnamese;
  String? _conversationId;
  SelectedImage? _image;
  bool _busy = false;
  bool _loadingHistory = false;
  bool _conversationFull = false;

  static const _suggestions = [
    'Giải thích thì hiện tại đơn trong Unit 1',
    'Từ vựng quan trọng Unit 2 Healthy Living',
    'Cách phân biệt âm /ə/ và /ɜː/ Unit 1',
    'Làm sao để giữ gìn sức khoẻ (Unit 2)?',
  ];

  @override
  void initState() {
    super.initState();
    if (widget.initialPrompt != null && widget.initialPrompt!.isNotEmpty) {
      _question.text = widget.initialPrompt!;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadConversations());
  }

  @override
  void didUpdateWidget(covariant TutorScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialPrompt != null &&
        widget.initialPrompt!.isNotEmpty &&
        widget.initialPrompt != oldWidget.initialPrompt) {
      _question.text = widget.initialPrompt!;
    }
  }

  @override
  void dispose() {
    _question.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _selectImage() async {
    try {
      final selected = await widget.imageSelector.select();
      if (mounted && selected != null) {
        setState(() => _image = selected);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Không thể chọn ảnh: $e')));
      }
    }
  }

  Future<void> _captureImage() async {
    try {
      final selected = await widget.imageSelector.capture();
      if (mounted && selected != null) {
        setState(() => _image = selected);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Không thể chụp ảnh: $e')));
      }
    }
  }

  void _showAttachmentPicker(BuildContext context) {
    final theme = Theme.of(context);
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: theme.colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 36,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.onSurfaceVariant.withValues(
                      alpha: 0.3,
                    ),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 4,
                  ),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      'Đính kèm bài tập',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                ListTile(
                  key: const Key('capture-image'),
                  leading: CircleAvatar(
                    backgroundColor: theme.colorScheme.primaryContainer,
                    child: Icon(
                      Icons.camera_alt_rounded,
                      color: theme.colorScheme.primary,
                    ),
                  ),
                  title: const Text('Chụp ảnh bài tập'),
                  subtitle: const Text('Mở camera để chụp bài tập hoặc SGK'),
                  onTap: () {
                    Navigator.pop(ctx);
                    _captureImage();
                  },
                ),
                ListTile(
                  key: const Key('select-image'),
                  leading: CircleAvatar(
                    backgroundColor: theme.colorScheme.secondaryContainer,
                    child: Icon(
                      Icons.photo_library_rounded,
                      color: theme.colorScheme.secondary,
                    ),
                  ),
                  title: const Text('Chọn ảnh từ thư viện'),
                  subtitle: const Text('Tải ảnh bài tập có sẵn trong máy'),
                  onTap: () {
                    Navigator.pop(ctx);
                    _selectImage();
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _loadConversations() async {
    if (_loadingHistory) return;
    setState(() => _loadingHistory = true);
    try {
      final conversations = await widget.api.loadTutorConversations();
      if (!mounted) return;
      setState(() => _conversations = List.of(conversations));
      if (_conversationId == null && conversations.isNotEmpty) {
        await _openConversation(conversations.first.id);
      }
    } finally {
      if (mounted) setState(() => _loadingHistory = false);
    }
  }

  Future<void> _openConversation(String conversationId) async {
    try {
      final conversation = await widget.api.loadTutorConversation(
        conversationId,
      );
      if (!mounted) return;
      setState(() {
        _conversationId = conversation.id;
        _language = conversation.language;
        _conversationFull = conversation.exchanges.length >= 50;
        _messages
          ..clear()
          ..addAll(
            conversation.exchanges.expand(
              (exchange) => [
                _ChatMessage(isUser: true, text: exchange.question),
                _ChatMessage(
                  isUser: false,
                  text: exchange.answer,
                  result: TutorResult(
                    exchange.answer,
                    exchange.citations,
                    conversationId: conversation.id,
                  ),
                  isRefusal: exchange.citations.isEmpty,
                ),
              ],
            ),
          );
      });
      _scrollToBottom();
    } on TutorConversationUnavailable {
      if (!mounted) return;
      setState(() {
        _conversationId = null;
        _messages.clear();
        _conversationFull = false;
      });
      await _loadConversations();
    }
  }

  Future<void> _resetChat() async {
    setState(() {
      _conversationId = null;
      _messages.clear();
      _question.clear();
      _image = null;
      _busy = false;
      _conversationFull = false;
    });
    final created = await widget.api.createTutorConversation(
      title: 'Đoạn chat mới',
      language: _language,
    );
    if (!mounted) return;
    setState(() {
      _conversationId = created.id;
      _conversations = [
        created,
        ..._conversations.where((item) => item.id != created.id),
      ];
    });
  }

  Future<String> _ensureConversation(String title) async {
    if (_conversationId != null) return _conversationId!;
    final created = await widget.api.createTutorConversation(
      title: title,
      language: _language,
    );
    if (mounted) {
      setState(() {
        _conversationId = created.id;
        _conversations = [
          created,
          ..._conversations.where((item) => item.id != created.id),
        ];
      });
    }
    return created.id;
  }

  Future<void> _deleteConversation(String conversationId) async {
    await widget.api.deleteTutorConversation(conversationId);
    if (!mounted) return;
    setState(() {
      _conversations = _conversations
          .where((item) => item.id != conversationId)
          .toList(growable: false);
      if (_conversationId == conversationId) {
        _conversationId = null;
        _messages.clear();
        _conversationFull = false;
      }
    });
  }

  Future<void> _confirmDeleteConversation(
    BuildContext sheetContext,
    String conversationId,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Xóa đoạn chat?'),
        content: const Text('Lịch sử trong đoạn chat này sẽ bị xóa.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            key: const Key('confirm-delete-conversation'),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _deleteConversation(conversationId);
    if (sheetContext.mounted) Navigator.pop(sheetContext);
  }

  Future<void> _showHistory() async {
    await _loadConversations();
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: SizedBox(
          height: 420,
          child: Column(
            children: [
              const ListTile(
                title: Text(
                  'Lịch sử trò chuyện',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                subtitle: Text('Tối đa 20 đoạn chat, lưu trong 90 ngày'),
              ),
              Expanded(
                child: _conversations.isEmpty
                    ? const Center(child: Text('Chưa có đoạn chat nào'))
                    : ListView.builder(
                        itemCount: _conversations.length,
                        itemBuilder: (context, index) {
                          final item = _conversations[index];
                          return ListTile(
                            key: Key('conversation-${item.id}'),
                            leading: const Icon(Icons.chat_bubble_outline),
                            title: Text(item.title),
                            subtitle: Text(
                              item.language == TutorLanguage.vietnamese
                                  ? 'Tiếng Việt'
                                  : 'English',
                            ),
                            onTap: () {
                              Navigator.pop(sheetContext);
                              _openConversation(item.id);
                            },
                            trailing: IconButton(
                              key: Key('delete-conversation-${item.id}'),
                              tooltip: 'Xóa đoạn chat',
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () => _confirmDeleteConversation(
                                sheetContext,
                                item.id,
                              ),
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _ask([String? customPrompt]) async {
    final rawText = (customPrompt ?? _question.text).trim();
    final attachedImage = _image;
    if (rawText.isEmpty && attachedImage == null) return;
    final queryText = rawText.isNotEmpty
        ? rawText
        : 'Giải thích và hướng dẫn làm bài tập trong hình ảnh này giúp em.';

    setState(() {
      _messages.add(
        _ChatMessage(isUser: true, text: queryText, image: attachedImage),
      );
      _busy = true;
      _question.clear();
      _image = null;
    });
    _scrollToBottom();

    try {
      final conversationId = await _ensureConversation(queryText);
      final result = await widget.api.askTutorInConversation(
        conversationId,
        TutorQuery(
          queryText,
          _language,
          attachedImage == null
              ? null
              : TutorImage(
                  attachedImage.name,
                  attachedImage.bytes,
                  attachedImage.mediaType,
                ),
        ),
      );
      if (mounted) {
        setState(() {
          _messages.add(
            _ChatMessage(
              isUser: false,
              text: result.answer,
              result: result,
              isRefusal: result.scopeStatus == 'out_of_scope',
            ),
          );
        });
        _scrollToBottom();
      }
    } on TutorRefusal {
      if (mounted) {
        setState(() {
          _messages.add(
            _ChatMessage(
              isUser: false,
              text: 'Nội dung này không có trong phạm vi SGK Unit 1–2 đã xác minh.',
              isRefusal: true,
            ),
          );
        });
        _scrollToBottom();
      }
    } on TutorConversationFull {
      if (mounted) setState(() => _conversationFull = true);
    } on TutorConversationUnavailable {
      if (mounted) {
        setState(() {
          _conversationId = null;
          _messages.clear();
          _conversationFull = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Đoạn chat đã hết hạn. Hãy bắt đầu đoạn chat mới.'),
          ),
        );
      }
    } on ApiException catch (error) {
      if (mounted) {
        final message = switch ((_language, error.code)) {
          (TutorLanguage.english, 'ai_provider_unavailable') =>
            'The AI tutor is temporarily unavailable. Please try again.',
          (TutorLanguage.english, 'image_processing_timeout') =>
            'The image took too long to process. Please try again.',
          (TutorLanguage.english, _) => 'The request could not be completed. Please check the connection and try again.',
          (TutorLanguage.vietnamese, 'ai_provider_unavailable') =>
            'Gia sư AI đang tạm thời quá tải. Em hãy thử lại sau nhé.',
          (TutorLanguage.vietnamese, 'image_processing_timeout') =>
            'Ảnh xử lý quá lâu. Em hãy thử gửi lại ảnh nhé.',
          (TutorLanguage.vietnamese, _) =>
            'Chưa thể hoàn thành yêu cầu. Em hãy kiểm tra kết nối và thử lại.',
        };
        setState(() {
          _messages.add(
            _ChatMessage(isUser: false, text: message, isRefusal: true),
          );
        });
        _scrollToBottom();
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        _scrollToBottom();
      }
    }
  }

  Widget _buildTopBar(BuildContext context) {
    final theme = Theme.of(context);
    final brand = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(7),
          decoration: BoxDecoration(
            color: theme.colorScheme.primaryContainer,
            shape: BoxShape.circle,
          ),
          child: Icon(
            Icons.auto_awesome,
            size: 18,
            color: theme.colorScheme.primary,
          ),
        ),
        const SizedBox(width: 10),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'AI Tutor',
              maxLines: 1,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              'Global Success 7',
              maxLines: 1,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                fontSize: 11,
              ),
            ),
          ],
        ),
      ],
    );
    final controls = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SegmentedButton<TutorLanguage>(
          showSelectedIcon: false,
          style: const ButtonStyle(
            visualDensity: VisualDensity.compact,
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          segments: const [
            ButtonSegment(
              value: TutorLanguage.vietnamese,
              label: Text('Tiếng Việt', style: TextStyle(fontSize: 12)),
            ),
            ButtonSegment(
              value: TutorLanguage.english,
              label: Text('Tiếng Anh', style: TextStyle(fontSize: 12)),
            ),
          ],
          selected: {_language},
          onSelectionChanged: (selection) =>
              setState(() => _language = selection.first),
        ),
        const SizedBox(width: 4),
        IconButton(
          key: const Key('tutor-history'),
          icon: const Icon(Icons.history_rounded, size: 21),
          tooltip: 'Lịch sử trò chuyện',
          onPressed: _loadingHistory ? null : _showHistory,
        ),
        if (_messages.isNotEmpty || _conversationId != null)
          IconButton(
            key: const Key('new-tutor-conversation'),
            icon: const Icon(Icons.add_comment_outlined, size: 20),
            tooltip: 'Đoạn chat mới',
            onPressed: _busy ? null : _resetChat,
          ),
      ],
    );
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(
          bottom: BorderSide(
            color: theme.colorScheme.outlineVariant.withValues(alpha: 0.4),
          ),
        ),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) => constraints.maxWidth < 520
            ? Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Align(alignment: Alignment.centerLeft, child: brand),
                  const SizedBox(height: 8),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerRight,
                    child: controls,
                  ),
                ],
              )
            : Row(children: [brand, const Spacer(), controls]),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    theme.colorScheme.primary,
                    theme.colorScheme.tertiary,
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: theme.colorScheme.primary.withValues(alpha: 0.25),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: const Icon(
                Icons.auto_awesome,
                size: 32,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Gia sư AI Tiếng Anh 7',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Hỏi bất kỳ điều gì về bài học, từ vựng hay ngữ pháp.\nMọi câu trả lời được đối chiếu trực tiếp từ Sách giáo khoa.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Gợi ý câu hỏi:',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(height: 10),
            for (final suggestion in _suggestions) ...[
              InkWell(
                onTap: () => _ask(suggestion),
                borderRadius: BorderRadius.circular(12),
                child: Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 12,
                  ),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: theme.colorScheme.outlineVariant.withValues(
                        alpha: 0.6,
                      ),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.lightbulb_outline,
                        size: 18,
                        color: theme.colorScheme.primary,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          suggestion,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      Icon(
                        Icons.arrow_forward_ios,
                        size: 12,
                        color: theme.colorScheme.outline,
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildUserMessage(BuildContext context, _ChatMessage msg) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(18),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(4),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (msg.image != null) ...[
                    Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.surface.withValues(alpha: 0.9),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: theme.colorScheme.outlineVariant.withValues(
                            alpha: 0.5,
                          ),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (msg.image!.bytes.length > 100) ...[
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: Image.memory(
                                msg.image!.bytes,
                                width: 180,
                                height: 130,
                                fit: BoxFit.cover,
                                errorBuilder: (_, _, _) =>
                                    const SizedBox.shrink(),
                              ),
                            ),
                            const SizedBox(height: 6),
                          ],
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.image_outlined,
                                size: 14,
                                color: theme.colorScheme.primary,
                              ),
                              const SizedBox(width: 6),
                              Flexible(
                                child: Text(
                                  msg.image!.name,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                  SelectableText(
                    msg.text,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onPrimaryContainer,
                      fontSize: 15,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAssistantMessage(BuildContext context, _ChatMessage msg) {
    final theme = Theme.of(context);

    if (msg.isRefusal) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: theme.colorScheme.errorContainer,
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.shield_outlined,
                size: 18,
                color: theme.colorScheme.error,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Card(
                key: const Key('tutor-refusal'),
                margin: EdgeInsets.zero,
                color: theme.colorScheme.errorContainer,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Text(
                    msg.text,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onErrorContainer,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [theme.colorScheme.primary, theme.colorScheme.tertiary],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.auto_awesome,
              size: 18,
              color: Colors.white,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerLow,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(18),
                ),
                border: Border.all(
                  color: theme.colorScheme.outlineVariant.withValues(
                    alpha: 0.6,
                  ),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  SelectableText(
                    msg.text,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontSize: 15,
                      height: 1.45,
                    ),
                  ),
                  if (msg.result != null &&
                      msg.result!.citations.isNotEmpty) ...[
                    const SizedBox(height: 14),
                    Divider(
                      height: 1,
                      color: theme.colorScheme.outlineVariant.withValues(
                        alpha: 0.5,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Icon(
                          Icons.verified_outlined,
                          size: 15,
                          color: theme.colorScheme.primary,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'Nguồn trích dẫn SGK đối chiếu:',
                          style: theme.textTheme.labelMedium?.copyWith(
                            color: theme.colorScheme.primary,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    for (final citation in msg.result!.citations)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: SourceCitation(source: citation),
                      ),
                  ],
                  const SizedBox(height: 6),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.copy_rounded, size: 16),
                        tooltip: 'Sao chép',
                        visualDensity: VisualDensity.compact,
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: msg.text));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Đã sao chép câu trả lời'),
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
      ),
    );
  }

  Widget _buildBusyIndicator(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [theme.colorScheme.primary, theme.colorScheme.tertiary],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.auto_awesome,
              size: 18,
              color: Colors.white,
            ),
          ),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(
                color: theme.colorScheme.outlineVariant.withValues(alpha: 0.5),
              ),
            ),
            child: const _TutorTypingIndicator(),
          ),
        ],
      ),
    );
  }

  Widget _buildInputDock(BuildContext context) {
    final theme = Theme.of(context);
    if (_conversationFull) {
      return SafeArea(
        top: false,
        child: Container(
          key: const Key('conversation-full'),
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: theme.colorScheme.surface,
            border: Border(
              top: BorderSide(color: theme.colorScheme.outlineVariant),
            ),
          ),
          child: FilledButton.icon(
            onPressed: _resetChat,
            icon: const Icon(Icons.add_comment_outlined),
            label: const Text('Bắt đầu đoạn chat mới'),
          ),
        ),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            offset: const Offset(0, -2),
            blurRadius: 8,
          ),
        ],
        border: Border(
          top: BorderSide(
            color: theme.colorScheme.outlineVariant.withValues(alpha: 0.4),
          ),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_image != null) ...[
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer.withValues(
                    alpha: 0.4,
                  ),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: theme.colorScheme.primary.withValues(alpha: 0.25),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (_image!.bytes.length > 100) ...[
                      ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: Image.memory(
                          _image!.bytes,
                          width: 32,
                          height: 32,
                          fit: BoxFit.cover,
                          errorBuilder: (_, _, _) => Icon(
                            Icons.image_outlined,
                            size: 18,
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                    ] else ...[
                      Icon(
                        Icons.image_outlined,
                        size: 16,
                        color: theme.colorScheme.primary,
                      ),
                      const SizedBox(width: 6),
                    ],
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 200),
                      child: Text(
                        _image!.name,
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    InkWell(
                      key: const Key('remove-attached-image'),
                      onTap: () => setState(() => _image = null),
                      borderRadius: BorderRadius.circular(12),
                      child: Icon(
                        Icons.close_rounded,
                        size: 16,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            Container(
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withValues(
                  alpha: 0.5,
                ),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: theme.colorScheme.outlineVariant),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  IconButton(
                    key: const Key('attach-button'),
                    icon: const Icon(
                      Icons.add_circle_outline_rounded,
                      size: 24,
                    ),
                    tooltip: 'Đính kèm ảnh bài tập',
                    onPressed: _busy
                        ? null
                        : () => _showAttachmentPicker(context),
                    visualDensity: VisualDensity.compact,
                    padding: const EdgeInsets.all(6),
                    constraints: const BoxConstraints(),
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: TextField(
                      key: const Key('tutor-question'),
                      controller: _question,
                      minLines: 1,
                      maxLines: 4,
                      decoration: InputDecoration(
                        hintText: _image != null
                            ? 'Nhập câu hỏi (hoặc bấm Hỏi AI)...'
                            : 'Hỏi AI về bài học, từ vựng, ngữ pháp...',
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 10,
                        ),
                      ),
                      onSubmitted: (_) {
                        if (!_busy) _ask();
                      },
                    ),
                  ),
                  const SizedBox(width: 4),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: FilledButton.icon(
                      onPressed: _busy ? null : () => _ask(),
                      icon: const Icon(Icons.auto_awesome, size: 16),
                      label: const Text('Hỏi AI'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 10,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(20),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildTopBar(context),
        Expanded(
          child: _messages.isEmpty
              ? _buildEmptyState(context)
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: _messages.length + (_busy ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index < _messages.length) {
                      final msg = _messages[index];
                      return msg.isUser
                          ? _buildUserMessage(context, msg)
                          : _buildAssistantMessage(context, msg);
                    }
                    return _buildBusyIndicator(context);
                  },
                ),
        ),
        _buildInputDock(context),
      ],
    );
  }
}

class _TutorTypingIndicator extends StatefulWidget {
  const _TutorTypingIndicator()
    : super(key: const Key('tutor-typing-indicator'));

  @override
  State<_TutorTypingIndicator> createState() => _TutorTypingIndicatorState();
}

class _TutorTypingIndicatorState extends State<_TutorTypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
    return Semantics(
      label: 'AI đang trả lời',
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (index) {
            final phase = (_controller.value - index * 0.16) % 1.0;
            final lift = -3.5 * math.sin(phase * math.pi);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2.5),
              child: Transform.translate(
                offset: Offset(0, lift),
                child: Container(
                  key: Key('tutor-typing-dot-$index'),
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.8),
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}
