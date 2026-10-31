import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../app/learning_api.dart';
import '../../services/speech_recorder.dart';
import '../../services/tts_service.dart';
import 'practice_session_store.dart';

class ReviewScreen extends StatefulWidget {
  final LearningApi api;
  final FlashcardDeck deck;
  final SpeechRecorder? audioPlayer;
  final TtsService? ttsService;
  final PracticeSessionStore? sessionStore;

  const ReviewScreen({
    super.key,
    required this.api,
    required this.deck,
    this.audioPlayer,
    this.ttsService,
    this.sessionStore,
  });

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen>
    with TickerProviderStateMixin {
  late final SpeechRecorder _player =
      widget.audioPlayer ?? createSpeechRecorder();
  late final TtsService _tts = widget.ttsService ?? NativeTtsService();
  late final PracticeSessionStore _sessionStore =
      widget.sessionStore ?? const PracticeSessionStore();
  late Future<List<Flashcard>> _cards;
  final List<String> _ratings = [];
  bool _checkedSession = false;

  late final AnimationController _flipController;
  late final Animation<double> _flipAnimation;

  late final AnimationController _springController;
  Animation<Offset>? _springAnimation;

  int _index = 0;
  bool _revealed = false;
  bool _busy = false;
  bool _playingAudio = false;
  bool _isSwipingOut = false;

  String? _error;
  String? _requestId;
  String? _rating;
  String? _submittedAnswer;

  Offset _dragOffset = Offset.zero;

  @override
  void initState() {
    super.initState();
    _cards = widget.api.loadCards(widget.deck.id);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkSavedSession();
    });

