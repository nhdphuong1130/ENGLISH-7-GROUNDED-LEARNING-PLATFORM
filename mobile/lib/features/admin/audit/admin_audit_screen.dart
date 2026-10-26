import 'package:flutter/material.dart';

import '../../../app/admin_api.dart';

class AdminAuditScreen extends StatefulWidget {
  final AdminApi api;
  const AdminAuditScreen({super.key, required this.api});
  @override
  State<AdminAuditScreen> createState() => _AdminAuditScreenState();
}

class _AdminAuditScreenState extends State<AdminAuditScreen> {
  late Future<List<AdminAuditRecord>> _events;
  @override
  void initState() {
    super.initState();
    _events = widget.api.loadAdminAudit();
  }

  void _reload() => setState(() => _events = widget.api.loadAdminAudit());

  @override
  Widget build(BuildContext context) => Material(
    child: FutureBuilder<List<AdminAuditRecord>>(
      future: _events,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
            child: FilledButton.icon(
              onPressed: _reload,
              icon: const Icon(Icons.refresh),
              label: const Text('Tải lại'),
            ),
          );
        }
        final items = snapshot.data!;
        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            separatorBuilder: (_, _) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final item = items[index];
              return Card(
                child: ExpansionTile(
                  leading: const Icon(Icons.history),
                  title: Text(item.action),
                  subtitle: Text('${item.entityType} • ${item.entityId}'),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: SelectableText(
                          'Trước:\n${item.before ?? {}}\n\nSau:\n${item.after ?? {}}',
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        );
      },
    ),
  );
}
