import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../api/api_error.dart';
import '../../app/learning_api.dart';
import '../../services/speech_recorder.dart';
import '../../services/tts_service.dart';

class SentencePracticeItem {
  final Flashcard card;
  final String sentence;

  const SentencePracticeItem({
    required this.card,
    required this.sentence,
  });
}

class SentencePracticeScreen extends StatefulWidget {
  final LearningApi api;
  final FlashcardDeck deck;
  final SpeechRecorder? recorder;
  final TtsService? ttsService;
  final bool isSentenceMode;

  const SentencePracticeScreen({
    super.key,
    required this.api,
    required this.deck,
    this.recorder,
    this.ttsService,
    this.isSentenceMode = true,
  });

  @override
  State<SentencePracticeScreen> createState() => _SentencePracticeScreenState();
}

class _SentencePracticeScreenState extends State<SentencePracticeScreen> {
  late final SpeechRecorder _recorder =
      widget.recorder ?? NativeSpeechRecorder();
  late final TtsService _tts = widget.ttsService ?? NativeTtsService();

  List<SentencePracticeItem> _items = [];
  bool _loadingCards = true;
  String? _initError;

  int _index = 0;
  int _failCount = 0;
  int _completedCount = 0;
  double _totalScore = 0.0;

  bool _recording = false;
  bool _submitting = false;
  SpeakingResult? _result;
  String? _error;
  String? _requestId;
  String? _voice;
  String? _activeTappedWord;

