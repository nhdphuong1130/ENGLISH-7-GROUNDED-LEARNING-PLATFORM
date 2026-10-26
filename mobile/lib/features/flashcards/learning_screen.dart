import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/learning_api.dart';
import '../../services/speech_recorder.dart';
import '../../services/tts_service.dart';
import '../speaking/sentence_practice_screen.dart';
import '../speaking/speaking_screen.dart';
import 'review_screen.dart';


class LearningScreen extends StatefulWidget {
  final LearningApi api;
  const LearningScreen({super.key, required this.api});
  @override
  State<LearningScreen> createState() => _LearningScreenState();
}

class _LearningScreenState extends State<LearningScreen> {
  late Future<List<FlashcardDeck>> _decks;
  bool _speaking = false;
  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _decks = widget.api.loadDecks();
  }

  Future<void> _change(Future<void> Function() action) async {
    try {
      await action();
      if (mounted) setState(_reload);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Không lưu được thay đổi. Vui lòng thử lại.'),
          ),
        );
      }
    }
  }

  Future<void> _name([FlashcardDeck? deck]) async {
    final name = await _editName(context, deck?.name ?? '');
    if (name == null) return;
    await _change(() async {
      if (deck == null) {
        await widget.api.createDeck(name);
      } else {
        await widget.api.renameDeck(deck.id, name);
      }
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Học từ & luyện nói'),
      actions: [
        IconButton(
          tooltip: 'Tải lại',
          onPressed: () => setState(_reload),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: FloatingActionButton.extended(
      onPressed: () => _name(),
      icon: const Icon(Icons.add),
      label: const Text('Tạo bộ từ'),
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: false, label: Text('Flashcard')),
              ButtonSegment(value: true, label: Text('Luyện nói')),
            ],
            selected: {_speaking},
            onSelectionChanged: (s) => setState(() => _speaking = s.first),
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            'Chọn bộ từ SGK hoặc bộ riêng của bạn. Ôn thẻ đến hạn và từ mới mỗi ngày.',
          ),
        ),
        Expanded(
          child: FutureBuilder<List<FlashcardDeck>>(
            future: _decks,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Center(
                  child: TextButton(
                    onPressed: () => setState(_reload),
                    child: const Text('Không tải được bộ từ. Thử lại'),
                  ),
                );
              }
              if (!snapshot.hasData) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.data!.isEmpty) {
                return const Center(
                  child: Text('Chưa có bộ từ. Hãy tạo bộ từ cá nhân.'),
                );
              }
              return ListView.builder(
                padding: const EdgeInsets.only(bottom: 90),
                itemCount: snapshot.data!.length,
                itemBuilder: (context, index) {
                  final deck = snapshot.data![index];
                  return ListTile(
                    title: Text(deck.name),
                    subtitle: Text(
                      '${deck.isPersonal ? "Cá nhân · Riêng tư" : "SGK đã kiểm duyệt"} · ${deck.cardCount} thẻ',
                    ),
                    onTap: () async {
                      await Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => DeckScreen(
                            api: widget.api,
                            deck: deck,
                            speaking: _speaking,
                          ),
                        ),
                      );
                      if (mounted) setState(_reload);
                    },
                    trailing: deck.isPersonal
                        ? PopupMenuButton<String>(
                            onSelected: (value) async {
                              if (value == 'rename') {
                                await _name(deck);
                              } else if (await _confirmDelete(
                                context,
                                'Xóa bộ “${deck.name}” và các thẻ?',
                              )) {
                                await _change(
                                  () => widget.api.deleteDeck(deck.id),
                                );
                              }
                            },
                            itemBuilder: (_) => const [
                              PopupMenuItem(
                                value: 'rename',
                                child: Text('Đổi tên'),
                              ),
                              PopupMenuItem(
                                value: 'delete',
                                child: Text('Xóa bộ'),
                              ),
                            ],
                          )
                        : const Icon(Icons.chevron_right),
                  );
                },
              );
            },
          ),
        ),
      ],
    ),
  );
}

