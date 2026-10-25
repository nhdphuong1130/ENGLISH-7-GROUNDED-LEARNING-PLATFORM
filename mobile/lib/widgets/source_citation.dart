import 'package:flutter/material.dart';

import '../app/student_api.dart';

class SourceCitation extends StatelessWidget {
  final SourceReference source;
  const SourceCitation({super.key, required this.source});

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
    return Semantics(
      label: 'Nguồn SGK',
      child: Chip(
        avatar: const Icon(Icons.menu_book, size: 18),
        label: Text(label),
      ),
    );
  }
}
