import 'package:flutter/material.dart';

import '../app/student_api.dart';

String resolveMediaUrl(String url) {
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  const defaultBase = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
  final base = defaultBase.replaceAll(RegExp(r'/+$'), '');
  var path = url.startsWith('/') ? url : '/$url';
  if (path.startsWith('/images/')) {
    path = '/api/v1/media$path';
  }
  return '$base$path';
}

class SourceCitation extends StatelessWidget {
  final SourceReference source;
  final bool hideImage;
  const SourceCitation({super.key, required this.source, this.hideImage = false});

  void _showFullImage(BuildContext context, String imageUrl) {
    showDialog<void>(
      context: context,
      builder: (ctx) => Dialog(
        insetPadding: const EdgeInsets.all(12),
        backgroundColor: Colors.black.withValues(alpha: 0.85),
        child: Stack(
          alignment: Alignment.topRight,
          children: [
            Center(
              child: InteractiveViewer(
                panEnabled: true,
                boundaryMargin: const EdgeInsets.all(20),
                minScale: 0.8,
                maxScale: 4.0,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.network(
                    imageUrl,
                    fit: BoxFit.contain,
                    errorBuilder: (context, error, stackTrace) => Container(
                      padding: const EdgeInsets.all(32),
                      color: Colors.black87,
                      child: const Text('Không thể tải hình ảnh bài học', style: TextStyle(color: Colors.white)),
                    ),
                  ),
                ),
              ),
            ),
            Positioned(
              top: 8,
              right: 8,
              child: IconButton(
                icon: const Icon(Icons.close, color: Colors.white, size: 28),
                onPressed: () => Navigator.of(ctx).pop(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final printed = source.printedPage;
    final unit = source.unitNumber;
    final label = unit == null
        ? (printed == null
              ? 'SGK PDF trang ${source.pdfPage}'
              : 'SGK trang $printed (PDF ${source.pdfPage})')
        : (printed == null
              ? '[Unit $unit, Page PDF ${source.pdfPage}]'
              : '[Unit $unit, Page $printed] · PDF ${source.pdfPage}');

    final hasImage = !hideImage && source.imageUrl != null && source.imageUrl!.isNotEmpty;

    return Semantics(
      label: 'Nguồn SGK',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Chip(
            avatar: const Icon(Icons.menu_book, size: 18),
            label: Text(label),
          ),
          if (hasImage) ...[
            const SizedBox(height: 8),
            GestureDetector(
              onTap: () => _showFullImage(context, resolveMediaUrl(source.imageUrl!)),
              child: Container(
                constraints: const BoxConstraints(maxHeight: 220),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Theme.of(context).colorScheme.outlineVariant,
                    width: 1,
                  ),
                  color: Theme.of(context).colorScheme.surfaceContainerLow,
                ),
                clipBehavior: Clip.antiAlias,
                child: Stack(
                  alignment: Alignment.bottomRight,
                  children: [
                    Image.network(
                      resolveMediaUrl(source.imageUrl!),
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      margin: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.65),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.zoom_in, color: Colors.white, size: 16),
                          SizedBox(width: 4),
                          Text(
                            'Chạm để phóng to SGK',
                            style: TextStyle(color: Colors.white, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