class DeckScreen extends StatefulWidget {
  final LearningApi api;
  final FlashcardDeck deck;
  final bool speaking;
  final SpeechRecorder? audioPlayer;
  final TtsService? ttsService;
  const DeckScreen({
    super.key,
    required this.api,
    required this.deck,
    this.speaking = false,
    this.audioPlayer,
    this.ttsService,
  });
  @override
  State<DeckScreen> createState() => _DeckScreenState();
}

class _DeckScreenState extends State<DeckScreen> {
  late final SpeechRecorder _player =
      widget.audioPlayer ?? createSpeechRecorder();
  late final TtsService _tts = widget.ttsService ?? NativeTtsService();
  late Future<List<Flashcard>> _cards;
  String? _playingCardId;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  @override
  void dispose() {
    unawaited(_player.dispose());
    unawaited(_tts.dispose());
    super.dispose();
  }

  void _reload() {
    _cards = widget.api.loadCards(widget.deck.id);
  }

  Future<void> _playCardAudio(Flashcard card) async {
    if (_playingCardId != null) return;
    setState(() => _playingCardId = card.id);
    try {
      try {
        await _tts.speak(card.word, language: 'en-GB');
      } catch (_) {
        final audioBytes = await widget.api.loadCardAudio(card.id);
        if (mounted) {
          await _player.play(audioBytes);
        }
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Tạm thời chưa phát được âm thanh. Em vẫn có thể tiếp tục xem từ vựng.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _playingCardId = null);
      }
    }
  }

  Future<void> _action(Future<void> Function() work) async {
    try {
      await work();
      if (mounted) setState(_reload);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Không lưu được. Kiểm tra từ trùng hoặc kết nối rồi thử lại.',
            ),
          ),
        );
      }
    }
  }

  Future<void> _edit([Flashcard? card]) async {
    final fields = await showDialog<Map<String, Object?>>(
      context: context,
      builder: (_) => _CardEditor(card: card),
    );
    if (fields == null) return;
    await _action(() async {
      if (card == null) {
        await widget.api.createCard(widget.deck.id, fields);
      } else {
        await widget.api.updateCard(card.id, fields);
      }
    });
  }

  Future<void> _destination(Flashcard card, {required bool copy}) =>
      _action(() async {
        final decks = (await widget.api.loadDecks())
            .where((d) => d.isPersonal && (copy || d.id != widget.deck.id))
            .toList();
        if (!mounted) return;
        final id = await showDialog<String>(
          context: context,
          builder: (context) => SimpleDialog(
            title: Text(copy ? 'Lưu vào bộ cá nhân' : 'Chuyển sang bộ'),
            children: [
              if (decks.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Hãy tạo một bộ cá nhân trước.'),
                ),
              for (final deck in decks)
                SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, deck.id),
                  child: Text(deck.name),
                ),
            ],
          ),
        );
        if (id == null) return;
        if (copy) {
          await widget.api.createCard(id, {
            'word': card.word,
            'meaning': card.meaning,
            'example': card.example,
            'notes': card.notes,
            'image_url': card.imageUrl,
            'source_card_id': card.id,
          });
        } else {
          await widget.api.updateCard(card.id, {'deck_id': id});
        }
      });
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.deck.name)),
    floatingActionButton: widget.deck.isPersonal
        ? FloatingActionButton(
            onPressed: () => _edit(),
            tooltip: 'Thêm từ',
            child: const Icon(Icons.add),
          )
        : null,
    body: Column(
      children: [
        if (!widget.speaking)
          Padding(
            padding: const EdgeInsets.all(12),
            child: FilledButton.icon(
                onPressed: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => ReviewScreen(
                        api: widget.api,
                        deck: widget.deck,
                        audioPlayer: widget.audioPlayer,
                        ttsService: widget.ttsService,
                      ),
                    ),
                  );
                  if (mounted) setState(_reload);
                },
                icon: const Icon(Icons.school),
                label: const Text('Ôn tập bộ thẻ từ vựng'),
              ),
          ),
        if (widget.speaking)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.tonalIcon(
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        onPressed: () async {
                          await Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => SentencePracticeScreen(
                                api: widget.api,
                                deck: widget.deck,
                                recorder: widget.audioPlayer,
                                ttsService: widget.ttsService,
                                isSentenceMode: false,
                              ),
                            ),
                          );
                          if (mounted) setState(_reload);
                        },
                        icon: const Icon(Icons.spellcheck_rounded),
                        label: const Text('Luyện nói từ vựng'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: FilledButton.icon(
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        onPressed: () async {
                          await Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => SentencePracticeScreen(
                                api: widget.api,
                                deck: widget.deck,
                                recorder: widget.audioPlayer,
                                ttsService: widget.ttsService,
                                isSentenceMode: true,
                              ),
                            ),
                          );
                          if (mounted) setState(_reload);
                        },
                        icon: const Icon(Icons.record_voice_over_rounded),
                        label: const Text('Luyện nói cả câu'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                const Text(
                  'Chọn luyện nói từng từ vựng hoặc nói câu hoàn chỉnh theo Unit:',
                  style: TextStyle(fontSize: 12),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        Expanded(
          child: FutureBuilder<List<Flashcard>>(
            future: _cards,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Center(
                  child: TextButton(
                    onPressed: () => setState(_reload),
                    child: const Text('Không tải được thẻ. Thử lại'),
                  ),
                );
              }
              if (!snapshot.hasData) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.data!.isEmpty) {
                return const Center(child: Text('Bộ từ chưa có thẻ.'));
              }
              return ListView(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 90),
                children: snapshot.data!
                    .map(
                      (card) => Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      card.word,
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleLarge,
                                    ),
                                  ),
                                  IconButton(
                                    tooltip: 'Nghe phát âm',
                                    onPressed: _playingCardId == card.id
                                        ? null
                                        : () => _playCardAudio(card),
                                    icon: _playingCardId == card.id
                                        ? const SizedBox(
                                            width: 18,
                                            height: 18,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                            ),
                                          )
                                        : const Icon(Icons.volume_up),
                                  ),
                                  IconButton(
                                    tooltip: card.difficult
                                        ? 'Bỏ đánh dấu khó'
                                        : 'Đánh dấu khó',
                                    onPressed: () => _action(() async {
                                      await widget.api.flagCard(
                                        card.id,
                                        !card.difficult,
                                      );
                                    }),
                                    icon: Icon(
                                      card.difficult
                                          ? Icons.star
                                          : Icons.star_border,
                                    ),
                                  ),
                                  PopupMenuButton<String>(
                                    onSelected: (value) async {
                                      switch (value) {
                                        case 'edit':
                                          await _edit(card);
                                        case 'delete':
                                          if (await _confirmDelete(
                                            context,
                                            'Xóa từ “${card.word}”?',
                                          )) {
                                            await _action(
                                              () => widget.api.deleteCard(
                                                card.id,
                                              ),
                                            );
                                          }
                                        case 'move':
                                          await _destination(card, copy: false);
                                        case 'copy':
                                          await _destination(card, copy: true);
                                      }
                                    },
                                    itemBuilder: (_) => [
                                      if (widget.deck.isPersonal) ...[
                                        const PopupMenuItem(
                                          value: 'edit',
                                          child: Text('Sửa từ'),
                                        ),
                                        const PopupMenuItem(
                                          value: 'move',
                                          child: Text('Chuyển bộ'),
                                        ),
                                        const PopupMenuItem(
                                          value: 'delete',
                                          child: Text('Xóa từ'),
                                        ),
                                      ],
                                      const PopupMenuItem(
                                        value: 'copy',
                                        child: Text('Lưu vào bộ cá nhân'),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                              Text(card.meaning),
                              if (card.ipa != null || card.pos != null)
                                Text('${card.ipa ?? ""} ${card.pos ?? ""}'),
                              if (card.notes.isNotEmpty)
                                Text('Ghi chú: ${card.notes}'),
                              if (card.imageUrl != null)
                                Image.network(
                                  card.imageUrl!,
                                  height: 120,
                                  errorBuilder: (_, error, stack) =>
                                      const Text('Không tải được hình ảnh'),
                                ),
                              Text(card.sourceLabel ?? 'Nội dung cá nhân'),
                              Text(
                                card.reviewCount == 0
                                    ? 'Từ mới'
                                    : card.dueAt == null
                                    ? 'Đã ôn'
                                    : 'Ôn tiếp: ${card.dueAt!.toLocal().toString().split(".").first}',
                              ),
                              if (widget.speaking)
                                TextButton.icon(
                                  onPressed: () => Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => SpeakingScreen(
                                        api: widget.api,
                                        card: card,
                                        recorder: widget.audioPlayer,
                                        ttsService: widget.ttsService,
                                      ),
                                    ),
                                  ),
                                  icon: const Icon(Icons.mic),
                                  label: const Text('Luyện nói từ này'),
                                )
                              else
                                FilledButton.tonalIcon(
                                  onPressed: _playingCardId == card.id
                                      ? null
                                      : () => _playCardAudio(card),
                                  icon: _playingCardId == card.id
                                      ? const SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                          ),
                                        )
                                      : const Icon(Icons.volume_up),
                                  label: const Text('Nghe phát âm tiếng Anh'),
                                ),
                            ],
                          ),
                        ),
                      ),
                    )
                    .toList(),
              );
            },
          ),
        ),
      ],
    ),
  );
}

