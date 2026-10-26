import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import '../../../app/admin_api.dart';

class AdminTransferScreen extends StatefulWidget {
  final AdminApi api;
  final Future<AdminImportFile?> Function()? pickFile;
  final Future<void> Function(String name, Uint8List bytes)? exportHandler;
  const AdminTransferScreen({
    super.key,
    required this.api,
    this.pickFile,
    this.exportHandler,
  });

  @override
  State<AdminTransferScreen> createState() => _AdminTransferScreenState();
}

class _AdminTransferScreenState extends State<AdminTransferScreen> {
  AdminImportFile? _file;
  AdminImportReport? _report;
  bool _busy = false;

  Future<AdminImportFile?> _select() async {
    if (widget.pickFile != null) return widget.pickFile!();
    final file = await openFile(
      acceptedTypeGroups: const [
        XTypeGroup(label: 'Bảng học viên', extensions: ['csv', 'xlsx']),
      ],
    );
    if (file == null) return null;
    final extension = file.name.split('.').last.toLowerCase();
    return AdminImportFile(
      file.name,
      extension == 'csv'
          ? 'text/csv'
          : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      await file.readAsBytes(),
    );
  }

  Future<void> _import(bool dryRun) async {
    final file = dryRun ? await _select() : _file;
    if (file == null || _busy) return;
    setState(() {
      _busy = true;
      _file = file;
    });
    try {
      final report = await widget.api.importAdminStudents(file, dryRun: dryRun);
      if (mounted) setState(() => _report = report);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _export(String format) async {
    final bytes = await widget.api.exportAdminStudentAccounts(format);
    final name = 'student-accounts.$format';
    if (widget.exportHandler != null) {
      await widget.exportHandler!(name, bytes);
      return;
    }
    await SharePlus.instance.share(
      ShareParams(
        files: [
          XFile.fromData(
            bytes,
            name: name,
            mimeType: format == 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Material(
    child: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          'Nhập và xuất dữ liệu',
          style: Theme.of(context).textTheme.headlineSmall
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        const Text(
          'Luôn kiểm tra thử trước khi ghi dữ liệu CSV/XLSX vào hệ thống.',
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Nhập tài khoản học viên',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _busy ? null : () => _import(true),
                  icon: const Icon(Icons.upload_file),
                  label: const Text('Chọn tệp và kiểm tra'),
                ),
                if (_report != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    '${_report!.validRows} dòng hợp lệ • ${_report!.errors.length} lỗi',
                  ),
                  for (final error in _report!.errors)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.error_outline),
                      title: Text('Dòng ${error.row}: ${error.message}'),
                      subtitle: Text(error.code),
                    ),
                  if (!_report!.applied && _report!.validRows > 0)
                    OutlinedButton.icon(
                      onPressed: _busy ? null : () => _import(false),
                      icon: const Icon(Icons.done_all),
                      label: const Text('Áp dụng dữ liệu hợp lệ'),
                    ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Xuất danh sách tài khoản',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  children: [
                    OutlinedButton(
                      onPressed: () => _export('csv'),
                      child: const Text('Xuất CSV'),
                    ),
                    OutlinedButton(
                      onPressed: () => _export('xlsx'),
                      child: const Text('Xuất XLSX'),
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
