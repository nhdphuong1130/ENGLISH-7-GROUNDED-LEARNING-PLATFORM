import 'package:flutter/material.dart';

import '../features/auth/login_screen.dart';
import '../features/admin/admin_shell.dart';
import '../features/flashcards/learning_screen.dart';
import '../features/lessons/lesson_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/progress/progress_screen.dart';
import '../features/quizzes/quiz_screen.dart';
import '../features/tutor/image_selector.dart';
import '../features/tutor/tutor_screen.dart';
import 'student_api.dart';

enum _SessionState { checking, authenticated, unauthenticated, failed }

class English7App extends StatefulWidget {
  final StudentApi api;
  final ImageSelector imageSelector;

  const English7App({
    super.key,
    required this.api,
    required this.imageSelector,
  });

  @override
  State<English7App> createState() => _English7AppState();
}

class _English7AppState extends State<English7App> {
  final _navigatorKey = GlobalKey<NavigatorState>();
  _SessionState _sessionState = _SessionState.checking;
  StudentProfile? _profile;

  @override
  void initState() {
    super.initState();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    setState(() => _sessionState = _SessionState.checking);
    try {
      final profile = await widget.api.restoreSession();
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _sessionState = profile == null
            ? _SessionState.unauthenticated
            : _SessionState.authenticated;
      });
    } catch (e, stack) {
      debugPrint('Session restore failed: $e\n$stack');
      if (!mounted) return;
      setState(() => _sessionState = _SessionState.failed);
    }
  }

  void _onAuthenticated() async {
    _navigatorKey.currentState?.popUntil((route) => route.isFirst);
    setState(() => _sessionState = _SessionState.checking);
    try {
      final profile = await widget.api.loadProfile();
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _sessionState = _SessionState.authenticated;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _sessionState = _SessionState.failed);
    }
  }

  Future<void> _logout() async {
    await widget.api.logout();
    if (!mounted) return;
    _navigatorKey.currentState?.popUntil((route) => route.isFirst);
    setState(() {
      _profile = null;
      _sessionState = _SessionState.unauthenticated;
    });
  }

  Widget _home() => switch (_sessionState) {
    _SessionState.checking => const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    ),
    _SessionState.authenticated =>
      _profile?.role == 'admin'
          ? AdminShell(api: widget.api, onLogout: _logout)
          : StudentShell(
              api: widget.api,
              imageSelector: widget.imageSelector,
              onLogout: _logout,
            ),
    _SessionState.unauthenticated => LoginScreen(
      api: widget.api,
      onAuthenticated: _onAuthenticated,
    ),
    _SessionState.failed => Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_rounded, size: 64, color: Colors.grey),
              const SizedBox(height: 16),
              const Text(
                'Không thể kiểm tra phiên đăng nhập',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              const Text(
                'Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại kết nối mạng hoặc đảm bảo backend đang chạy.',
                style: TextStyle(fontSize: 14, color: Colors.grey),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _restoreSession,
                child: const Text('Thử lại'),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: _logout,
                child: const Text('Đăng nhập tài khoản khác'),
              ),
            ],
          ),
        ),
      ),
    ),
  };

  @override
  Widget build(BuildContext context) => MaterialApp(
    navigatorKey: _navigatorKey,
    title: 'English 7',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff2563eb)),
      useMaterial3: true,
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
    ),
    home: _home(),
  );
}

class StudentShell extends StatefulWidget {
  final StudentApi api;
  final ImageSelector imageSelector;
  final Future<void> Function() onLogout;
  const StudentShell({
    super.key,
    required this.api,
    required this.imageSelector,
    required this.onLogout,
  });

  @override
  State<StudentShell> createState() => _StudentShellState();
}

class _StudentShellState extends State<StudentShell> {
  int _index = 0;
  String? _tutorInitialPrompt;

  @override
  Widget build(BuildContext context) {
    final pages = [
      LessonScreen(api: widget.api),
      TutorScreen(
        api: widget.api,
        imageSelector: widget.imageSelector,
        initialPrompt: _tutorInitialPrompt,
      ),
      QuizScreen(api: widget.api),
      ProgressScreen(
        api: widget.api,
        active: _index == 3,
        onNavigateTab: (targetIndex, {initialPrompt}) {
          setState(() {
            _index = targetIndex;
            if (initialPrompt != null) {
              _tutorInitialPrompt = initialPrompt;
            }
          });
        },
      ),
      ProfileScreen(api: widget.api, onLogout: widget.onLogout),
      LearningScreen(api: widget.api),
    ];
    return Scaffold(
      appBar: _index == 5
          ? null
          : AppBar(title: const Text('English 7 Global Success')),
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.menu_book_outlined),
            label: 'Bài học',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            label: 'Tutor',
          ),
          NavigationDestination(
            icon: Icon(Icons.quiz_outlined),
            label: 'Kiểm tra',
          ),
          NavigationDestination(
            icon: Icon(Icons.insights_outlined),
            label: 'Tiến độ',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Cá nhân',
          ),
          NavigationDestination(
            icon: Icon(Icons.style_outlined),
            label: 'Luyện tập',
          ),
        ],
      ),
    );
  }
}
