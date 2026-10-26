import 'dart:typed_data';

import 'package:image_picker/image_picker.dart';

class SelectedImage {
  final String name;
  final Uint8List bytes;
  final String mediaType;
  const SelectedImage(this.name, this.bytes, this.mediaType);
}

abstract interface class ImageSelector {
  Future<SelectedImage?> select();
  Future<SelectedImage?> capture();
}

class GalleryImageSelector implements ImageSelector {
  final ImagePicker _picker;
  GalleryImageSelector([ImagePicker? picker])
    : _picker = picker ?? ImagePicker();

  @override
  Future<SelectedImage?> select() async {
    final image = await _picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 1920,
      maxHeight: 1920,
      imageQuality: 85,
    );
    if (image == null) return null;
    final mediaType = image.mimeType ?? _mediaTypeForName(image.name);
    return SelectedImage(image.name, await image.readAsBytes(), mediaType);
  }

  @override
  Future<SelectedImage?> capture() async {
    final image = await _picker.pickImage(
      source: ImageSource.camera,
      maxWidth: 1920,
      maxHeight: 1920,
      imageQuality: 85,
    );
    if (image == null) return null;
    final mediaType = image.mimeType ?? _mediaTypeForName(image.name);
    return SelectedImage(image.name, await image.readAsBytes(), mediaType);
  }

  static String _mediaTypeForName(String name) {
    final lower = name.toLowerCase();
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.webp')) return 'image/webp';
    return 'image/jpeg';
  }
}