  Timer? _recordingTimer;
  Timer? _autoAdvanceTimer;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _recordingTimer?.cancel();
    _autoAdvanceTimer?.cancel();
    unawaited(_recorder.dispose());
    unawaited(_tts.dispose());
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _loadingCards = true;
      _initError = null;
    });

    try {
      final cards = await widget.api.loadCards(widget.deck.id);
      SpeakingVoices? voices;
      try {
        voices = await widget.api.loadVoices();
      } catch (_) {
        // Voices runtime might be offline or unreachable
      }

      final items = cards.map((c) {
        final text = widget.isSentenceMode
            ? (c.example.trim().isNotEmpty
                ? c.example.trim()
                : 'My favourite ${c.word} is very interesting.')
            : c.word.trim();
        return SentencePracticeItem(card: c, sentence: text);
      }).toList();

      if (mounted) {
        setState(() {
          _items = items;
          final availableVoices = voices?.items ?? [];
          _voice = availableVoices.any((v) => v.id == voices?.selectedVoice)
              ? voices?.selectedVoice
              : (availableVoices.firstOrNull?.id ?? 'en-GB-SoniaNeural');
          _loadingCards = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _initError = 'Không thể tải danh sách luyện nói. Hãy thử lại.';
          _loadingCards = false;
        });
      }
    }
  }

  SentencePracticeItem? get _currentItem {
    if (_index >= 0 && _index < _items.length) {
      return _items[_index];
    }
    return null;
  }

  List<String> get _promptWords {
    final item = _currentItem;
    if (item == null) return [];
    return item.sentence
        .split(RegExp(r'\s+'))
        .where((w) => w.trim().isNotEmpty)
        .toList();
  }

  String _clean(String w) =>
      w.toLowerCase().replaceAll(RegExp(r"[^a-z0-9']"), '');

  WordEvaluation? _getWordEvaluation(String word, int wordIndex) {
    final evals = _result?.wordEvaluations;
    if (evals == null || evals.isEmpty) return null;
    final clean = _clean(word);
    if (clean.isEmpty) return null;

    if (wordIndex < evals.length && _clean(evals[wordIndex].word) == clean) {
      return evals[wordIndex];
    }
    for (final e in evals) {
      if (_clean(e.word) == clean) return e;
    }
    return null;
  }

  Future<void> _speakPrompt({double rate = 0.48}) async {
    final item = _currentItem;
    if (item == null || _recording || _submitting) return;

    try {
      await _tts.speak(item.sentence, language: 'en-GB', rate: rate);
    } catch (_) {
      // Ignored if device TTS unavailable
    }
  }

  Future<void> _speakWord(String word) async {
    final cleanWord = word.replaceAll(RegExp(r"[^a-zA-Z0-9']"), '');
    if (cleanWord.isEmpty || _recording || _submitting) return;

    setState(() => _activeTappedWord = word);
    try {
      await _tts.speak(cleanWord, language: 'en-GB', rate: 0.42);
    } catch (_) {
      // Ignored if device TTS unavailable
    } finally {
      if (mounted) {
        Future.delayed(const Duration(milliseconds: 400), () {
          if (mounted) setState(() => _activeTappedWord = null);
        });
      }
    }
  }

  Future<void> _startRecording() async {
    if (_recording || _submitting) return;
    _autoAdvanceTimer?.cancel();

    setState(() {
      _recording = true;
      _submitting = false;
      _result = null;
      _error = null;
      _requestId = null;
    });

    try {
      await _recorder.start();
      _recordingTimer = Timer(const Duration(seconds: 15), () {
        if (mounted && _recording) {
          _stopAndSubmit();
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _recording = false;
          _error = e is SpeechRecordingException
              ? e.message
              : 'Không thể bắt đầu thu âm. Kiểm tra quyền micro.';
        });
      }
    }
  }

  Future<void> _stopAndSubmit() async {
    if (!_recording) return;
    _recordingTimer?.cancel();

    Uint8List? audioBytes;
    try {
      audioBytes = await _recorder.stop();
    } catch (e) {
      if (mounted) {
        setState(() {
          _recording = false;
          _error = 'Lỗi thu âm: $e';
        });
      }
      return;
    }

    if (!mounted) return;

    if (audioBytes.isEmpty) {
      setState(() {
        _recording = false;
        _error = 'Bản thu rỗng. Hãy thử nói lại.';
      });
      return;
    }

    final item = _currentItem;
    if (item == null) {
      setState(() => _recording = false);
      return;
    }

    setState(() {
      _recording = false;
      _submitting = true;
      _error = null;
    });

    _requestId ??= learningRequestId();
    final voiceId = _voice ?? 'en-GB-SoniaNeural';

    try {
      final res = await widget.api.submitSpeaking(
        requestId: _requestId!,
        cardId: item.card.id,
        voiceId: voiceId,
        audio: audioBytes,
        prompt: item.sentence,
      );

      if (mounted) {
        final isPassed = res.matchPercent >= 80.0;
        setState(() {
          _submitting = false;
          _result = res;
          if (isPassed) {
            _completedCount++;
            _totalScore += res.matchPercent;
          } else {
            _failCount++;
          }
        });

        // If >= 80%, auto-advance after 1.8 seconds!
        if (isPassed) {
          _autoAdvanceTimer = Timer(const Duration(milliseconds: 1800), () {
            if (mounted) {
              _nextItem();
            }
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _submitting = false;
          _error = e is ApiException &&
                  const {
                    'no_speech',
                    'invalid_recording',
                    'recording_too_large',
                  }.contains(e.code)
              ? 'Chưa nghe rõ bản thu. Em hãy thử lại và đọc to trong 15 giây.'
              : 'Không gửi được bản thu. Kiểm tra kết nối mạng và thử lại.';
        });
      }
    }
  }

  void _skipItem() {
    // Only allow skipping if user failed >= 5 times
    if (_failCount < 5) return;
    _recordingTimer?.cancel();
    _autoAdvanceTimer?.cancel();
    if (_recording) {
      unawaited(_recorder.stop());
      _recording = false;
    }
    _nextItem();
  }

  void _nextItem() {
    _autoAdvanceTimer?.cancel();
    setState(() {
      _index++;
      _result = null;
      _error = null;
      _requestId = null;
      _failCount = 0;
      _submitting = false;
      _recording = false;
    });
  }

  void _retry() {
    _autoAdvanceTimer?.cancel();
    setState(() {
      _result = null;
      _error = null;
    });
    _startRecording();
  }

  Widget _buildWordChip(String word, int wordIndex) {
    final ev = _getWordEvaluation(word, wordIndex);
    Color? bg;
    Color? fg;
    Color? border;

    if (ev != null) {
      if (ev.status == 'correct') {
        bg = const Color(0xFFDCFCE7);
        fg = const Color(0xFF166534);
        border = const Color(0xFF86EFAC);
      } else if (ev.status == 'near') {
        bg = const Color(0xFFFEF3C7);
        fg = const Color(0xFF92400E);
        border = const Color(0xFFFDE68A);
      } else {
        bg = const Color(0xFFFEE2E2);
        fg = const Color(0xFF991B1B);
        border = const Color(0xFFFCA5A5);
      }
    }

    final isTapped = _activeTappedWord == word;

    return ActionChip(
      avatar: isTapped
          ? const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.volume_up, size: 14),
      label: Text(
        word,
        style: TextStyle(
          fontWeight: FontWeight.w600,
          color: fg,
        ),
      ),
      backgroundColor: isTapped
          ? Theme.of(context).colorScheme.primaryContainer
          : bg,
      side: border != null ? BorderSide(color: border) : null,
      onPressed: _recording || _submitting ? null : () => _speakWord(word),
    );
  }

  @override
  Widget build(BuildContext context) {
    final modeLabel = widget.isSentenceMode ? 'câu' : 'từ vựng';
    final titlePrefix = widget.isSentenceMode ? 'Luyện nói câu' : 'Luyện nói từ vựng';

    if (_loadingCards) {
      return Scaffold(
        appBar: AppBar(title: Text('$titlePrefix - ${widget.deck.name}')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_initError != null) {
      return Scaffold(
        appBar: AppBar(title: Text('$titlePrefix - ${widget.deck.name}')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(_initError!),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadData,
                child: const Text('Tải lại'),
              ),
            ],
          ),
        ),
      );
    }

    if (_items.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: Text('$titlePrefix - ${widget.deck.name}')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.info_outline, size: 48, color: Colors.grey),
              const SizedBox(height: 12),
              Text('Bộ từ này chưa có $modeLabel để luyện nói.'),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Quay lại'),
              ),
            ],
          ),
        ),
      );
    }

    // Finished all items: summary screen!
    if (_index >= _items.length) {
      final avgScore = _completedCount > 0
          ? (_totalScore / _completedCount).toStringAsFixed(0)
          : '0';

      return Scaffold(
        appBar: AppBar(
          title: const Text('Kết quả luyện nói'),
          automaticallyImplyLeading: false,
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: const BoxDecoration(
                    color: Color(0xFFFEF3C7),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.emoji_events_rounded,
                    size: 72,
                    color: Color(0xFFD97706),
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  '🎉 Hoàn thành bài luyện nói $modeLabel!',
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 10),
                Text(
                  'Bạn đã hoàn thành các $modeLabel trong ${widget.deck.name}.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 24),
                Card(
                  elevation: 0,
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 24,
                      vertical: 16,
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('Số $modeLabel đạt yêu cầu:'),
                            Text(
                              '$_completedCount / ${_items.length}',
                              style: const TextStyle(fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                        const Divider(height: 20),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('Điểm trung bình:'),
                            Text(
                              '$avgScore%',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF166534),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 32),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () {
                      setState(() {
                        _index = 0;
                        _completedCount = 0;
                        _totalScore = 0.0;
                        _failCount = 0;
                        _result = null;
                        _error = null;
                      });
                    },
                    icon: const Icon(Icons.refresh),
                    label: const Text('Luyện tập lại từ đầu'),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Quay lại danh sách bộ từ'),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final currentItem = _currentItem!;
    final progress = (_index + 1) / _items.length;
    final isPassed = _result != null && _result!.matchPercent >= 80.0;
    final isFailed = _result != null && _result!.matchPercent < 80.0;

    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.deck.name} • $titlePrefix'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          tooltip: 'Thoát',
          onPressed: () => Navigator.of(context).pop(),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(6),
          child: LinearProgressIndicator(
            value: progress,
            backgroundColor: Colors.grey.shade200,
            valueColor: AlwaysStoppedAnimation<Color>(
              Theme.of(context).colorScheme.primary,
            ),
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                children: [
                  // Progress header
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '${widget.isSentenceMode ? "Câu" : "Từ"} ${_index + 1} / ${_items.length}',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                      if (currentItem.card.sourceLabel != null)
                        Text(
                          currentItem.card.sourceLabel!,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey.shade600,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Prompt instruction banner
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primaryContainer,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          widget.isSentenceMode
                              ? Icons.record_voice_over_rounded
                              : Icons.spellcheck_rounded,
                          size: 20,
                          color: Theme.of(context).colorScheme.onPrimaryContainer,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          widget.isSentenceMode
                              ? 'Lắng nghe và đọc to câu hoàn chỉnh sau:'
                              : 'Lắng nghe và phát âm từ vựng sau:',
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Content Target Card
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: isPassed
                            ? const Color(0xFF86EFAC)
                            : isFailed
                                ? const Color(0xFFFCA5A5)
                                : Theme.of(context).colorScheme.outlineVariant,
                        width: isPassed || isFailed ? 2.0 : 1.0,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.04),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (widget.isSentenceMode) ...[
                          // Câu mẫu liền mạch (Continuous model sentence - User screenshot requirement)
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: Theme.of(context)
                                  .colorScheme
                                  .primaryContainer
                                  .withValues(alpha: 0.22),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: Theme.of(context)
                                    .colorScheme
                                    .primary
                                    .withValues(alpha: 0.3),
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
                                      color: Theme.of(context).colorScheme.primary,
                                    ),
                                    const SizedBox(width: 6),
                                    Text(
                                      'Câu mẫu liền mạch:',
                                      style: TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                        color: Theme.of(context).colorScheme.primary,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  currentItem.sentence,
                                  style: TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w700,
                                    color: Theme.of(context).colorScheme.onSurface,
                                    height: 1.45,
                                    letterSpacing: 0.2,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 14),

                          // Interactive Word chips breakdown
                          Text(
                            'Chạm từng từ để nghe phát âm chi tiết:',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              for (int i = 0; i < _promptWords.length; i++)
                                _buildWordChip(_promptWords[i], i),
                            ],
                          ),
                        ] else ...[
                          // Từ vựng liền mạch (Single Word Practice)
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 18,
                            ),
                            decoration: BoxDecoration(
                              color: Theme.of(context)
                                  .colorScheme
                                  .primaryContainer
                                  .withValues(alpha: 0.22),
                              borderRadius: BorderRadius.circular(14),
                              border: Border.all(
                                color: Theme.of(context)
                                    .colorScheme
                                    .primary
                                    .withValues(alpha: 0.3),
                              ),
                            ),
                            child: Column(
                              children: [
                                Text(
                                  currentItem.card.word,
                                  style: TextStyle(
                                    fontSize: 32,
                                    fontWeight: FontWeight.w800,
                                    color: Theme.of(context).colorScheme.primary,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                                if (currentItem.card.ipa != null &&
                                    currentItem.card.ipa!.isNotEmpty) ...[
                                  const SizedBox(height: 4),
                                  Text(
                                    currentItem.card.ipa!,
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontStyle: FontStyle.italic,
                                      fontFamily: 'monospace',
                                      color: Theme.of(context).colorScheme.secondary,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ],

                        const SizedBox(height: 14),
                        const Divider(),
                        const SizedBox(height: 8),

                        // Audio sample controls
                        Row(
                          children: [
                            FilledButton.tonalIcon(
                              onPressed: _recording || _submitting
                                  ? null
                                  : () => _speakPrompt(rate: 0.48),
                              icon: const Icon(Icons.volume_up_rounded, size: 18),
                              label: const Text('Nghe mẫu (1.0x)'),
                            ),
                            const SizedBox(width: 8),
                            IconButton.filledTonal(
                              onPressed: _recording || _submitting
                                  ? null
                                  : () => _speakPrompt(rate: 0.32),
                              icon: const Icon(Icons.slow_motion_video_rounded),
                              tooltip: 'Nghe chậm (0.5x)',
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),

                        // Context: Vietnamese meaning
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest
                                .withValues(alpha: 0.5),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            widget.isSentenceMode
                                ? 'Từ trọng tâm: "${currentItem.card.word}" • Nghĩa: ${currentItem.card.meaning}'
                                : 'Nghĩa từ: ${currentItem.card.meaning}',
                            style: TextStyle(
                              fontSize: 12.5,
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Error notice if any
                  if (_error != null)
                    Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF2F2),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: const Color(0xFFFCA5A5)),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.error_outline,
                            color: Color(0xFFDC2626),
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _error!,
                              style: const TextStyle(
                                fontSize: 13,
                                color: Color(0xFF991B1B),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),

                  // Result Evaluation Card
                  if (_result != null) ...[
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: isPassed
                            ? const Color(0xFFF0FDF4)
                            : const Color(0xFFFFFBEB),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: isPassed
                              ? const Color(0xFF86EFAC)
                              : const Color(0xFFFCD34D),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                isPassed
                                    ? Icons.check_circle_rounded
                                    : Icons.info_outline_rounded,
                                color: isPassed
                                    ? const Color(0xFF16A34A)
                                    : const Color(0xFFD97706),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  isPassed
                                      ? '🎉 Xuất sắc! Đạt ${_result!.matchPercent.toInt()}%'
                                      : '⚠️ Đạt ${_result!.matchPercent.toInt()}% (Cần đạt ≥ 80%)',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                    color: isPassed
                                        ? const Color(0xFF166534)
                                        : const Color(0xFF92400E),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _result!.feedback,
                            style: TextStyle(
                              fontSize: 13,
                              color: isPassed
                                  ? const Color(0xFF15803D)
                                  : const Color(0xFF78350F),
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Bản thu ghi nhận: "${_result!.transcript}"',
                            style: TextStyle(
                              fontSize: 12,
                              fontStyle: FontStyle.italic,
                              color: Colors.grey.shade700,
                            ),
                          ),
                          if (isPassed) ...[
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  'Tự động chuyển $modeLabel tiếp theo...',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.green.shade800,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ],
                          if (isFailed) ...[
                            const SizedBox(height: 8),
                            if (_failCount >= 5)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 8,
                                ),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFEF3C7),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                    color: const Color(0xFFFDE68A),
                                  ),
                                ),
                                child: const Row(
                                  children: [
                                    Icon(
                                      Icons.info_outline,
                                      size: 18,
                                      color: Color(0xFF92400E),
                                    ),
                                    SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        'Bạn đã thử 5 lần chưa đạt. Bạn có thể bấm "Bỏ qua ➔" để sang phần tiếp theo hoặc bấm "Thử lại ↻".',
                                        style: TextStyle(
                                          fontSize: 12,
                                          color: Color(0xFF92400E),
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              )
                            else
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 6,
                                ),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFEF3C7),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  '💡 Bạn đã phát âm chưa đạt $_failCount/5 lần. Cần thử lại ít nhất 5 lần nếu muốn bỏ qua.',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: Color(0xFF92400E),
                                  ),
                                ),
                              ),
                          ],
                        ],
                      ),
                    ),
                  ],

                  if (_submitting) ...[
                    const SizedBox(height: 16),
                    const Center(
                      child: Column(
                        children: [
                          CircularProgressIndicator(),
                          SizedBox(height: 10),
                          Text(
                            'Đang chấm điểm bản thu phát âm...',
                            style: TextStyle(fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),

            // Bottom Bar with Controls
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                border: Border(
                  top: BorderSide(
                    color: Theme.of(context).colorScheme.outlineVariant,
                    width: 0.8,
                  ),
                ),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Hint message
                  if (_recording)
                    const Padding(
                      padding: EdgeInsets.only(bottom: 8),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.mic, color: Colors.red, size: 16),
                          SizedBox(width: 6),
                          Text(
                            'Đang thu âm... Hãy bấm "Dừng thu" để chấm điểm.',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.red,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    )
                  else if (!isPassed && !isFailed)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(
                        widget.isSentenceMode
                            ? 'Bấm "Thu âm" và đọc cả câu. Bấm "Dừng thu" để hệ thống tự động gửi.'
                            : 'Bấm "Thu âm" và phát âm từ vựng. Bấm "Dừng thu" để hệ thống tự động gửi.',
                        style: const TextStyle(fontSize: 12, color: Colors.grey),
                        textAlign: TextAlign.center,
                      ),
                    ),

                  // Button Rows
                  if (_recording) ...[
                    SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: FilledButton.icon(
                        style: FilledButton.styleFrom(
                          backgroundColor: Colors.red.shade600,
                        ),
                        onPressed: _stopAndSubmit,
                        icon: const Icon(Icons.stop),
                        label: const Text(
                          'Dừng thu & Chấm điểm',
                          style: TextStyle(fontSize: 16),
                        ),
                      ),
                    ),
                  ] else if (isPassed) ...[
                    SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: FilledButton.icon(
                        style: FilledButton.styleFrom(
                          backgroundColor: const Color(0xFF16A34A),
                        ),
                        onPressed: _nextItem,
                        icon: const Icon(Icons.arrow_forward),
                        label: const Text(
                          'Tiếp tục ngay ➔',
                          style: TextStyle(fontSize: 16),
                        ),
                      ),
                    ),
                  ] else if (isFailed) ...[
                    if (_failCount >= 5) ...[
                      Row(
                        children: [
                          Expanded(
                            flex: 1,
                            child: OutlinedButton.icon(
                              style: OutlinedButton.styleFrom(
                                minimumSize: const Size.fromHeight(48),
                              ),
                              onPressed: _skipItem,
                              icon: const Icon(Icons.skip_next),
                              label: const Text('Bỏ qua ➔'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            flex: 2,
                            child: FilledButton.icon(
                              style: FilledButton.styleFrom(
                                minimumSize: const Size.fromHeight(48),
                              ),
                              onPressed: _retry,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Thử lại ↻'),
                            ),
                          ),
                        ],
                      ),
                    ] else ...[
                      SizedBox(
                        width: double.infinity,
                        height: 48,
                        child: FilledButton.icon(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                          ),
                          onPressed: _retry,
                          icon: const Icon(Icons.refresh),
                          label: Text('Thử lại ↻ (Lần $_failCount/5)'),
                        ),
                      ),
                    ],
                  ] else ...[
                    SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: FilledButton.icon(
                        style: FilledButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                        ),
                        onPressed: _submitting ? null : _startRecording,
                        icon: const Icon(Icons.mic),
                        label: const Text(
                          'Thu âm',
                          style: TextStyle(fontSize: 16),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
