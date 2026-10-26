import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../app/learning_api.dart';
import '../../api/api_error.dart';
import '../../services/speech_recorder.dart';
import '../../services/tts_service.dart';

class SpeakingScreen extends StatefulWidget {
  final LearningApi api;
  final Flashcard card;
  final SpeechRecorder? recorder;
  final TtsService? ttsService;

  const SpeakingScreen({
    super.key,
    required this.api,
    required this.card,
    this.recorder,
    this.ttsService,
  });

  @override
  State<SpeakingScreen> createState() => _SpeakingScreenState();
}

class _SpeakingScreenState extends State<SpeakingScreen> {
  late final SpeechRecorder _recorder =
      widget.recorder ?? createSpeechRecorder();
  late final TtsService _tts = widget.ttsService ?? NativeTtsService();

  SpeakingVoices? _voices;
  String? _voice, _error, _requestId, _submittedVoice;
  Uint8List? _audio;
  SpeakingResult? _result;
  Timer? _timer;
  bool _busy = false, _recording = false;

  @override
  void initState() {
    super.initState();
    _loadVoices();
  }

  String get _effectivePrompt => widget.card.word.trim();

  Future<void> _loadVoices() async {
    try {
      final voices = await widget.api.loadVoices();
      if (!mounted) return;
      setState(() {
        _voices = voices;
        _voice = voices.items.any((v) => v.id == voices.selectedVoice)
            ? voices.selectedVoice
            : voices.items.firstOrNull?.id;
        _error = null;
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Không tải được giọng đọc. Hãy thử lại.');
      }
    }
  }

  Future<void> _run(Future<void> Function() work) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await work();
    } catch (e) {
      if (mounted) {
        setState(
          () => _error = e is SpeechRecordingException
              ? e.message
              : e is ApiException &&
                    const {
                      'no_speech',
                      'invalid_recording',
                      'recording_too_large',
                    }.contains(e.code)
              ? 'Chưa nghe rõ bản thu. Em hãy chọn Thu lại và nói rõ trong 15 giây.'
              : 'Thao tác chưa thành công. Kiểm tra kết nối và thử lại.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _playResponse(Future<Uint8List> response) async {
    final bytes = await response;
    if (mounted) await _recorder.play(bytes);
  }

  Future<void> _speakPrompt({double rate = 0.48}) async {
    await _run(() async {
      try {
        await _tts.speak(_effectivePrompt, language: 'en-GB', rate: rate);
      } catch (_) {
        await _playResponse(
          widget.card.audioUrl != null
              ? widget.api.loadSampleAudio(widget.card.audioUrl!)
              : widget.api.loadCardAudio(widget.card.id),
        );
      }
    });
  }

  Future<void> _start() => _run(() async {
    await _recorder.start();
    if (!mounted) {
      await _recorder.dispose();
      return;
    }
    setState(() {
      _recording = true;
      _audio = null;
      _result = null;
      _requestId = null;
      _submittedVoice = null;
    });
    _timer = Timer(const Duration(seconds: 15), () {
      if (mounted) _stopAndSubmit();
    });
  });

  Future<void> _stopAndSubmit() => _run(() async {
    _timer?.cancel();
    Uint8List? bytes;
    try {
      bytes = await _recorder.stop();
      if (mounted) {
        setState(() {
          _audio = bytes;
          _recording = false;
        });
      }
    } finally {
      if (mounted) setState(() => _recording = false);
    }

    if (bytes.isNotEmpty) {
      _requestId ??= learningRequestId();
      _submittedVoice ??= _voice ?? 'en-GB-SoniaNeural';
      final result = await widget.api.submitSpeaking(
        requestId: _requestId!,
        cardId: widget.card.id,
        voiceId: _submittedVoice!,
        audio: bytes,
        prompt: _effectivePrompt,
      );
      if (mounted) {
        setState(() {
          _result = result;
        });
        await _recorder.dispose();
      }
    }
  });

  Future<void> _send() => _run(() async {
    if (_audio == null) return;
    _requestId ??= learningRequestId();
    _submittedVoice ??= _voice;
    final result = await widget.api.submitSpeaking(
      requestId: _requestId!,
      cardId: widget.card.id,
      voiceId: _submittedVoice!,
      audio: _audio!,
      prompt: _effectivePrompt,
    );
    if (mounted) {
      setState(() => _result = result);
      await _recorder.dispose();
    }
  });

  @override
  void dispose() {
    _timer?.cancel();
    _audio = null;
    unawaited(_recorder.dispose());
    unawaited(_tts.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final card = widget.card;
    final ready = _voices?.available == true && _voice != null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Luyện nói từ vựng'),
        toolbarHeight: 48,
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          Text(card.word, style: Theme.of(context).textTheme.headlineMedium),
          if (card.ipa != null && card.ipa!.isNotEmpty)
            Text(
              card.ipa!,
              style: TextStyle(
                fontSize: 14,
                color: Theme.of(context).colorScheme.secondary,
                fontFamily: 'monospace',
              ),
            ),
          Text(card.meaning),
          Text(card.sourceLabel ?? 'Nội dung SGK Unit'),
          const SizedBox(height: 8),

          // Standard Audio Button Row (Normal 1.0x & Slow Turtle 0.5x)
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _busy || _recording ? null : () => _speakPrompt(rate: 0.48),
                  icon: const Icon(Icons.volume_up_rounded, size: 18),
                  label: const Text('Nghe mẫu tiếng Anh'),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.outlined(
                onPressed: _busy || _recording ? null : () => _speakPrompt(rate: 0.32),
                icon: const Icon(Icons.slow_motion_video_rounded),
                tooltip: 'Nghe chậm (0.5x)',
              ),
            ],
          ),

          Padding(
            padding: const EdgeInsets.only(top: 2, bottom: 4),
            child: Text(
              _recording
                  ? 'Đang lắng nghe... Chạm "Dừng thu" để hệ thống tự động chấm điểm ngay.'
                  : 'Nói rõ ràng vào mic. Khi bấm "Dừng thu", hệ thống sẽ tự động gửi và chấm điểm.',
              style: TextStyle(
                fontSize: 11.5,
                color: Theme.of(context).colorScheme.onSurfaceVariant.withValues(alpha: 0.8),
              ),
            ),
          ),

          if (!ready)
            TextButton(
              onPressed: _busy || _recording ? null : () => _run(_loadVoices),
              child: const Text('Tải lại giọng đọc'),
            ),
          if (_voices != null && !ready)
            const Text(
              'Dịch vụ giọng nói chưa sẵn sàng. Bạn có thể tiếp tục học flashcard.',
            ),
          if (_voices != null && _voices!.items.isNotEmpty)
            DropdownButtonFormField<String>(
              isDense: true,
              initialValue: _voice,
              decoration: const InputDecoration(
                labelText: 'Giọng gia sư',
                isDense: true,
                contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              ),
              items: _voices!.items
                  .map(
                    (v) => DropdownMenuItem(value: v.id, child: Text(v.name)),
                  )
                  .toList(),
              onChanged: _busy || _recording || _requestId != null
                  ? null
                  : (value) {
                      if (value != null) {
                        _run(() async {
                          await widget.api.selectVoice(value);
                          if (mounted) setState(() => _voice = value);
                        });
                      }
                    },
            ),
          TextButton(
            onPressed: !ready || _busy || _recording
                ? null
                : () => _run(
                    () => _playResponse(widget.api.previewVoice(_voice!)),
                  ),
            child: const Text('Nghe thử giọng'),
          ),

          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (_busy) const LinearProgressIndicator(),
          const SizedBox(height: 6),

          // Primary Record / Stop Button (Auto-submits on stop!)
          if (_recording)
            FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFFDC2626),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              onPressed: _busy ? null : _stopAndSubmit,
              icon: const Icon(Icons.stop_rounded),
              label: const Text('Dừng thu', style: TextStyle(fontWeight: FontWeight.bold)),
            )
          else
            FilledButton.icon(
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              onPressed: _busy ? null : _start,
              icon: const Icon(Icons.mic_rounded),
              label: Text(
                _audio == null && _result == null ? 'Thu âm' : 'Thu lại',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),

          // In case auto-submit encountered a network error, provide manual retry button
          if (_audio != null && _result == null) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _run(() => _recorder.play(_audio!)),
                    child: const Text('Nghe bản thu'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFF16A34A),
                      foregroundColor: Colors.white,
                    ),
                    onPressed: _busy || !ready ? null : _send,
                    child: const Text('Gửi bản thu'),
                  ),
                ),
              ],
            ),
          ],

          // Results Presentation (Duolingo Style Feedback)
          if (_result != null) ...[
            const Divider(height: 20),
            _buildResultBanner(context),
            const SizedBox(height: 8),
            Text('Câu mẫu: ${_result!.prompt}'),
            Text('Bản chép lời: ${_result!.transcript}'),
            Text(
              'Mức độ khớp câu mẫu: ${_result!.matchPercent.toStringAsFixed(0)}%',
            ),
            const Text(
              'Đây không phải điểm phát âm. Nhận dạng giọng nói có thể sai.',
            ),
            Text(
              'Từ chưa nhận ra: ${_result!.missingWords.isEmpty ? "Không có" : _result!.missingWords.join(", ")}',
            ),
            Text(
              'Từ thừa: ${_result!.extraWords.isEmpty ? "Không có" : _result!.extraWords.join(", ")}',
            ),
            Text(_result!.feedback),
            if (_result!.sourceLabel != null) Text(_result!.sourceLabel!),
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _run(
                            () => _playResponse(
                              widget.api.loadSpeakingAudio(_result!.id),
                            ),
                          ),
                    child: const Text('Nghe phản hồi'),
                  ),
                ),
                if (_audio != null) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _busy
                          ? null
                          : () => _run(() => _recorder.play(_audio!)),
                      child: const Text('Nghe bản thu'),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildResultBanner(BuildContext context) {
    final match = _result!.matchPercent;
    Color bg;
    Color text;
    IconData icon;
    String title;

    if (match >= 80) {
      bg = const Color(0xFFDCFCE7);
      text = const Color(0xFF15803D);
      icon = Icons.check_circle_rounded;
      title = 'Xuất sắc! Phát âm rất chuẩn 🎉';
    } else if (match >= 50) {
      bg = const Color(0xFFE0F2FE);
      text = const Color(0xFF0369A1);
      icon = Icons.thumb_up_rounded;
      title = 'Rất tốt! Cố gắng luyện thêm nhé 👍';
    } else {
      bg = const Color(0xFFFEE2E2);
      text = const Color(0xFFB91C1C);
      icon = Icons.lightbulb_rounded;
      title = 'Hãy nghe lại câu mẫu và thử lại nhé! 🎯';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(icon, color: text, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 13.5,
                color: text,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