    _flipController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 320),
    );
    _flipAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _flipController, curve: Curves.easeInOut),
    );

    _springController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 240),
    );
    _springController.addListener(() {
      if (_springAnimation != null) {
        setState(() {
          _dragOffset = _springAnimation!.value;
        });
      }
    });
  }

  Future<void> _checkSavedSession() async {
    if (_checkedSession) return;
    _checkedSession = true;
    try {
      final cards = await _cards;
      if (!mounted) return;
      final saved = await _sessionStore.load(widget.deck.id, 'flashcard');
      if (saved != null &&
          saved.currentIndex > 0 &&
          saved.currentIndex < cards.length) {
        if (!mounted) return;
        final shouldResume = await showDialog<bool>(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
            title: const Text('Tiếp tục bài học?'),
            content: Text(
              'Em đang học dở đến thẻ ${saved.currentIndex + 1}/${saved.totalCards}. Em có muốn tiếp tục không?',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: const Text('Học lại từ đầu'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                child: const Text('Tiếp tục'),
              ),
            ],
          ),
        );
        if (shouldResume == true && mounted) {
          setState(() {
            _index = saved.currentIndex;
            _ratings.clear();
            _ratings.addAll(saved.ratings);
          });
        } else if (mounted) {
          await _sessionStore.clear(widget.deck.id, 'flashcard');
          setState(() {
            _index = 0;
            _ratings.clear();
          });
        }
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _flipController.dispose();
    _springController.dispose();
    unawaited(_player.dispose());
    unawaited(_tts.dispose());
    super.dispose();
  }

  void _toggleFlip() {
    if (_busy || _isSwipingOut) return;
    if (_revealed) {
      _flipController.reverse();
      setState(() => _revealed = false);
    } else {
      _flipController.forward();
      setState(() => _revealed = true);
    }
  }

  Future<void> _playCardAudio(Flashcard card) async {
    if (_playingAudio) return;
    setState(() => _playingAudio = true);
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
              'Tạm thời chưa phát được âm thanh. Em vẫn có thể tiếp tục ôn từ.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _playingAudio = false);
      }
    }
  }

  Future<bool> _rate(Flashcard card, String rating) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    _requestId ??= learningRequestId();
    _rating ??= rating;
    _submittedAnswer ??= '';
    try {
      await widget.api.reviewCard(
        card.id,
        requestId: _requestId!,
        answer: _submittedAnswer!,
        rating: _rating!,
      );
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
      return true;
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Chưa lưu được. Bấm thử lại để gửi kết quả ôn tập.';
          _busy = false;
        });
      }
      return false;
    }
  }

  Future<void> _swipeAndRate(Flashcard card, String rating) async {
    if (_busy || _isSwipingOut) return;
    _isSwipingOut = true;

    final targetDx = rating == 'good' ? 520.0 : -520.0;
    final currentOffset = _dragOffset;

    _springAnimation = Tween<Offset>(
      begin: currentOffset,
      end: Offset(targetDx, currentOffset.dy * 0.3),
    ).animate(CurvedAnimation(parent: _springController, curve: Curves.easeOutCubic));

    _springController.reset();
    await _springController.forward();

    final ok = await _rate(card, rating);
    if (!ok) {
      _isSwipingOut = false;
      _springAnimation = Tween<Offset>(
        begin: _dragOffset,
        end: Offset.zero,
      ).animate(CurvedAnimation(parent: _springController, curve: Curves.easeOutBack));
      _springController.reset();
      await _springController.forward();
      return;
    }

    _ratings.add(rating);
    final nextIndex = _index + 1;
    final cards = await _cards;
    if (nextIndex < cards.length) {
      unawaited(_sessionStore.save(PracticeSessionState(
        deckId: widget.deck.id,
        mode: 'flashcard',
        currentIndex: nextIndex,
        totalCards: cards.length,
        ratings: List<String>.from(_ratings),
        scores: const [],
        attempts: const [],
        updatedAt: DateTime.now(),
      )));
    } else {
      unawaited(_sessionStore.clear(widget.deck.id, 'flashcard'));
    }

    _next();
    _dragOffset = Offset.zero;
    _isSwipingOut = false;
  }

  void _springBack() {
    _springAnimation = Tween<Offset>(
      begin: _dragOffset,
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _springController, curve: Curves.easeOutBack));
    _springController.reset();
    _springController.forward();
  }

  void _next() {
    setState(() {
      _index++;
      _revealed = false;
      _playingAudio = false;
      _requestId = null;
      _rating = null;
      _submittedAnswer = null;
      _error = null;
      _dragOffset = Offset.zero;
      _flipController.reset();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F3ED),
      appBar: AppBar(
        title: Text(widget.deck.name),
        elevation: 0,
        backgroundColor: Colors.transparent,
      ),
      body: FutureBuilder<List<Flashcard>>(
        future: _cards,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Không tải được thẻ từ vựng.'),
                  const SizedBox(height: 12),
                  FilledButton.tonal(
                    onPressed: () => setState(() {
                      _cards = widget.api.loadCards(widget.deck.id);
                    }),
                    child: const Text('Thử lại'),
                  ),
                ],
              ),
            );
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final cards = snapshot.data!;
          if (_index >= cards.length) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(22),
                      decoration: const BoxDecoration(
                        color: Color(0xFFFEF3C7),
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.emoji_events_rounded,
                        size: 56,
                        color: Color(0xFFD97706),
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Hoàn thành xuất sắc!',
                      style: TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF1E293B),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Em đã ôn xong tất cả ${cards.length} thẻ từ vựng trong lượt này.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 15,
                        color: Color(0xFF64748B),
                      ),
                    ),
                    const SizedBox(height: 28),
                    FilledButton.icon(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.check_rounded),
                      label: const Text('Trở về danh sách thẻ'),
                    ),
                  ],
                ),
              ),
            );
          }

          final card = cards[_index];
          final masteredCount = _ratings.where((r) => r == 'good').length;
          final masteryPercent =
              cards.isEmpty ? 0 : ((masteredCount / cards.length) * 100).round();
          Color masteryColor;
          if (masteryPercent >= 70) {
            masteryColor = const Color(0xFF16A34A);
          } else if (masteryPercent >= 50) {
            masteryColor = const Color(0xFFD97706);
          } else {
            masteryColor = const Color(0xFFDC2626);
          }

          return LayoutBuilder(
            builder: (context, constraints) {
              final cardWidth = min(constraints.maxWidth - 48, 350.0);
              const cardHeight = 240.0;
              const holeCenter = Offset(38, 32);

              return Column(
                children: [
                  // Top progress indicator
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Thẻ ${_index + 1} / ${cards.length}',
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFF64748B),
                              ),
                            ),
                            Text(
                              'Đã thuộc: $masteredCount/${cards.length} ($masteryPercent%)',
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
                                color: masteryColor,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: List.generate(cards.length, (i) {
                            Color segmentColor;
                            if (i < _ratings.length) {
                              segmentColor = _ratings[i] == 'good'
                                  ? const Color(0xFF16A34A)
                                  : const Color(0xFFDC2626);
                            } else if (i == _index) {
                              segmentColor = const Color(0xFF93C5FD);
                            } else {
                              segmentColor = const Color(0xFFE2E8F0);
                            }
                            return Expanded(
                              child: Container(
                                height: 6,
                                margin: EdgeInsets.only(
                                  left: i == 0 ? 0 : 2,
                                  right: i == cards.length - 1 ? 0 : 2,
                                ),
                                decoration: BoxDecoration(
                                  color: segmentColor,
                                  borderRadius: BorderRadius.circular(3),
                                ),
                              ),
                            );
                          }),
                        ),
                      ],
                    ),
                  ),

                  const Spacer(),

                  // Physical Ring-Binder Flashcard Stack
                  SizedBox(
                    width: cardWidth + 30,
                    height: cardHeight + 40,
                    child: Stack(
                      clipBehavior: Clip.none,
                      alignment: Alignment.center,
                      children: [
                        // Background half of the metal binder ring
                        Positioned(
                          left: (cardWidth + 30 - cardWidth) / 2,
                          top: 20,
                          child: IgnorePointer(
                            child: CustomPaint(
                              size: Size(cardWidth, cardHeight),
                              painter: _BinderRingPainter(
                                isForeground: false,
                                holeCenter: holeCenter,
                              ),
                            ),
                          ),
                        ),

                        // Fanned dummy cards underneath
                        Positioned(
                          left: (cardWidth + 30 - cardWidth) / 2,
                          top: 20,
                          child: Transform(
                            alignment: const Alignment(-0.78, -0.72),
                            transform: Matrix4.translationValues(-8.0, 10.0, 0.0)
                              ..rotateZ(-0.14),
                            child: _buildDummyCard(
                              width: cardWidth,
                              height: cardHeight,
                              color: const Color(0xFFEDE6DA),
                            ),
                          ),
                        ),
                        Positioned(
                          left: (cardWidth + 30 - cardWidth) / 2,
                          top: 20,
                          child: Transform(
                            alignment: const Alignment(-0.78, -0.72),
                            transform: Matrix4.translationValues(-4.0, 5.0, 0.0)
                              ..rotateZ(-0.07),
                            child: _buildDummyCard(
                              width: cardWidth,
                              height: cardHeight,
                              color: const Color(0xFFF5EFE4),
                            ),
                          ),
                        ),

                        // Active Interactive Flashcard
                        Positioned(
                          left: (cardWidth + 30 - cardWidth) / 2,
                          top: 20,
                          child: Transform.translate(
                            offset: Offset(_dragOffset.dx, _dragOffset.dy * 0.25),
                            child: Transform.rotate(
                              angle: _dragOffset.dx * 0.0007,
                              child: GestureDetector(
                                onTap: _toggleFlip,
                                onPanStart: (details) {
                                  if (_busy || _isSwipingOut) return;
                                  _springController.stop();
                                },
                                onPanUpdate: (details) {
                                  if (_busy || _isSwipingOut) return;
                                  setState(() => _dragOffset += details.delta);
                                },
                                onPanEnd: (details) {
                                  if (_busy || _isSwipingOut) return;
                                  const threshold = 110.0;
                                  if (_dragOffset.dx > threshold) {
                                    _swipeAndRate(card, 'good');
                                  } else if (_dragOffset.dx < -threshold) {
                                    _swipeAndRate(card, 'again');
                                  } else {
                                    _springBack();
                                  }
                                },
                                child: Stack(
                                  clipBehavior: Clip.none,
                                  children: [
                                    // 3D Flip Card Widget
                                    AnimatedBuilder(
                                      animation: _flipAnimation,
                                      builder: (context, child) {
                                        final angle = _flipAnimation.value * pi;
                                        final isFront = angle < pi / 2;
                                        return Transform(
                                          alignment: Alignment.center,
                                          transform: Matrix4.identity()
                                            ..setEntry(3, 2, 0.0012)
                                            ..rotateY(angle),
                                          child: isFront
                                              ? _buildFrontCard(
                                                  card,
                                                  cardWidth,
                                                  cardHeight,
                                                  holeCenter,
                                                )
                                              : Transform(
                                                  alignment: Alignment.center,
                                                  transform: Matrix4.identity()
                                                    ..rotateY(pi),
                                                  child: _buildBackCard(
                                                    card,
                                                    cardWidth,
                                                    cardHeight,
                                                    holeCenter,
                                                  ),
                                                ),
                                        );
                                      },
                                    ),

                                    // Drag stamp badge: ĐÃ NHỚ (Green)
                                    if (_dragOffset.dx > 25)
                                      Positioned(
                                        top: 24,
                                        left: 55,
                                        child: _buildStamp(
                                          text: 'ĐÃ NHỚ',
                                          color: const Color(0xFF16A34A),
                                          angle: -0.2,
                                          opacity: ((_dragOffset.dx - 25) / 80)
                                              .clamp(0.0, 1.0),
                                        ),
                                      ),

                                    // Drag stamp badge: CHƯA NHỚ (Red)
                                    if (_dragOffset.dx < -25)
                                      Positioned(
                                        top: 24,
                                        right: 24,
                                        child: _buildStamp(
                                          text: 'CHƯA NHỚ',
                                          color: const Color(0xFFDC2626),
                                          angle: 0.2,
                                          opacity: ((-_dragOffset.dx - 25) / 80)
                                              .clamp(0.0, 1.0),
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),

                        // Foreground half of the metal binder ring (enters hole over card)
                        Positioned(
                          left: (cardWidth + 30 - cardWidth) / 2,
                          top: 20,
                          child: IgnorePointer(
                            child: CustomPaint(
                              size: Size(cardWidth, cardHeight),
                              painter: _BinderRingPainter(
                                isForeground: true,
                                holeCenter: holeCenter,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const Spacer(),

                  // Error & Status message
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF2F2),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFFFCA5A5)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.error_outline, color: Color(0xFFDC2626), size: 20),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _error!,
                                style: const TextStyle(fontSize: 12, color: Color(0xFF991B1B)),
                              ),
                            ),
                            TextButton(
                              onPressed: _busy ? null : () => _rate(card, _rating ?? 'good'),
                              child: const Text('Thử lại'),
                            ),
                          ],
                        ),
                      ),
                    ),

                  if (_busy)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 4),
                      child: SizedBox(
                        height: 2,
                        child: LinearProgressIndicator(),
                      ),
                    ),

                  // Bottom Action Buttons
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                    child: _buildActionButtons(card),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }

  Widget _buildFrontCard(
    Flashcard card,
    double width,
    double height,
    Offset holeCenter,
  ) {
    return Container(
      width: width,
      height: height,
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
      decoration: BoxDecoration(
        color: const Color(0xFFFCFBF8),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE5DDD0), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Stack(
        children: [
          // Punched hole cutout
          Positioned(
            left: holeCenter.dx - 12 - 20,
            top: holeCenter.dy - 12 - 16,
            child: _buildHoleGrommet(),
          ),
          // Content
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Top row: POS badge
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  if (card.pos != null && card.pos!.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFEFF6FF),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFBFDBFE)),
                      ),
                      child: Text(
                        card.pos!,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF1D4ED8),
                        ),
                      ),
                    ),
                ],
              ),
              const Spacer(),
              // English Word
              Center(
                child: Text(
                  card.word,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF0F172A),
                    letterSpacing: -0.5,
                  ),
                ),
              ),
              const SizedBox(height: 6),
              // IPA phonetic transcription & Pronunciation audio button
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (card.ipa != null && card.ipa!.isNotEmpty)
                    Text(
                      card.ipa!,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFF64748B),
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: _playingAudio
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.volume_up, size: 24),
                    color: const Color(0xFF2563EB),
                    tooltip: 'Nghe phát âm',
                    onPressed: () => _playCardAudio(card),
                  ),
                ],
              ),
              const Spacer(),
              // Flip hint
              Center(
                child: Text.rich(
                  TextSpan(
                    children: [
                      WidgetSpan(
                        alignment: PlaceholderAlignment.middle,
                        child: Padding(
                          padding: const EdgeInsets.only(right: 4),
                          child: Icon(
                            Icons.touch_app_outlined,
                            size: 14,
                            color: Colors.grey.shade500,
                          ),
                        ),
                      ),
                      TextSpan(
                        text: 'Chạm thẻ để lật xem đáp án ↻',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBackCard(
    Flashcard card,
    double width,
    double height,
    Offset holeCenter,
  ) {
    return Container(
      width: width,
      height: height,
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF9),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE5DDD0), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Stack(
        children: [
          // Punched hole cutout (mirrored on back)
          Positioned(
            right: holeCenter.dx - 12 - 20,
            top: holeCenter.dy - 12 - 16,
            child: _buildHoleGrommet(),
          ),
          // Content
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Top row: Source badge & English recap
              Row(
                children: [
                  if (card.sourceLabel != null && card.sourceLabel!.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF3C7),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFFDE68A)),
                      ),
                      child: Text(
                        card.sourceLabel!,
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF92400E),
                        ),
                      ),
                    ),
                  const Spacer(),
                  Text(
                    card.word,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF94A3B8),
                    ),
                  ),
                  const SizedBox(width: 4),
                  IconButton(
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    icon: const Icon(Icons.volume_up, size: 20),
                    color: const Color(0xFF2563EB),
                    tooltip: 'Nghe lại',
                    onPressed: () => _playCardAudio(card),
                  ),
                ],
              ),
              const Spacer(),
              // Vietnamese Meaning
              Center(
                child: Text(
                  card.meaning,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF0F172A),
                  ),
                ),
              ),
              const Spacer(),
              // Swipe instructions
              Center(
                child: Text(
                  '← Kéo trái: Chưa nhớ  |  Kéo phải: Đã nhớ →',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                    color: Colors.grey.shade500,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDummyCard({
    required double width,
    required double height,
    required Color color,
  }) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFE2D8C8), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
    );
  }

  Widget _buildHoleGrommet() {
    return Container(
      width: 24,
      height: 24,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: const Color(0xFFCBD5E1),
        border: Border.all(color: const Color(0xFF94A3B8), width: 2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 2,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Center(
        child: Container(
          width: 14,
          height: 14,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            color: Color(0xFF1E293B),
          ),
        ),
      ),
    );
  }

  Widget _buildStamp({
    required String text,
    required Color color,
    required double angle,
    required double opacity,
  }) {
    return Opacity(
      opacity: opacity,
      child: Transform.rotate(
        angle: angle,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            border: Border.all(color: color, width: 3),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text(
            text,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w900,
              color: color,
              letterSpacing: 1.5,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildActionButtons(Flashcard card) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        // Chưa nhớ button
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFFDC2626),
                side: const BorderSide(color: Color(0xFFFCA5A5), width: 1.5),
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              onPressed: (_busy || _isSwipingOut)
                  ? null
                  : () => _swipeAndRate(card, 'again'),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.close_rounded, size: 18),
                  SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      'Chưa nhớ',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        // Lật thẻ / Xem đáp án button
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: FilledButton.tonal(
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              onPressed: (_busy || _isSwipingOut) ? null : _toggleFlip,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.flip_rounded, size: 18),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      _revealed ? 'Mặt trước' : 'Xem đáp án',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        // Đã nhớ button
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF16A34A),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              onPressed: (_busy || _isSwipingOut)
                  ? null
                  : () => _swipeAndRate(card, 'good'),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.check_rounded, size: 18),
                  SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      'Đã nhớ',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _BinderRingPainter extends CustomPainter {
  static const double ringRadius = 30.0;
  static const double wireThickness = 5.0;

  final bool isForeground;
  final Offset holeCenter;

  _BinderRingPainter({
    required this.isForeground,
    required this.holeCenter,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final ringCenter = Offset(holeCenter.dx, holeCenter.dy - 12);
    final rect = Rect.fromCircle(center: ringCenter, radius: ringRadius);

    if (!isForeground) {
      // Background half of the ring (behind the cards)
      final shadowPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = wireThickness + 2
        ..color = Colors.black.withValues(alpha: 0.12)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
      canvas.drawArc(rect, -pi * 0.95, pi * 1.05, false, shadowPaint);

      final bgPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = wireThickness
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF94A3B8),
            Color(0xFFE2E8F0),
            Color(0xFF64748B),
            Color(0xFFCBD5E1),
          ],
        ).createShader(rect);
      canvas.drawArc(rect, -pi * 0.95, pi * 1.05, false, bgPaint);

      // Ring hinge/clasp detail
      final hingeAngle = -pi * 0.45;
      final hingePos =
          ringCenter + Offset(cos(hingeAngle), sin(hingeAngle)) * ringRadius;
      final hingePaint = Paint()..color = const Color(0xFF64748B);
      canvas.drawCircle(hingePos, wireThickness * 0.8, hingePaint);
    } else {
      // Foreground half of the ring (loops out of hole and across front)
      final fgPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = wireThickness
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0xFFF8FAFC),
            Color(0xFFE2E8F0),
            Color(0xFF94A3B8),
            Color(0xFF475569),
          ],
        ).createShader(rect);

      final highlightPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = 1.5
        ..color = Colors.white.withValues(alpha: 0.9);

      canvas.drawArc(rect, 0.05 * pi, 0.95 * pi, false, fgPaint);
      canvas.drawArc(
        Rect.fromCircle(center: ringCenter, radius: ringRadius - 1),
        0.15 * pi,
        0.75 * pi,
        false,
        highlightPaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _BinderRingPainter oldDelegate) =>
      oldDelegate.isForeground != isForeground ||
      oldDelegate.holeCenter != holeCenter;
}