class _CardEditor extends StatefulWidget {
  final Flashcard? card;
  const _CardEditor({this.card});
  @override
  State<_CardEditor> createState() => _CardEditorState();
}

class _CardEditorState extends State<_CardEditor> {
  final _form = GlobalKey<FormState>();
  late final _fields = <String, TextEditingController>{
    'word': TextEditingController(text: widget.card?.word),
    'meaning': TextEditingController(text: widget.card?.meaning),
    'example': TextEditingController(text: widget.card?.example),
    'notes': TextEditingController(text: widget.card?.notes),
    'image_url': TextEditingController(text: widget.card?.imageUrl),
  };
  @override
  void dispose() {
    for (final c in _fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.card == null ? 'Thêm từ cá nhân' : 'Sửa từ cá nhân'),
    content: SingleChildScrollView(
      child: Form(
        key: _form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final entry in _fields.entries)
              TextFormField(
                controller: entry.value,
                decoration: InputDecoration(
                  labelText: const {
                    'word': 'Từ tiếng Anh',
                    'meaning': 'Nghĩa tiếng Việt',
                    'example': 'Ví dụ (tùy chọn)',
                    'notes': 'Ghi chú (tùy chọn)',
                    'image_url': 'URL hình ảnh (tùy chọn)',
                  }[entry.key],
                ),
                validator: (value) {
                  if ((entry.key == 'word' || entry.key == 'meaning') &&
                      (value?.trim().isEmpty ?? true)) {
                    return 'Vui lòng nhập nội dung';
                  }
                  if (entry.key == 'image_url' &&
                      value != null &&
                      value.isNotEmpty &&
                      !(Uri.tryParse(value)?.scheme == 'https')) {
                    return 'Dùng đường dẫn https';
                  }
                  return null;
                },
              ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Hủy'),
      ),
      FilledButton(
        onPressed: () {
          if (_form.currentState!.validate()) {
            Navigator.pop(context, <String, Object?>{
              for (final entry in _fields.entries)
                entry.key:
                    entry.key == 'image_url' && entry.value.text.trim().isEmpty
                    ? null
                    : entry.value.text.trim(),
            });
          }
        },
        child: const Text('Lưu'),
      ),
    ],
  );
}

Future<String?> _editName(BuildContext context, String current) async {
  var name = current;
  return showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Tên bộ cá nhân'),
      content: TextFormField(
        initialValue: current,
        onChanged: (value) => name = value,
        autofocus: true,
        maxLength: 120,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Hủy'),
        ),
        FilledButton(
          onPressed: () {
            if (name.trim().isNotEmpty) {
              Navigator.pop(context, name.trim());
            }
          },
          child: const Text('Lưu'),
        ),
      ],
    ),
  );
}

Future<bool> _confirmDelete(BuildContext context, String message) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(message),
        content: const Text('Thao tác này không thể hoàn tác.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Hủy'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Xóa'),
          ),
        ],
      ),
    ) ??
    false;
