import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/student_api.dart';
import '../../services/native_audio_player.dart';
import '../../widgets/audio_player.dart';

class QuizScreen extends StatefulWidget {
  final StudentApi api;
  final QuizSession? initialSession;
  const QuizScreen({super.key, required this.api, this.initialSession});

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  QuizOptions? _options;
  int? _duration;
  String _difficulty = 'adaptive';
  String _mode = 'mixed';
  QuizSession? _session;
  QuizResult? _result;
  final Map<String, String> _answers = {};
  int _remainingSeconds = 0;
  int _remainingPlays = 0;
  bool _isPlayingAudio = false;
  Timer? _timer;
  bool _isLoadingOptions = true;
  String? _loadError;
  bool _isStarting = false;
  bool _isSubmitting = false;
  final TextEditingController _customDurationController = TextEditingController();

  @override
  void initState() {
    super.initState();
    if (widget.initialSession != null) {
      final s = widget.initialSession!;
      _session = s;
      _remainingSeconds = s.durationMinutes * 60;
      _isLoadingOptions = false;
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (!mounted || _remainingSeconds <= 1) {
          timer.cancel();
          if (mounted) setState(() => _remainingSeconds = 0);
        } else {
          setState(() => _remainingSeconds--);
        }
      });
    } else {
      _fetchOptions();
    }
  }

  void _fetchOptions() {
    setState(() {
      _isLoadingOptions = true;
      _loadError = null;
    });
    widget.api
        .loadQuizOptions()
        .then((options) {
          if (!mounted) return;
          setState(() {
            _options = options;
            _duration = options.presetDurations.isNotEmpty
                ? options.presetDurations.first
                : null;
            if (_duration != null) {
              _customDurationController.text = '$_duration';
            }
            _isLoadingOptions = false;
          });
        })
        .catchError((error) {
          if (!mounted) return;
          setState(() {
            _isLoadingOptions = false;
            _loadError =
                'Không thể tải cấu hình bài kiểm tra. Vui lòng thử lại.';
          });
        });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _customDurationController.dispose();
    if (_isPlayingAudio) {
      NativeAudioPlayer.stop();
    }
    super.dispose();
  }

  String _resolveAudioUrl(String rawUrl) {
    if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) {
      return rawUrl;
    }
    const defaultBase = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    );
    final base = defaultBase.replaceAll(RegExp(r'/+$'), '');
    final path = rawUrl.startsWith('/') ? rawUrl : '/$rawUrl';
    return '$base$path';
  }

  Future<void> _playQuizAudio() async {
    if (_session?.audioUrl == null || _remainingPlays <= 0) return;
    setState(() {
      _remainingPlays--;
      _isPlayingAudio = true;
    });
    final resolvedUrl = _resolveAudioUrl(_session!.audioUrl!);
    final success = await NativeAudioPlayer.play(resolvedUrl);
    if (!success && mounted) {
      setState(() => _isPlayingAudio = false);
    }
  }

  Future<void> _pauseQuizAudio() async {
    await NativeAudioPlayer.pause();
    if (mounted) {
      setState(() => _isPlayingAudio = false);
    }
  }

  Future<void> _start() async {
    if (_duration == null) return;
    setState(() => _isStarting = true);
    try {
      final session = await widget.api.createQuiz(
        QuizSetup(_duration!, _difficulty, _mode),
      );
      if (!mounted) return;
      setState(() {
        _session = session;
        _remainingSeconds = session.durationMinutes * 60;
        _remainingPlays = _options!.maxAudioPlays;
        _isPlayingAudio = false;
        _result = null;
        _answers.clear();
        _isStarting = false;
      });
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (!mounted || _remainingSeconds <= 1) {
          timer.cancel();
          if (mounted) setState(() => _remainingSeconds = 0);
        } else {
          setState(() => _remainingSeconds--);
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _isStarting = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Lỗi tạo bài kiểm tra: $e')));
    }
  }

  Future<void> _submit() async {
    if (_isSubmitting || _session == null || _result != null) return;
    setState(() => _isSubmitting = true);
    try {
      final result = await widget.api.submitQuiz(
        _session!.id,
        Map.of(_answers),
      );
      _timer?.cancel();
      if (_isPlayingAudio) {
        await NativeAudioPlayer.stop();
        _isPlayingAudio = false;
      }
      if (mounted) setState(() => _result = result);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Không thể lưu kết quả. Vui lòng thử nộp lại.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  String get _clock {
    final minutes = _remainingSeconds ~/ 60;
    final seconds = _remainingSeconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  Future<void> _showDurationPickerDialog(BuildContext context) async {
    if (_options == null) return;
    final minMins = _options!.customMinimumMinutes;
    final maxMins = _options!.customMaximumMinutes;
    int tempDuration = (_duration ?? minMins).clamp(minMins, maxMins);

    final selected = await showDialog<int>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final theme = Theme.of(context);
            return AlertDialog(
              title: Row(
                children: [
                  Icon(Icons.access_time_filled_rounded, color: theme.colorScheme.primary),
                  const SizedBox(width: 10),
                  const Text('Chọn thời gian'),
                ],
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primaryContainer.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: theme.colorScheme.primary.withValues(alpha: 0.2)),
                    ),
                    child: Column(
                      children: [
                        Icon(
                          Icons.schedule_rounded,
                          size: 52,
                          color: theme.colorScheme.primary,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '$tempDuration phút',
                          style: theme.textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      IconButton.filledTonal(
                        icon: const Icon(Icons.remove),
                        tooltip: 'Giảm 5 phút',
                        onPressed: tempDuration > minMins
                            ? () {
                                setModalState(() {
                                  tempDuration = (tempDuration - 5).clamp(minMins, maxMins);
                                });
                              }
                            : null,
                      ),
                      const SizedBox(width: 16),
                      Text(
                        'Tùy chỉnh nhanh',
                        style: theme.textTheme.labelMedium,
                      ),
                      const SizedBox(width: 16),
                      IconButton.filledTonal(
                        icon: const Icon(Icons.add),
                        tooltip: 'Tăng 5 phút',
                        onPressed: tempDuration < maxMins
                            ? () {
                                setModalState(() {
                                  tempDuration = (tempDuration + 5).clamp(minMins, maxMins);
                                });
                              }
                            : null,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Slider(
                    value: tempDuration.toDouble(),
                    min: minMins.toDouble(),
                    max: maxMins.toDouble(),
                    divisions: (maxMins - minMins).clamp(1, 100),
                    label: '$tempDuration phút',
                    onChanged: (val) {
                      setModalState(() {
                        tempDuration = val.round();
                      });
                    },
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('$minMins phút', style: theme.textTheme.bodySmall),
                        Text('$maxMins phút', style: theme.textTheme.bodySmall),
                      ],
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: const Text('Hủy'),
                ),
                FilledButton.icon(
                  icon: const Icon(Icons.check, size: 18),
                  label: const Text('Áp dụng'),
                  onPressed: () => Navigator.of(ctx).pop(tempDuration),
                ),
              ],
            );
          },
        );
      },
    );

    if (selected != null && mounted) {
      setState(() {
        _duration = selected;
        _customDurationController.text = '$selected';
      });
    }
  }

  String _effectiveSection(QuizQuestion question, int index) {
    if (question.section != null && question.section!.trim().isNotEmpty) {
      return question.section!;
    }
    final qType = question.questionType.toLowerCase();
    final lowerPrompt = question.prompt.toLowerCase();
    final hasAudio = _session?.audioUrl != null;

    if (qType == 'listening' ||
        (hasAudio && index < 2 && question.options.contains('Not given'))) {
      return 'PHẦN A. KỸ NĂNG NGHE (LISTENING)';
    }
    if (qType == 'reading' ||
        question.passage != null ||
        question.options.contains('Not given')) {
      return 'PHẦN C. ĐỌC HIỂU (READING)';
    }
    if (qType == 'reorder' ||
        qType == 'error_correction' ||
        lowerPrompt.contains('/') ||
        lowerPrompt.contains('(a)')) {
      return 'PHẦN D. KỸ NĂNG VIẾT (WRITING)';
    }
    return 'PHẦN B. NGỮ ÂM & NGÔN NGỮ (LANGUAGE FOCUS)';
  }

  String? _effectivePassage(QuizQuestion question) {
    if (question.passage != null && question.passage!.trim().isNotEmpty) {
      return question.passage!;
    }
    final lowerPrompt = question.prompt.toLowerCase();
    if (lowerPrompt.contains('driverless') ||
        lowerPrompt.contains('pedestrian') ||
        lowerPrompt.contains('bamboo-copter') ||
        lowerPrompt.contains('flying car') ||
        lowerPrompt.contains('traffic')) {
      return 'FUTURE MEANS OF TRANSPORT\n\n'
          'In the near future, our means of transport will be much greener, smarter, and safer. '
          'Scientists are actively developing driverless cars powered by electricity and solar panels. '
          'A driverless car allows passengers to read, work, or relax while travelling, as intelligent '
          'onboard computers handle navigation and obstacle detection. In crowded cities, personal '
          'aerial vehicles such as the bamboo-copter and solar-powered jetpacks will help commuters fly '
          'over traffic jams. Furthermore, strict traffic safety regulations will still apply: '
          'pedestrians must obey street signs and never cross the road on a red light.';
    }
    if (lowerPrompt.contains('alaska') ||
        lowerPrompt.contains('arctic') ||
        lowerPrompt.contains('glacier') ||
        lowerPrompt.contains('sledding')) {
      return 'ALASKA - THE AMAZING STATE\n\n'
          'Alaska is perhaps the most amazing state in the USA. It has coastlines facing '
          'both the Arctic Ocean and the Pacific Ocean. Alaska has more than three million lakes '
          'and over one hundred thousand glaciers. Many people visit Alaska every year to enjoy '
          'dog sledding, fishing, and watching unique wildlife such as grizzly bears and bald eagles. '
          'Solar and wind energy are also being developed in Alaska to provide clean power for remote villages.';
    }
    if (lowerPrompt.contains('london') ||
        lowerPrompt.contains('portobello') ||
        lowerPrompt.contains('antique') ||
        lowerPrompt.contains('market')) {
      return 'PORTOBELLO MARKET IN LONDON\n\n'
          'Visitors to London are struck by the splendour of one of the world\'s oldest capitals, '
          'admiring iconic sites like Big Ben and Buckingham Palace. However, visitors seeking everyday '
          'life should not miss Portobello Market, the most-visited street market in London.\n\n'
          'Portobello Market is divided into different sections selling second-hand items, clothing, jewellery, '
          'souvenirs, and fresh food. The most sought-after area is devoted to antiques with over 1,000 booths '
          'manned by antique dealers from throughout England.';
    }
    return null;
  }

  Widget _buildExamHeader() {
    final modeTitle = switch (_mode) {
      'listening' => 'KỸ NĂNG NGHE (LISTENING)',
      'reading' => 'ĐỌC HIỂU & NGÔN NGỮ (READING & LANGUAGE)',
      _ => 'ĐỀ THI TỔNG HỢP (COMPREHENSIVE EXAMINATION)',
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outlineVariant,
          width: 1.2,
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
        children: [
          Text(
            'BỘ GIÁO DỤC VÀ ĐÀO TẠO',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.2,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            'CHƯƠNG TRÌNH TIẾNG ANH 7 GLOBAL SUCCESS',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.5,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            modeTitle,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 10),
          Divider(
            height: 1,
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              Row(
                children: [
                  const Icon(Icons.timer_outlined, size: 18, color: Colors.deepOrange),
                  const SizedBox(width: 6),
                  Text(
                    _clock,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Colors.deepOrange,
                    ),
                  ),
                ],
              ),
              Row(
                children: [
                  const Icon(Icons.quiz_outlined, size: 18, color: Colors.indigo),
                  const SizedBox(width: 6),
                  Text(
                    '${_session!.questions.length} câu hỏi',
                    style: const TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
              Row(
                children: [
                  const Icon(Icons.tune_rounded, size: 18, color: Colors.teal),
                  const SizedBox(width: 6),
                  const Text(
                    'Thích ứng',
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String sectionTitle) {
    IconData icon = Icons.assignment_outlined;
    String instruction = '';
    final lower = sectionTitle.toLowerCase();
    if (lower.contains('nghe') || lower.contains('listening')) {
      icon = Icons.headphones;
      instruction =
          'Listen to the recording and decide whether each statement is True (T), False (F), or Not Given (NG):\n'
          '(Nghe đoạn ghi âm và chọn True, False hoặc Not given cho mỗi câu dưới đây:)';
    } else if (lower.contains('đọc') || lower.contains('reading')) {
      icon = Icons.menu_book_rounded;
      instruction =
          'Read the following passage and mark the letter A, B, C, or D (or True/False/Not given) to indicate the correct answer:\n'
          '(Đọc đoạn văn sau và chọn đáp án đúng nhất cho các câu hỏi bên dưới:)';
    } else if (lower.contains('viết') ||
        lower.contains('writing') ||
        lower.contains('sắp xếp')) {
      icon = Icons.edit_note;
      instruction =
          'Mark the letter A, B, C, or D to indicate the correct sentence or the underlined part that needs correction:\n'
          '(Chọn chữ cái A, B, C hoặc D để hoàn chỉnh câu hoặc phát hiện lỗi sai trong câu:)';
    } else if (lower.contains('ngôn ngữ') ||
        lower.contains('ngữ pháp') ||
        lower.contains('language')) {
      icon = Icons.spellcheck;
      instruction =
          'Mark the letter A, B, C, or D on your answer sheet to indicate the correct answer to each of the following questions:\n'
          '(Chọn đáp án đúng nhất A, B, C hoặc D để hoàn thành các câu sau:)';
    }

    final isListening = lower.contains('nghe') || lower.contains('listening');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          margin: const EdgeInsets.only(top: 20, bottom: 8),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: Theme.of(context)
                .colorScheme
                .primaryContainer
                .withValues(alpha: 0.7),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color:
                  Theme.of(context).colorScheme.primary.withValues(alpha: 0.3),
            ),
          ),
          child: Row(
            children: [
              Icon(icon, size: 20, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  sectionTitle,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (instruction.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 8),
            child: Text(
              instruction,
              style: TextStyle(
                fontSize: 12.5,
                fontStyle: FontStyle.italic,
                height: 1.4,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        if (isListening && _session?.audioUrl != null) ...[
          LimitedAudioPlayer(
            remainingPlays: _remainingPlays,
            title: _session!.audioTitle,
            isPlaying: _isPlayingAudio,
            onPlay: _playQuizAudio,
            onPause: _pauseQuizAudio,
          ),
          const SizedBox(height: 12),
        ],
      ],
    );
  }

  Widget _buildPassageCard(String passage) {
    return Container(
      margin: const EdgeInsets.only(top: 6, bottom: 16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Theme.of(context).colorScheme.outlineVariant,
          width: 1.2,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: Theme.of(context)
                  .colorScheme
                  .primaryContainer
                  .withValues(alpha: 0.35),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(11),
                topRight: Radius.circular(11),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.menu_book_rounded,
                  size: 18,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'BÀI ĐỌC (READING PASSAGE)',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13.5,
                    letterSpacing: 0.5,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SelectableText(
                  passage,
                  style: const TextStyle(
                    fontSize: 14.5,
                    height: 1.6,
                    letterSpacing: 0.15,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '(Adapted from Tiếng Anh 7 Global Success)',
                  style: TextStyle(
                    fontSize: 12,
                    fontStyle: FontStyle.italic,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuestionCard(QuizQuestion question, int index) {
    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 12,
                  backgroundColor:
                      Theme.of(context).colorScheme.primaryContainer,
                  child: Text(
                    '${index + 1}',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color:
                          Theme.of(context).colorScheme.onPrimaryContainer,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  'Câu hỏi ${index + 1}',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                if (_buildQuestionTypeBadge(question.questionType) != null)
                  _buildQuestionTypeBadge(question.questionType)!,
              ],
            ),
            const SizedBox(height: 10),
            if (question.questionType == 'reorder') ...[
              Text(
                'Sắp xếp các từ/cụm từ sau thành câu hoàn chỉnh:',
                style: TextStyle(
                  fontSize: 12,
                  fontStyle: FontStyle.italic,
                  color: Colors.teal.shade800,
                ),
              ),
              const SizedBox(height: 4),
            ] else if (question.questionType == 'error_correction') ...[
              Text(
                'Chọn phần gạch chân (A, B, C hoặc D) bị sai ngữ pháp:',
                style: TextStyle(
                  fontSize: 12,
                  fontStyle: FontStyle.italic,
                  color: Colors.orange.shade900,
                ),
              ),
              const SizedBox(height: 4),
            ],
            Text(
              question.prompt,
              style: const TextStyle(fontSize: 15, height: 1.4),
            ),
            const SizedBox(height: 12),
            if (question.options.any((opt) => opt.length > 25))
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  for (final option in question.options)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: ChoiceChip(
                        label: SizedBox(
                          width: double.infinity,
                          child: Text(
                            option,
                            style: const TextStyle(fontSize: 14),
                          ),
                        ),
                        selected: _answers[question.id] == option,
                        onSelected: (selected) {
                          setState(() {
                            if (selected) {
                              _answers[question.id] = option;
                            } else {
                              _answers.remove(question.id);
                            }
                          });
                        },
                      ),
                    ),
                ],
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final option in question.options)
                    ChoiceChip(
                      label: Text(option),
                      selected: _answers[question.id] == option,
                      onSelected: (selected) {
                        setState(() {
                          if (selected) {
                            _answers[question.id] = option;
                          } else {
                            _answers.remove(question.id);
                          }
                        });
                      },
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget? _buildQuestionTypeBadge(String type) {
    switch (type) {
      case 'reorder':
        return Chip(
          visualDensity: VisualDensity.compact,
          avatar: const Icon(Icons.sort, size: 14, color: Colors.teal),
          label: const Text(
            'Sắp xếp câu',
            style: TextStyle(
              fontSize: 11,
              color: Colors.teal,
              fontWeight: FontWeight.w600,
            ),
          ),
          backgroundColor: Colors.teal.withValues(alpha: 0.08),
          side: BorderSide(color: Colors.teal.withValues(alpha: 0.25)),
        );
      case 'error_correction':
        return Chip(
          visualDensity: VisualDensity.compact,
          avatar: Icon(
            Icons.find_replace,
            size: 14,
            color: Colors.orange.shade800,
          ),
          label: Text(
            'Tìm lỗi sai',
            style: TextStyle(
              fontSize: 11,
              color: Colors.orange.shade800,
              fontWeight: FontWeight.w600,
            ),
          ),
          backgroundColor: Colors.orange.withValues(alpha: 0.08),
          side: BorderSide(color: Colors.orange.withValues(alpha: 0.25)),
        );
      case 'reading':
        return Chip(
          visualDensity: VisualDensity.compact,
          avatar: Icon(
            Icons.chrome_reader_mode,
            size: 14,
            color: Colors.blue.shade700,
          ),
          label: Text(
            'Đọc hiểu',
            style: TextStyle(
              fontSize: 11,
              color: Colors.blue.shade700,
              fontWeight: FontWeight.w600,
            ),
          ),
          backgroundColor: Colors.blue.withValues(alpha: 0.08),
          side: BorderSide(color: Colors.blue.withValues(alpha: 0.25)),
        );
      case 'language':
        return Chip(
          visualDensity: VisualDensity.compact,
          avatar: Icon(
            Icons.spellcheck,
            size: 14,
            color: Colors.purple.shade700,
          ),
          label: Text(
            'Ngữ pháp & Từ vựng',
            style: TextStyle(
              fontSize: 11,
              color: Colors.purple.shade700,
              fontWeight: FontWeight.w600,
            ),
          ),
          backgroundColor: Colors.purple.withValues(alpha: 0.08),
          side: BorderSide(color: Colors.purple.withValues(alpha: 0.25)),
        );
      case 'listening':
        return Chip(
          visualDensity: VisualDensity.compact,
          avatar: Icon(
            Icons.headphones,
            size: 14,
            color: Colors.green.shade700,
          ),
          label: Text(
            'Nghe hiểu',
            style: TextStyle(
              fontSize: 11,
              color: Colors.green.shade700,
              fontWeight: FontWeight.w600,
            ),
          ),
          backgroundColor: Colors.green.withValues(alpha: 0.08),
          side: BorderSide(color: Colors.green.withValues(alpha: 0.25)),
        );
      default:
        return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_result != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.emoji_events, size: 64, color: Colors.amber),
            const SizedBox(height: 16),
            Text(
              'Kết quả: ${_result!.correct}/${_result!.total}',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () {
                if (_isPlayingAudio) {
                  NativeAudioPlayer.stop();
                }
                setState(() {
                  _session = null;
                  _result = null;
                  _isPlayingAudio = false;
                  _answers.clear();
                });
              },
              icon: const Icon(Icons.refresh),
              label: const Text('Làm bài mới'),
            ),
          ],
        ),
      );
    }
    if (_session != null) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildExamHeader(),
          for (var i = 0; i < _session!.questions.length; i++) ...[
            if (i == 0 ||
                _effectiveSection(_session!.questions[i], i) !=
                    _effectiveSection(_session!.questions[i - 1], i - 1))
              _buildSectionHeader(
                _effectiveSection(_session!.questions[i], i),
              ),
            if (_effectivePassage(_session!.questions[i]) != null &&
                (i == 0 ||
                    _effectivePassage(_session!.questions[i]) !=
                        _effectivePassage(_session!.questions[i - 1])))
              _buildPassageCard(
                _effectivePassage(_session!.questions[i])!,
              ),
            _buildQuestionCard(_session!.questions[i], i),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _isSubmitting ? null : _submit,
            child: Text(_isSubmitting ? 'Đang lưu...' : 'Nộp bài'),
          ),
        ],
      );
    }
    if (_loadError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              Text(_loadError!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.tonal(
                onPressed: _fetchOptions,
                child: const Text('Thử lại'),
              ),
            ],
          ),
        ),
      );
    }
    if (_isLoadingOptions || _options == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Tạo bài kiểm tra',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 16),
        Text('Hình thức thi', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            ChoiceChip(
              label: const Text('Đề thi Tổng hợp'),
              selected: _mode == 'mixed',
              onSelected: (_) => setState(() => _mode = 'mixed'),
            ),
            ChoiceChip(
              label: const Text('Kỹ năng Nghe'),
              selected: _mode == 'listening',
              onSelected: (_) => setState(() => _mode = 'listening'),
            ),
            ChoiceChip(
              label: const Text('Đọc hiểu & Ngôn ngữ'),
              selected: _mode == 'reading',
              onSelected: (_) => setState(() => _mode = 'reading'),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Text(
          'Thời gian làm bài',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            for (final duration in _options!.presetDurations)
              ChoiceChip(
                label: Text('$duration phút'),
                selected: _duration == duration,
                onSelected: (_) => setState(() {
                  _duration = duration;
                  _customDurationController.text = '$duration';
                }),
              ),
          ],
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('custom-duration'),
          controller: _customDurationController,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            labelText: 'Thời gian tùy chỉnh',
            hintText: 'Nhập số phút',
            prefixIcon: const Icon(Icons.timer_outlined),
            suffixText: 'phút',
            suffixIcon: IconButton(
              icon: const Icon(Icons.access_time_filled_rounded),
              tooltip: 'Mở bộ chọn thời gian',
              onPressed: () => _showDurationPickerDialog(context),
            ),
            helperText:
                '${_options!.customMinimumMinutes}–${_options!.customMaximumMinutes} phút (bấm biểu tượng đồng hồ để điều chỉnh trực quan)',
          ),
          onChanged: (value) {
            final parsed = int.tryParse(value);
            if (parsed != null &&
                parsed >= _options!.customMinimumMinutes &&
                parsed <= _options!.customMaximumMinutes) {
              setState(() => _duration = parsed);
            }
          },
        ),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
          initialValue: _difficulty,
          decoration: const InputDecoration(labelText: 'Độ khó'),
          items: const [
            DropdownMenuItem(value: 'adaptive', child: Text('Thích ứng')),
            DropdownMenuItem(value: 'easy', child: Text('Dễ')),
            DropdownMenuItem(value: 'medium', child: Text('Trung bình')),
            DropdownMenuItem(value: 'hard', child: Text('Khó')),
          ],
          onChanged: (value) => setState(() => _difficulty = value!),
        ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: _isStarting ? null : _start,
          child: _isStarting
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Text('Bắt đầu'),
        ),
      ],
    );
  }
}
