import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';

class AdminRevisionScreen extends StatefulWidget {
  final AdminApi api;
  final String path;
  final Future<void> Function(int version)? onRestore;
  const AdminRevisionScreen({
    super.key,
    required this.api,
    required this.path,
    this.onRestore,
  });

  @override
  State<AdminRevisionScreen> createState() => _AdminRevisionScreenState();
}

class _AdminRevisionScreenState extends State<AdminRevisionScreen> {
  late final Future<List<AdminRevision>> _revisions = widget.api
      .loadAdminRevisions(widget.path);

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Lịch sử phiên bản')),
    body: FutureBuilder<List<AdminRevision>>(
      future: _revisions,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        return ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: snapshot.data!.length,
          separatorBuilder: (_, _) => const SizedBox(height: 8),
          itemBuilder: (context, index) {
            final item = snapshot.data![index];
            return Card(
              child: ExpansionTile(
                title: Text('Phiên bản ${item.version}'),
                subtitle: Text(item.status),
                children: [
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: SelectableText(
                        item.snapshot.entries
                            .map((entry) => '${entry.key}: ${entry.value}')
                            .join('\n'),
                      ),
                    ),
                  ),
                  if (widget.onRestore != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: OutlinedButton.icon(
                        onPressed: () async {
                          await widget.onRestore!(item.version);
                          if (context.mounted) Navigator.pop(context);
                        },
                        icon: const Icon(Icons.restore),
                        label: const Text('Khôi phục thành bản nháp mới'),
                      ),
                    ),
                ],
              ),
            );
          },
        );
      },
    ),
  );
}
