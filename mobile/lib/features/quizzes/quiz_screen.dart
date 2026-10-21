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
          Center(
            child: Text(
              _clock,
              style: Theme.of(context).textTheme.displaySmall,
            ),
          ),
          const SizedBox(height: 16),
          if (_session!.audioUrl != null) ...[
            LimitedAudioPlayer(
              remainingPlays: _remainingPlays,
              title: _session!.audioTitle,
              isPlaying: _isPlayingAudio,
              onPlay: _playQuizAudio,
              onPause: _pauseQuizAudio,
            ),
            const SizedBox(height: 16),
          ],
          for (var i = 0; i < _session!.questions.length; i++)
            Card(
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
                          backgroundColor: Theme.of(context)
                              .colorScheme
                              .primaryContainer,
                          child: Text(
                            '${i + 1}',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onPrimaryContainer,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'Câu hỏi ${i + 1}',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _session!.questions[i].prompt,
                      style: const TextStyle(fontSize: 15, height: 1.4),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final option in _session!.questions[i].options)
                          ChoiceChip(
                            label: Text(option),
                            selected:
                                _answers[_session!.questions[i].id] == option,
                            onSelected: (selected) {
                              setState(() {
                                if (selected) {
                                  _answers[_session!.questions[i].id] = option;
                                } else {
                                  _answers.remove(_session!.questions[i].id);
                                }
                              });
                            },
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
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
                onSelected: (_) => setState(() => _duration = duration),
              ),
          ],
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('custom-duration'),
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            labelText: 'Thời gian tùy chỉnh',
            helperText:
                '${_options!.customMinimumMinutes}–${_options!.customMaximumMinutes} phút',
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
